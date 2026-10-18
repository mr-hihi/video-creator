from collections.abc import Callable
from dataclasses import dataclass

from app.modules.app_settings.service import AppSettingService
from app.modules.film_clones.clone_access import (
    LATER_STEPS,
    RESUMABLE_STEPS,
    CloneAccess,
    ensure_action_allowed,
    is_failed_at,
    is_waiting_at,
)
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_generation import CloneImageQueue
from app.modules.film_clones.clone_steps import (
    WRITING_SCRIPT_VALUES,
    CloneSceneImageCheck,
    current_name,
)
from app.modules.film_clones.errors import CloneConflictError
from app.modules.film_clones.localization_rules import (
    LocalizationChoices,
    find_assets_missing_reference,
    find_transcript_language,
    resolve_script_language,
    to_localization_values,
    validate_localization_choices,
)
from app.modules.film_clones.models import (
    CloneImageStatus,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.jobs.models import JobOutputKind
from app.modules.jobs.repository import JobRepository

REQUEUED_IMAGE_STATUSES = frozenset({CloneImageStatus.NONE, CloneImageStatus.FAILED})


@dataclass(frozen=True)
class CloneActionTools:
    repository: FilmCloneRepository
    job_repository: JobRepository
    files: CloneFiles
    app_setting_service: AppSettingService
    image_queue: CloneImageQueue
    scene_image_check: CloneSceneImageCheck
    notify_worker: Callable[[], None]


class CloneActionService:
    def __init__(self, tools: CloneActionTools, access: CloneAccess):
        self._tools = tools
        self._access = access

    def localize(self, clone_id: str, choices: LocalizationChoices) -> None:
        clone = self._access.get_clone(clone_id)
        ensure_action_allowed(
            "localize", clone, is_waiting_at(clone, CloneStep.CHOOSING_LOCALIZATION)
        )
        validate_localization_choices(choices)
        video_notes = self._tools.job_repository.find_outputs(clone.job_id).get(
            JobOutputKind.VIDEO_NOTES
        )
        script_language = resolve_script_language(
            self._tools.app_setting_service.get_script_language(),
            choices.target_country,
            find_transcript_language(video_notes),
        )
        self._tools.repository.update_clone(
            clone_id, to_localization_values(choices, script_language)
        )
        self._tools.notify_worker()

    def write_script(self, clone_id: str) -> None:
        clone = self._access.get_clone(clone_id)
        ensure_action_allowed("write-script", clone, is_waiting_at(clone, CloneStep.REVIEWING))
        missing_names = [
            current_name(asset)
            for asset in find_assets_missing_reference(self._tools.repository.find_assets(clone_id))
        ]
        if missing_names:
            raise CloneConflictError(f"Reference images missing for: {', '.join(missing_names)}")
        self._tools.repository.update_clone(clone_id, WRITING_SCRIPT_VALUES)
        self._tools.notify_worker()

    def resume(self, clone_id: str) -> None:
        clone = self._access.get_clone(clone_id)
        ensure_action_allowed("resume", clone, is_failed_at(clone, RESUMABLE_STEPS))
        self._tools.repository.update_clone(
            clone_id, {"status": CloneStatus.RUNNING, "error_message": None}
        )
        if clone.step is not CloneStep.GENERATING_SCENE_IMAGES:
            self._tools.notify_worker()
            return
        self._queue_unfinished_scene_images(clone)
        self._tools.scene_image_check.check(clone_id)

    def relocalize(self, clone_id: str) -> None:
        clone = self._access.get_clone(clone_id)
        is_allowed = (
            is_waiting_at(clone, CloneStep.REVIEWING)
            or clone.status is CloneStatus.DONE
            or is_failed_at(clone, LATER_STEPS)
        )
        ensure_action_allowed("relocalize", clone, is_allowed)
        if self._access.find_open_requests(clone_id):
            raise CloneConflictError(f"Film clone {clone_id} has image generation running")
        for scene in self._tools.repository.find_scenes(clone_id):
            self._tools.files.delete(scene.image_path)
        for asset in self._tools.repository.find_assets(clone_id):
            self._tools.files.delete(asset.reference_path)
        self._tools.repository.reset_localization(
            clone_id,
            {
                "status": CloneStatus.WAITING,
                "step": CloneStep.CHOOSING_LOCALIZATION,
                "should_run_automatically": False,
                "script_title": None,
                "logline": None,
                "error_message": None,
                "finished_at": None,
            },
        )

    def _queue_unfinished_scene_images(self, clone: FilmClone) -> None:
        shots_by_id = {shot.id: shot for shot in self._tools.repository.find_shots(clone.id)}
        refreshed_clone = self._access.get_clone(clone.id)
        for scene in self._tools.repository.find_scenes(clone.id):
            if scene.image_status in REQUEUED_IMAGE_STATUSES:
                self._tools.image_queue.queue_scene_image(
                    refreshed_clone, scene, shots_by_id[scene.shot_id]
                )
