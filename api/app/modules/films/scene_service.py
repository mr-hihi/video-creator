from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.modules.films.errors import FilmConflictError, InvalidFilmRequestError, SceneNotFoundError
from app.modules.films.field_rules import to_bounded_text
from app.modules.films.film_access import FilmAccess, SceneContext
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue, SceneOrderContext
from app.modules.films.models import (
    Episode,
    EpisodeStatus,
    FilmProject,
    MediaStatus,
    Scene,
    SceneImageSource,
    VoiceTemplate,
)
from app.modules.films.part_rules import MAX_PART_SCENES, TOO_MANY_PART_SCENES_MESSAGE
from app.modules.films.project_service import EDIT_PROMPT_LIMIT, EDIT_PROMPT_MESSAGE
from app.modules.films.repository import FilmRepository
from app.modules.films.scene_resets import DEFAULT_TRIM_START_MS, NARRATION_RESET, NEW_IMAGE_RESET
from app.modules.films.scene_rules import (
    TrimRange,
    ensure_valid_trim,
    to_insert_position,
    to_valid_character_ids,
    to_valid_image_prompt,
    to_valid_narration,
    to_valid_position,
    to_valid_scene_clip_duration,
    to_valid_video_prompt,
)
from app.modules.films.stage_runner import NO_NARRATOR_MESSAGE
from app.modules.films.upload_rules import (
    IMAGE_UPLOAD,
    FileUpload,
    build_too_large_message,
    to_upload_extension,
)
from app.modules.media_generation.models import GenerationRequest

SCENE_GENERATION_RUNNING_MESSAGE = "Scene {number} has generation running"
REFERENCES_FIRST_MESSAGE = "Generate the reference images of {names} first"
NO_IMAGE_YET_MESSAGE = "Scene {number} has no image yet"
NO_IMAGE_TO_EDIT_MESSAGE = "Scene {number} has no image to edit"
NO_NARRATION_TEXT_MESSAGE = "Scene {number} has no narration text"
NO_CLIP_YET_MESSAGE = "Scene {number} has no clip yet"
PART_NOT_IN_EPISODE_MESSAGE = "Part {part_id} is not in this episode"
NAME_SEPARATOR = ", "
TRIM_FIELDS = ("trim_start_ms", "trim_end_ms")
UPLOADED_IMAGE_VALUES = {
    **NEW_IMAGE_RESET,
    "image_status": MediaStatus.DONE,
    "image_source": SceneImageSource.UPLOADED,
    "image_error": None,
    "provider_media": None,
}


@dataclass(frozen=True)
class SceneDraft:
    part_id: str
    after_position: int | None
    image_prompt: str
    video_prompt: str
    narrator_text: str | None
    character_ids: Sequence[str]
    clip_duration_s: int | None = None


@dataclass(frozen=True)
class SceneServiceTools:
    repository: FilmRepository
    access: FilmAccess
    files: FilmFiles
    media_queue: FilmMediaQueue


def to_order_context(context: SceneContext) -> SceneOrderContext:
    return SceneOrderContext(context.project, context.episode.id, context.scene)


