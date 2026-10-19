from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_steps import current_name
from app.modules.film_clones.models import (
    AssetKind,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneStatus,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.films.errors import FilmConflictError, FilmNotFoundError, InvalidFilmRequestError
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_imports import (
    CharacterSeed,
    FileCopy,
    FilmImports,
    ReferenceFile,
    to_image_extension,
)
from app.modules.films.film_prompts import to_project_aspect
from app.modules.films.models import (
    Character,
    EntityType,
    EpisodePart,
    FilmProject,
    MediaStatus,
    ReferenceSource,
    Scene,
    SceneImageSource,
    Style,
)
from app.modules.films.part_rules import MAX_PART_SCENES, to_part_number
from app.modules.films.repository import FilmRepository
from app.modules.films.scene_resets import DEFAULT_TRIM_START_MS
from app.modules.films.scene_rules import SCENE_PROMPT_LIMIT
from app.modules.films.style_service import get_known_style
from app.modules.films.views import CUT_HEAD_S
from app.modules.jobs.storage import JobStorage

SOURCE_CLONE_REQUIRED_MESSAGE = "sourceCloneId is required for a film clone source"
CLONE_NOT_FOUND_MESSAGE = "Film clone {clone_id} not found"
CLONE_NOT_DONE_MESSAGE = "Film clone {clone_id} is not done"
LANGUAGE_MISMATCH_MESSAGE = (
    "The clone is written in {clone_language}; the project narrates in {project_language}"
)
ASPECT_MISMATCH_MESSAGE = "The clone's images are {aspect}; the project is {orientation}"
DIALOGUE_LINE = "Dialogue: {dialogue}"
CLONE_PART_TITLE = "Part {number}"
CLONE_PART_PLAN = "Scenes {first}-{last} of the film clone."
ENTITY_TYPES_BY_ASSET_KIND = {
    AssetKind.CHARACTER: EntityType.CHARACTER,
    AssetKind.COSTUME: EntityType.VISUAL_ASSET,
    AssetKind.PROP: EntityType.VISUAL_ASSET,
    AssetKind.LOCATION: EntityType.LOCATION,
}


@dataclass(frozen=True)
class CloneSourceTools:
    repository: FilmRepository
    files: FilmFiles
    imports: FilmImports
    clone_repository: FilmCloneRepository
    clone_files: CloneFiles
    job_storage: JobStorage


@dataclass(frozen=True)
class CloneImportTarget:
    project: FilmProject
    episode_id: str


@dataclass(frozen=True)
class CloneImport:
    new_characters: tuple[Character, ...]
    linked_character_ids: tuple[str, ...]
    parts: tuple[EpisodePart, ...]
    scenes: tuple[Scene, ...]
    file_copies: tuple[FileCopy, ...]


@dataclass
class _ImportPlan:
    clone: FilmClone
    style: Style
    target: CloneImportTarget
    new_characters: list[Character] = field(default_factory=list)
    linked_character_ids: list[str] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    part_ids: list[str] = field(default_factory=list)
    file_copies: list[FileCopy] = field(default_factory=list)
    character_ids_by_name: dict[str, str] = field(default_factory=dict)
    character_ids_by_asset_id: dict[str, str] = field(default_factory=dict)

    def next_scene_part_id(self) -> str:
        if len(self.scenes) == len(self.part_ids) * MAX_PART_SCENES:
            self.part_ids.append(str(uuid4()))
        return self.part_ids[-1]

    def to_import(self) -> CloneImport:
        return CloneImport(
            new_characters=tuple(self.new_characters),
            linked_character_ids=tuple(self.linked_character_ids),
            parts=tuple(self._to_part(position) for position in range(len(self.part_ids))),
            scenes=tuple(self.scenes),
            file_copies=tuple(self.file_copies),
        )

    def _to_part(self, position: int) -> EpisodePart:
        first = position * MAX_PART_SCENES
        scene_count = len(self.scenes[first : first + MAX_PART_SCENES])
        return EpisodePart(
            id=self.part_ids[position],
            episode_id=self.target.episode_id,
            position=position,
            title=CLONE_PART_TITLE.format(number=to_part_number(position)),
            plan=CLONE_PART_PLAN.format(first=first + 1, last=first + scene_count),
            target_duration_s=scene_count * (self.target.project.clip_duration_s - CUT_HEAD_S),
            recap=None,
        )


def to_video_prompt(clone_scene: CloneScene) -> str:
    parts = [clone_scene.description.strip()]
    dialogue = (clone_scene.dialogue or "").strip()
    if dialogue:
        parts.append(DIALOGUE_LINE.format(dialogue=dialogue))
    return "\n".join(parts)[:SCENE_PROMPT_LIMIT]


def to_current_description(asset: CloneAsset) -> str:
    if asset.changed and asset.localized_description:
        return asset.localized_description
    return asset.description


class CloneSource:
    def __init__(self, tools: CloneSourceTools):
        self._tools = tools

    def get_done_clone(self, clone_id: str | None, project: FilmProject) -> FilmClone:
        if not clone_id:
            raise InvalidFilmRequestError(SOURCE_CLONE_REQUIRED_MESSAGE)
        clone = self._tools.clone_repository.find_by_id(clone_id)
        if clone is None:
            raise FilmNotFoundError(CLONE_NOT_FOUND_MESSAGE.format(clone_id=clone_id))
        if clone.status is not CloneStatus.DONE:
            raise FilmConflictError(CLONE_NOT_DONE_MESSAGE.format(clone_id=clone_id))
        if clone.script_language != project.language.value:
            raise FilmConflictError(
                LANGUAGE_MISMATCH_MESSAGE.format(
                    clone_language=clone.script_language, project_language=project.language
                )
            )
        if clone.aspect is None or clone.aspect.value != to_project_aspect(project.orientation):
            raise FilmConflictError(
                ASPECT_MISMATCH_MESSAGE.format(aspect=clone.aspect, orientation=project.orientation)
            )
        return clone

    def has_clone(self, clone_id: str | None) -> bool:
        if clone_id is None:
            return False
        return self._tools.clone_repository.find_by_id(clone_id) is not None

    def plan_import(self, clone: FilmClone, target: CloneImportTarget) -> CloneImport:
        style = get_known_style(self._tools.repository, target.project.style_id)
        plan = _ImportPlan(clone=clone, style=style, target=target)
        for asset in self._tools.clone_repository.find_assets(clone.id):
            self._add_asset(asset, plan)
        for clone_scene in self._tools.clone_repository.find_scenes(clone.id):
            self._add_scene(clone_scene, plan)
        return plan.to_import()

    def _add_asset(self, asset: CloneAsset, plan: _ImportPlan) -> None:
        name_key = current_name(asset).casefold()
        if name_key not in plan.character_ids_by_name:
            plan.character_ids_by_name[name_key] = self._link_or_create(asset, plan)
        plan.character_ids_by_asset_id[asset.id] = plan.character_ids_by_name[name_key]

    def _link_or_create(self, asset: CloneAsset, plan: _ImportPlan) -> str:
        name = current_name(asset)
        library_character = self._tools.repository.find_character_by_name(name)
        if library_character is not None:
            plan.linked_character_ids.append(library_character.id)
            return library_character.id
        planned = self._tools.imports.plan_character(
            CharacterSeed(
                id=str(uuid4()),
                name=name,
                entity_type=ENTITY_TYPES_BY_ASSET_KIND[asset.kind],
                description=to_current_description(asset),
                voice_description=None,
                style=plan.style,
                reference=self._find_reference(plan.clone, asset),
                origin_clone_id=plan.clone.id,
            )
        )
        plan.new_characters.append(planned.character)
        plan.linked_character_ids.append(planned.character.id)
        plan.file_copies.extend(planned.file_copies)
        return planned.character.id

    def _find_reference(self, clone: FilmClone, asset: CloneAsset) -> ReferenceFile | None:
        path = (
            self._find_generated_reference(asset)
            if asset.changed
            else self._find_frame(clone, asset)
        )
        if path is None or not path.is_file():
            return None
        return ReferenceFile(path, ReferenceSource.FILM_CLONE)

    def _find_generated_reference(self, asset: CloneAsset) -> Path | None:
        if asset.reference_status is not CloneImageStatus.DONE or not asset.reference_path:
            return None
        return self._tools.clone_files.to_absolute(asset.reference_path)

    def _find_frame(self, clone: FilmClone, asset: CloneAsset) -> Path | None:
        if not asset.reference_frame:
            return None
        return self._tools.job_storage.output_dir(clone.job_id) / asset.reference_frame

    def _add_scene(self, clone_scene: CloneScene, plan: _ImportPlan) -> None:
        scene_id = str(uuid4())
        character_ids = [
            plan.character_ids_by_asset_id[asset_id]
            for asset_id in clone_scene.asset_ids
            if asset_id in plan.character_ids_by_asset_id
        ]
        part_id = plan.next_scene_part_id()
        plan.scenes.append(
            Scene(
                id=scene_id,
                episode_id=plan.target.episode_id,
                part_id=part_id,
                position=len(plan.scenes) % MAX_PART_SCENES,
                image_prompt=clone_scene.image_prompt[:SCENE_PROMPT_LIMIT],
                video_prompt=to_video_prompt(clone_scene),
                narrator_text=None,
                character_ids=list(dict.fromkeys(character_ids)),
                clip_duration_s=plan.target.project.clip_duration_s,
                clip_status=MediaStatus.NONE,
                narration_status=MediaStatus.NONE,
                trim_start_ms=DEFAULT_TRIM_START_MS,
                trim_end_ms=None,
                **self._plan_scene_image(scene_id, clone_scene, plan),
            )
        )

    def _plan_scene_image(
        self, scene_id: str, clone_scene: CloneScene, plan: _ImportPlan
    ) -> dict[str, Any]:
        image = self._find_scene_image(clone_scene)
        if image is None:
            return {"image_status": MediaStatus.NONE}
        destination = self._tools.files.scene_image_path(
            plan.target.project.id, plan.target.episode_id, scene_id, to_image_extension(image)
        )
        plan.file_copies.append(FileCopy(image, destination))
        return {
            "image_status": MediaStatus.DONE,
            "image_source": SceneImageSource.FILM_CLONE,
            "image_path": self._tools.files.to_relative(destination),
        }

    def _find_scene_image(self, clone_scene: CloneScene) -> Path | None:
        if clone_scene.image_status is not CloneImageStatus.DONE or not clone_scene.image_path:
            return None
        image = self._tools.clone_files.to_absolute(clone_scene.image_path)
        return image if image.is_file() else None
