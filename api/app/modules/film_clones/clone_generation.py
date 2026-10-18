from collections.abc import Callable
from pathlib import Path

from app.modules.film_clones.clone_catalog import (
    CAMERA_ANGLE_LABELS,
    COMPOSITIONS_BY_KIND,
    SHOT_SIZE_LABELS,
)
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.models import (
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.jobs.storage import JobStorage
from app.modules.media_generation.models import GenerationKind, GenerationRequest
from app.modules.media_generation.service import (
    GenerationOrder,
    GenerationService,
    GenerationTargetIds,
)
from app.modules.media_generation.task_builder import ASPECT_PARAM, SOURCE_IMAGE_KEY
from app.modules.providers.provider_catalog import MediaKind


class CloneImageQueue:
    def __init__(self, generation_service: GenerationService, job_storage: JobStorage):
        self._generation_service = generation_service
        self._job_storage = job_storage

    def queue_reference(self, clone: FilmClone, asset: CloneAsset) -> GenerationRequest:
        composition = COMPOSITIONS_BY_KIND[asset.kind]
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.CLONE_REFERENCE_IMAGE,
                media_kind=MediaKind.IMAGE,
                prompt=f"Reference image of {asset.localized_description}. {composition.text}",
                target_ids=GenerationTargetIds(clone_id=clone.id, clone_asset_id=asset.id),
                params={ASPECT_PARAM: composition.aspect.value},
            )
        )

    def queue_scene_image(
        self, clone: FilmClone, scene: CloneScene, shot: CloneShot
    ) -> GenerationRequest:
        frame_path = self._job_storage.output_dir(clone.job_id) / shot.frame
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.CLONE_SCENE_IMAGE,
                media_kind=MediaKind.EDIT_IMAGE,
                prompt=build_scene_image_prompt(scene, shot),
                target_ids=GenerationTargetIds(clone_id=clone.id, clone_scene_id=scene.id),
                input_paths={SOURCE_IMAGE_KEY: str(frame_path)},
                params={ASPECT_PARAM: clone.aspect.value if clone.aspect else None},
            )
        )


def build_scene_image_prompt(scene: CloneScene, shot: CloneShot) -> str:
    shot_labels = [
        label
        for label in (
            SHOT_SIZE_LABELS.get(shot.shot_size) if shot.shot_size else None,
            CAMERA_ANGLE_LABELS.get(shot.camera_angle) if shot.camera_angle else None,
        )
        if label
    ]
    if not shot_labels:
        return scene.image_prompt
    return f"{scene.image_prompt} Shot: {', '.join(shot_labels)}."


class CloneReferenceTarget:
    def __init__(
        self,
        repository: FilmCloneRepository,
        files: CloneFiles,
        check_references: Callable[[str], None],
    ):
        self._repository = repository
        self._files = files
        self._check_references = check_references

    def mark_queued(self, request: GenerationRequest) -> None:
        self._set_status(request, CloneImageStatus.QUEUED)

    def is_ready(self, request: GenerationRequest) -> bool:
        return True

    def mark_processing(self, request: GenerationRequest) -> None:
        self._set_status(request, CloneImageStatus.PROCESSING)

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._files.reference_path(
            request.clone_id or "", request.clone_asset_id or "", file_extension
        )

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._files.keep_only(file_path)
        self._repository.update_asset(
            request.clone_asset_id or "",
            {
                "reference_status": CloneImageStatus.DONE,
                "reference_path": self._files.to_relative(file_path),
                "reference_error": None,
            },
        )

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        asset = self._repository.find_asset(request.clone_asset_id or "")
        if asset is None:
            return
        status = CloneImageStatus.DONE if asset.reference_path else CloneImageStatus.FAILED
        self._repository.update_asset(
            asset.id, {"reference_status": status, "reference_error": error_message}
        )

    def mark_cancelled(self, request: GenerationRequest) -> None:
        asset = self._repository.find_asset(request.clone_asset_id or "")
        if asset is None:
            return
        status = CloneImageStatus.DONE if asset.reference_path else CloneImageStatus.NONE
        self._repository.update_asset(asset.id, {"reference_status": status})

    def on_final(self, request: GenerationRequest) -> None:
        if request.clone_id is not None:
            self._check_references(request.clone_id)

    def _set_status(self, request: GenerationRequest, status: CloneImageStatus) -> None:
        self._repository.update_asset(request.clone_asset_id or "", {"reference_status": status})


class CloneSceneImageTarget:
    def __init__(
        self,
        repository: FilmCloneRepository,
        files: CloneFiles,
        check_scene_images: Callable[[str], None],
    ):
        self._repository = repository
        self._files = files
        self._check_scene_images = check_scene_images

    def mark_queued(self, request: GenerationRequest) -> None:
        self._set_status(request, CloneImageStatus.QUEUED)

    def is_ready(self, request: GenerationRequest) -> bool:
        return True

    def mark_processing(self, request: GenerationRequest) -> None:
        self._set_status(request, CloneImageStatus.PROCESSING)

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._files.scene_path(
            request.clone_id or "", request.clone_scene_id or "", file_extension
        )

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._files.keep_only(file_path)
        self._repository.update_scene(
            request.clone_scene_id or "",
            {
                "image_status": CloneImageStatus.DONE,
                "image_path": self._files.to_relative(file_path),
                "image_error": None,
            },
        )

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        scene = self._repository.find_scene(request.clone_scene_id or "")
        if scene is None:
            return
        status = CloneImageStatus.DONE if scene.image_path else CloneImageStatus.FAILED
        self._repository.update_scene(
            scene.id, {"image_status": status, "image_error": error_message}
        )

    def mark_cancelled(self, request: GenerationRequest) -> None:
        scene = self._repository.find_scene(request.clone_scene_id or "")
        if scene is None:
            return
        status = CloneImageStatus.DONE if scene.image_path else CloneImageStatus.NONE
        self._repository.update_scene(scene.id, {"image_status": status})

    def on_final(self, request: GenerationRequest) -> None:
        if request.clone_id is not None:
            self._check_scene_images(request.clone_id)

    def _set_status(self, request: GenerationRequest, status: CloneImageStatus) -> None:
        self._repository.update_scene(request.clone_scene_id or "", {"image_status": status})