class SceneService:
    def __init__(self, tools: SceneServiceTools):
        self._tools = tools

    def add_scene(self, episode_id: str, draft: SceneDraft) -> Scene:
        context = self._tools.access.get_editable_episode(episode_id)
        part = self._tools.repository.find_part(draft.part_id)
        if part is None or part.episode_id != episode_id:
            raise InvalidFilmRequestError(PART_NOT_IN_EPISODE_MESSAGE.format(part_id=draft.part_id))
        scene_count = self._count_scenes(part.id)
        if scene_count >= MAX_PART_SCENES:
            raise InvalidFilmRequestError(TOO_MANY_PART_SCENES_MESSAGE)
        scene = Scene(
            id=str(uuid4()),
            episode_id=episode_id,
            part_id=part.id,
            position=to_insert_position(draft.after_position, scene_count),
            image_prompt=to_valid_image_prompt(draft.image_prompt),
            video_prompt=to_valid_video_prompt(draft.video_prompt),
            narrator_text=to_valid_narration(draft.narrator_text),
            character_ids=self._to_cast_ids(context.project, draft.character_ids),
            clip_duration_s=(
                context.project.clip_duration_s
                if draft.clip_duration_s is None
                else to_valid_scene_clip_duration(draft.clip_duration_s)
            ),
            image_status=MediaStatus.NONE,
            clip_status=MediaStatus.NONE,
            narration_status=MediaStatus.NONE,
            trim_start_ms=DEFAULT_TRIM_START_MS,
            trim_end_ms=None,
        )
        self._tools.repository.insert_scene(scene)
        self._flag_assembly(context.episode)
        return self._reload(scene.id)

    def update_scene(self, scene_id: str, changes: Mapping[str, Any]) -> Scene:
        context = self._tools.access.get_editable_scene(scene_id)
        self._ensure_trimmable(context.scene, changes)
        values = {
            **self._to_scene_values(context, changes),
            **to_narration_values(context.scene, changes),
            **to_trim_values(context.scene, changes),
        }
        new_position = self._to_new_position(context, changes)
        if values:
            self._tools.repository.update_scene(scene_id, values)
        if new_position is not None:
            self._tools.repository.move_scene(context.scene, new_position)
        if "narration_status" in values:
            self._tools.files.delete(context.scene.narration_path)
        if new_position is not None or is_reset_or_trim(context.scene, values):
            self._flag_assembly(context.episode)
        return self._reload(scene_id)

    def delete_scene(self, scene_id: str) -> None:
        context = self._get_idle_scene(scene_id)
        self._tools.repository.delete_scene(context.scene)
        self._tools.files.delete_dir(
            self._tools.files.scene_dir(context.project.id, context.episode.id, scene_id)
        )
        self._flag_assembly(context.episode)

    def upload_image(self, scene_id: str, upload: FileUpload) -> Scene:
        context = self._get_idle_scene(scene_id)
        extension = to_upload_extension(upload.filename, IMAGE_UPLOAD)
        destination = self._tools.files.scene_image_path(
            context.project.id, context.episode.id, scene_id, extension
        )
        self._tools.files.save_upload(
            upload.stream,
            destination,
            build_too_large_message(IMAGE_UPLOAD, self._tools.files.max_upload_mb),
        )
        self._tools.repository.update_scene(
            scene_id,
            {**UPLOADED_IMAGE_VALUES, "image_path": self._tools.files.to_relative(destination)},
        )
        self._tools.files.delete(context.scene.clip_path)
        self._tools.files.delete_dir(
            self._tools.files.scene_clip_segments_dir(
                context.project.id, context.episode.id, scene_id
            )
        )
        self._flag_assembly(context.episode)
        return self._reload(scene_id)

    def generate_image(self, scene_id: str) -> GenerationRequest:
        context = self._get_idle_scene(scene_id)
        missing_names = self._find_missing_reference_names(context.scene)
        if missing_names:
            raise FilmConflictError(
                REFERENCES_FIRST_MESSAGE.format(names=NAME_SEPARATOR.join(missing_names))
            )
        return self._tools.media_queue.queue_scene_image(to_order_context(context))

    def edit_image(self, scene_id: str, prompt: str) -> GenerationRequest:
        context = self._get_idle_scene(scene_id)
        edit_prompt = to_bounded_text(prompt, EDIT_PROMPT_LIMIT, EDIT_PROMPT_MESSAGE)
        if context.scene.image_status is not MediaStatus.DONE:
            raise FilmConflictError(
                NO_IMAGE_TO_EDIT_MESSAGE.format(number=self._to_scene_number(context.scene))
            )
        return self._tools.media_queue.queue_scene_edit(to_order_context(context), edit_prompt)

    def generate_clip(self, scene_id: str) -> GenerationRequest:
        context = self._get_idle_scene(scene_id)
        if context.scene.image_status is not MediaStatus.DONE:
            raise FilmConflictError(
                NO_IMAGE_YET_MESSAGE.format(number=self._to_scene_number(context.scene))
            )
        return self._tools.media_queue.queue_scene_clip(to_order_context(context))

    def generate_narration(self, scene_id: str) -> GenerationRequest:
        context = self._get_idle_scene(scene_id)
        if not (context.scene.narrator_text or "").strip():
            raise FilmConflictError(
                NO_NARRATION_TEXT_MESSAGE.format(number=self._to_scene_number(context.scene))
            )
        voice = self._get_narrator_voice(context.project)
        return self._tools.media_queue.queue_narration(to_order_context(context), voice)

    def _get_idle_scene(self, scene_id: str) -> SceneContext:
        context = self._tools.access.get_editable_scene(scene_id)
        if self._tools.repository.find_open_requests_for_scene(scene_id):
            raise FilmConflictError(
                SCENE_GENERATION_RUNNING_MESSAGE.format(number=self._to_scene_number(context.scene))
            )
        return context

    def _get_narrator_voice(self, project: FilmProject) -> VoiceTemplate:
        voice_id = project.narrator_voice_id
        voice = None if voice_id is None else self._tools.repository.find_voice(voice_id)
        if voice is None:
            raise FilmConflictError(NO_NARRATOR_MESSAGE)
        return voice

    def _find_missing_reference_names(self, scene: Scene) -> list[str]:
        characters_by_id = self._tools.repository.find_characters_by_ids(scene.character_ids)
        return [
            characters_by_id[character_id].name
            for character_id in scene.character_ids
            if character_id in characters_by_id
            and characters_by_id[character_id].reference_status is not MediaStatus.DONE
        ]

    def _to_scene_values(self, context: SceneContext, changes: Mapping[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        if "image_prompt" in changes:
            values["image_prompt"] = to_valid_image_prompt(changes["image_prompt"])
        if "video_prompt" in changes:
            values["video_prompt"] = to_valid_video_prompt(changes["video_prompt"])
        if "clip_duration_s" in changes:
            values["clip_duration_s"] = to_valid_scene_clip_duration(changes["clip_duration_s"])
        if "character_ids" in changes:
            values["character_ids"] = self._to_cast_ids(
                context.project, changes["character_ids"] or []
            )
        return values

    def _to_new_position(self, context: SceneContext, changes: Mapping[str, Any]) -> int | None:
        position = changes.get("position")
        if position is None:
            return None
        valid_position = to_valid_position(position, self._count_scenes(context.scene.part_id))
        return None if valid_position == context.scene.position else valid_position

    def _to_cast_ids(self, project: FilmProject, character_ids: Sequence[str]) -> list[str]:
        if not character_ids:
            return []
        linked_ids = [
            character.id for character in self._tools.repository.find_project_characters(project.id)
        ]
        return to_valid_character_ids(character_ids, linked_ids)

    def _count_scenes(self, part_id: str) -> int:
        return self._tools.repository.count_scenes_by_part([part_id]).get(part_id, 0)

    def _to_scene_number(self, scene: Scene) -> int:
        part = self._tools.repository.find_part(scene.part_id)
        earlier_count = 0 if part is None else self._tools.repository.count_scenes_before_part(part)
        return earlier_count + scene.position + 1

    def _ensure_trimmable(self, scene: Scene, changes: Mapping[str, Any]) -> None:
        is_trim_change = any(field in changes for field in TRIM_FIELDS)
        if is_trim_change and scene.clip_status is not MediaStatus.DONE:
            raise FilmConflictError(NO_CLIP_YET_MESSAGE.format(number=self._to_scene_number(scene)))

    def _flag_assembly(self, episode: Episode) -> None:
        if episode.status is EpisodeStatus.DONE:
            self._tools.repository.update_episode(episode.id, {"needs_assembly": True})

    def _reload(self, scene_id: str) -> Scene:
        scene = self._tools.repository.find_scene(scene_id)
        if scene is None:
            raise SceneNotFoundError(scene_id)
        return scene


def to_narration_values(scene: Scene, changes: Mapping[str, Any]) -> dict[str, Any]:
    if "narrator_text" not in changes:
        return {}
    narrator_text = to_valid_narration(changes["narrator_text"])
    if narrator_text == scene.narrator_text:
        return {}
    return {"narrator_text": narrator_text, **NARRATION_RESET}


def to_trim_values(scene: Scene, changes: Mapping[str, Any]) -> dict[str, Any]:
    if not any(field in changes for field in TRIM_FIELDS):
        return {}
    start_ms = changes.get("trim_start_ms", scene.trim_start_ms)
    trim = TrimRange(
        start_ms=DEFAULT_TRIM_START_MS if start_ms is None else start_ms,
        end_ms=changes.get("trim_end_ms", scene.trim_end_ms),
        clip_duration_ms=scene.clip_duration_ms or 0,
    )
    ensure_valid_trim(trim)
    return {"trim_start_ms": trim.start_ms, "trim_end_ms": trim.end_ms}


def is_reset_or_trim(scene: Scene, values: Mapping[str, Any]) -> bool:
    is_trim_change = any(
        field in values and values[field] != getattr(scene, field) for field in TRIM_FIELDS
    )
    return is_trim_change or "narration_status" in values
