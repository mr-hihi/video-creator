from dataclasses import dataclass, fields

from app.modules.film_clones.clone_access import CloneAccess, is_failed_at, is_waiting_at
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_generation import CloneImageQueue
from app.modules.film_clones.clone_replies import (
    DESCRIPTION_LIMIT,
    DIALOGUE_LIMIT,
    IMAGE_PROMPT_LIMIT,
    NAME_LIMIT,
    ORIGIN_LIMIT,
)
from app.modules.film_clones.clone_steps import current_name
from app.modules.film_clones.errors import CloneConflictError, InvalidCloneRequestError
from app.modules.film_clones.models import (
    AssetKind,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.repository import LOCALIZED_FIELDS_CLEARED, FilmCloneRepository
from app.modules.media_generation.models import GenerationRequest

NAME_LENGTH_MESSAGE = f"Asset name must be 1-{NAME_LIMIT} characters"
DESCRIPTION_LENGTH_MESSAGE = f"Description must be 1-{DESCRIPTION_LIMIT} characters"
ORIGIN_LENGTH_MESSAGE = f"Culture and period must be 1-{ORIGIN_LIMIT} characters"
DIALOGUE_LENGTH_MESSAGE = f"Dialogue must be at most {DIALOGUE_LIMIT} characters"
IMAGE_PROMPT_LENGTH_MESSAGE = f"Image prompt must be 1-{IMAGE_PROMPT_LIMIT} characters"


@dataclass(frozen=True)
class OriginalAssetChanges:
    name: str | None = None
    kind: AssetKind | None = None
    description: str | None = None
    culture: str | None = None
    period: str | None = None

    @property
    def is_empty(self) -> bool:
        return all(getattr(self, field.name) is None for field in fields(self))


@dataclass(frozen=True)
class LocalizedAssetChanges:
    changed: bool | None = None
    localized_name: str | None = None
    localized_description: str | None = None


@dataclass(frozen=True)
class SceneChanges:
    description: str | None = None
    dialogue: str | None = None
    image_prompt: str | None = None


@dataclass(frozen=True)
class CloneEditingTools:
    repository: FilmCloneRepository
    files: CloneFiles
    image_queue: CloneImageQueue


class CloneEditingService:
    def __init__(self, tools: CloneEditingTools, access: CloneAccess):
        self._repository = tools.repository
        self._files = tools.files
        self._image_queue = tools.image_queue
        self._access = access

    def update_original_asset(self, asset_id: str, changes: OriginalAssetChanges) -> CloneAsset:
        asset = self._access.get_asset(asset_id)
        self._ensure_before_localization(self._access.get_clone(asset.clone_id))
        values = {}
        if changes.name is not None:
            values["name"] = self._to_unique_name(asset, changes.name)
        if changes.kind is not None:
            values["kind"] = changes.kind
        if changes.description is not None:
            values["description"] = to_bounded_text(
                changes.description, DESCRIPTION_LIMIT, DESCRIPTION_LENGTH_MESSAGE
            )
        for field_name in ("culture", "period"):
            if getattr(changes, field_name) is not None:
                values[field_name] = to_bounded_text(
                    getattr(changes, field_name), ORIGIN_LIMIT, ORIGIN_LENGTH_MESSAGE
                )
        self._repository.update_asset(asset_id, values)
        return self._access.get_asset(asset_id)

    def update_localized_asset(self, asset_id: str, changes: LocalizedAssetChanges) -> CloneAsset:
        asset = self._access.get_asset(asset_id)
        self._ensure_reviewing(self._access.get_clone(asset.clone_id))
        self._ensure_reference_idle(asset)
        if changes.changed is False:
            self._files.delete(asset.reference_path)
            self._repository.update_asset(asset_id, LOCALIZED_FIELDS_CLEARED)
            return self._access.get_asset(asset_id)
        if changes.changed is None and not asset.changed:
            raise CloneConflictError(f"Asset '{current_name(asset)}' is not changed")
        localized_description = (
            to_bounded_text(
                changes.localized_description, DESCRIPTION_LIMIT, DESCRIPTION_LENGTH_MESSAGE
            )
            if changes.localized_description is not None
            else asset.localized_description
        )
        if not localized_description:
            raise InvalidCloneRequestError("Describe the localized asset first")
        localized_name = (
            to_bounded_text(changes.localized_name, NAME_LIMIT, NAME_LENGTH_MESSAGE)
            if changes.localized_name is not None
            else asset.localized_name or asset.name
        )
        self._repository.update_asset(
            asset_id,
            {
                "changed": True,
                "localized_name": localized_name,
                "localized_description": localized_description,
            },
        )
        return self._access.get_asset(asset_id)

    def delete_asset(self, asset_id: str) -> None:
        asset = self._access.get_asset(asset_id)
        self._ensure_before_localization(self._access.get_clone(asset.clone_id))
        self._repository.delete_asset(asset)

    def generate_reference(self, asset_id: str) -> GenerationRequest:
        asset = self._access.get_asset(asset_id)
        clone = self._access.get_clone(asset.clone_id)
        self._ensure_reviewing(clone)
        if not asset.changed:
            raise CloneConflictError(f"Asset '{current_name(asset)}' is not changed")
        self._ensure_reference_idle(asset)
        return self._image_queue.queue_reference(clone, asset)

    def update_scene(self, scene_id: str, changes: SceneChanges) -> CloneScene:
        scene = self._access.get_scene(scene_id)
        self._ensure_scene_editable(scene)
        values = {}
        if changes.description is not None:
            values["description"] = to_bounded_text(
                changes.description, DESCRIPTION_LIMIT, DESCRIPTION_LENGTH_MESSAGE
            )
        if changes.dialogue is not None:
            dialogue = changes.dialogue.strip()
            if len(dialogue) > DIALOGUE_LIMIT:
                raise InvalidCloneRequestError(DIALOGUE_LENGTH_MESSAGE)
            values["dialogue"] = dialogue or None
        if changes.image_prompt is not None:
            values["image_prompt"] = to_bounded_text(
                changes.image_prompt, IMAGE_PROMPT_LIMIT, IMAGE_PROMPT_LENGTH_MESSAGE
            )
        self._repository.update_scene(scene_id, values)
        return self._access.get_scene(scene_id)

    def generate_scene_image(self, scene_id: str) -> GenerationRequest:
        scene = self._access.get_scene(scene_id)
        clone = self._ensure_scene_editable(scene)
        shot = self._repository.find_shot(scene.shot_id)
        if shot is None:
            raise CloneConflictError(f"Scene {scene.position + 1} has no shot")
        return self._image_queue.queue_scene_image(clone, scene, shot)

    def _ensure_before_localization(self, clone: FilmClone) -> None:
        if not is_waiting_at(clone, CloneStep.CHOOSING_LOCALIZATION):
            raise CloneConflictError("Assets can be edited only before localization")

    def _ensure_reviewing(self, clone: FilmClone) -> None:
        if not is_waiting_at(clone, CloneStep.REVIEWING):
            raise CloneConflictError("Localized fields can be edited only while reviewing")

    def _ensure_reference_idle(self, asset: CloneAsset) -> None:
        is_busy = any(
            request.clone_asset_id == asset.id
            for request in self._access.find_open_requests(asset.clone_id)
        )
        if is_busy:
            raise CloneConflictError(f"Asset '{current_name(asset)}' has generation running")

    def _ensure_scene_editable(self, scene: CloneScene) -> FilmClone:
        clone = self._access.get_clone(scene.clone_id)
        is_editable = clone.status is CloneStatus.DONE or is_failed_at(
            clone, {CloneStep.GENERATING_SCENE_IMAGES}
        )
        if not is_editable:
            raise CloneConflictError("Scenes can be edited once the script is written")
        is_busy = scene.image_status in (
            CloneImageStatus.QUEUED,
            CloneImageStatus.PROCESSING,
        ) or any(
            request.clone_scene_id == scene.id
            for request in self._access.find_open_requests(scene.clone_id)
        )
        if is_busy:
            raise CloneConflictError(f"Scene {scene.position + 1} has generation running")
        return clone

    def _to_unique_name(self, asset: CloneAsset, requested_name: str) -> str:
        name = to_bounded_text(requested_name, NAME_LIMIT, NAME_LENGTH_MESSAGE)
        is_taken = any(
            other.id != asset.id and other.name.casefold() == name.casefold()
            for other in self._repository.find_assets(asset.clone_id)
        )
        if is_taken:
            raise CloneConflictError(f"An asset named '{name}' already exists in this clone")
        return name


def to_bounded_text(value: str, limit: int, message: str) -> str:
    text = value.strip()
    if not 1 <= len(text) <= limit:
        raise InvalidCloneRequestError(message)
    return text
