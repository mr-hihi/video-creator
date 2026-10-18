from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.modules.media_generation.models import (
    CLONE_GENERATION_KINDS,
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.targets import GenerationTarget
from app.modules.providers.provider_catalog import MediaFeature, MediaKind
from app.modules.providers.service import ProviderSettingService


@dataclass(frozen=True)
class GenerationTargetIds:
    project_id: str | None = None
    clone_id: str | None = None
    episode_id: str | None = None
    scene_id: str | None = None
    character_id: str | None = None
    clone_asset_id: str | None = None
    clone_scene_id: str | None = None


@dataclass(frozen=True)
class GenerationOrder:
    kind: GenerationKind
    media_kind: MediaKind
    prompt: str
    target_ids: GenerationTargetIds
    input_paths: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)


class GenerationService:
    def __init__(
        self,
        repository: GenerationRequestRepository,
        provider_service: ProviderSettingService,
        targets_by_kind: Mapping[GenerationKind, GenerationTarget],
        notify_worker: Callable[[], None],
    ):
        self._repository = repository
        self._provider_service = provider_service
        self._targets_by_kind = targets_by_kind
        self._notify_worker = notify_worker

    def queue(self, order: GenerationOrder) -> GenerationRequest:
        request = self._repository.add(
            GenerationRequest(
                id=str(uuid4()),
                kind=order.kind,
                media_kind=order.media_kind,
                **vars(order.target_ids),
                provider=self._provider_service.pick_provider(
                    order.media_kind, _to_media_feature(order.kind)
                ),
                prompt=order.prompt,
                input_paths=order.input_paths,
                params=order.params,
                status=GenerationStatus.QUEUED,
                attempts=0,
            )
        )
        self._targets_by_kind[order.kind].mark_queued(request)
        self._notify_worker()
        return request

    def find_open_for_clone(self, clone_id: str) -> list[GenerationRequest]:
        return self._repository.find_open_for_clone(clone_id)

    def find_clone_ids_with_open_requests(self, clone_ids: Collection[str]) -> set[str]:
        return self._repository.find_clone_ids_with_open_requests(clone_ids)

    def cancel_queued(self, requests: Collection[GenerationRequest]) -> None:
        queued_requests = [
            request for request in requests if request.status is GenerationStatus.QUEUED
        ]
        self._repository.cancel_queued([request.id for request in queued_requests])
        for request in queued_requests:
            self._targets_by_kind[request.kind].mark_cancelled(request)

    def delete_for_clone(self, clone_id: str) -> None:
        self._repository.delete_for_clone(clone_id)


def _to_media_feature(kind: GenerationKind) -> MediaFeature:
    if kind in CLONE_GENERATION_KINDS:
        return MediaFeature.FILM_CLONE
    return MediaFeature.FILM_STUDIO
