from collections.abc import Collection

from app.modules.film_clones.errors import (
    CloneActionNotAllowedError,
    CloneAssetNotFoundError,
    CloneSceneNotFoundError,
    FilmCloneNotFoundError,
)
from app.modules.film_clones.models import (
    CloneAsset,
    CloneScene,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.media_generation.models import GenerationRequest
from app.modules.media_generation.service import GenerationService

LATER_STEPS = frozenset(
    {CloneStep.PROPOSING, CloneStep.WRITING_SCRIPT, CloneStep.GENERATING_SCENE_IMAGES}
)
RESUMABLE_STEPS = LATER_STEPS | {CloneStep.EXTRACTING_ASSETS, CloneStep.ANALYZING_SHOTS}


class CloneAccess:
    def __init__(self, repository: FilmCloneRepository, generation_service: GenerationService):
        self._repository = repository
        self._generation_service = generation_service

    def get_clone(self, clone_id: str) -> FilmClone:
        clone = self._repository.find_by_id(clone_id)
        if clone is None:
            raise FilmCloneNotFoundError(clone_id)
        return clone

    def get_asset(self, asset_id: str) -> CloneAsset:
        asset = self._repository.find_asset(asset_id)
        if asset is None:
            raise CloneAssetNotFoundError(asset_id)
        return asset

    def get_scene(self, scene_id: str) -> CloneScene:
        scene = self._repository.find_scene(scene_id)
        if scene is None:
            raise CloneSceneNotFoundError(scene_id)
        return scene

    def find_open_requests(self, clone_id: str) -> list[GenerationRequest]:
        return self._generation_service.find_open_for_clone(clone_id)


def ensure_action_allowed(action: str, clone: FilmClone, is_allowed: bool) -> None:
    if not is_allowed:
        raise CloneActionNotAllowedError(action, clone.id, clone.status.value, clone.step.value)


def is_waiting_at(clone: FilmClone, step: CloneStep) -> bool:
    return clone.status is CloneStatus.WAITING and clone.step is step


def is_failed_at(clone: FilmClone, steps: Collection[CloneStep]) -> bool:
    return clone.status is CloneStatus.FAILED and clone.step in steps
