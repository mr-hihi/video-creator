from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.app_settings.repository import AppSettingRepository
from app.modules.app_settings.service import AppSettingService
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.service import (
    GenerationOrder,
    GenerationService,
    GenerationTargetIds,
)
from app.modules.media_generation.targets import GenerationTarget
from app.modules.providers.provider_catalog import MediaFeature, MediaKind, ProviderId
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.service import ProviderSettingService, ProviderSettingTools


def build_service():
    repository = MagicMock(spec=GenerationRequestRepository)
    repository.add.side_effect = lambda request: request
    provider_service = MagicMock(spec=ProviderSettingService)
    provider_service.pick_provider.return_value = ProviderId.FAL.value
    target = MagicMock(spec=GenerationTarget)
    notify_worker = MagicMock()
    service = GenerationService(
        repository,
        provider_service,
        {kind: target for kind in GenerationKind},
        notify_worker,
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        provider_service=provider_service,
        target=target,
        notify_worker=notify_worker,
    )


def build_order(kind: GenerationKind, media_kind: MediaKind) -> GenerationOrder:
    return GenerationOrder(
        kind=kind,
        media_kind=media_kind,
        prompt="A harbour at dawn",
        target_ids=GenerationTargetIds(),
    )


def build_request(request_id: str, status: GenerationStatus) -> GenerationRequest:
    return GenerationRequest(
        id=request_id, kind=GenerationKind.CLONE_REFERENCE_IMAGE, status=status
    )


@pytest.fixture
def queued():
    parts = build_service()
    request = parts.service.queue(
        GenerationOrder(
            kind=GenerationKind.CLONE_REFERENCE_IMAGE,
            media_kind=MediaKind.IMAGE,
            prompt="A fisherman in a straw hat",
            target_ids=GenerationTargetIds(clone_id="clone-1", clone_asset_id="asset-1"),
            params={"aspect": "1:1"},
        )
    )
    return SimpleNamespace(request=request, parts=parts)


@pytest.fixture(
    params=[
        (GenerationKind.CLONE_REFERENCE_IMAGE, MediaKind.IMAGE, MediaFeature.FILM_CLONE),
        (GenerationKind.CLONE_SCENE_IMAGE, MediaKind.EDIT_IMAGE, MediaFeature.FILM_CLONE),
        (GenerationKind.CHARACTER_IMAGE, MediaKind.IMAGE, MediaFeature.FILM_STUDIO),
        (GenerationKind.SCENE_IMAGE, MediaKind.IMAGE, MediaFeature.FILM_STUDIO),
        (GenerationKind.EDIT_IMAGE, MediaKind.EDIT_IMAGE, MediaFeature.FILM_STUDIO),
        (GenerationKind.THUMBNAIL, MediaKind.IMAGE, MediaFeature.FILM_STUDIO),
        (GenerationKind.SCENE_CLIP, MediaKind.VIDEO, MediaFeature.FILM_STUDIO),
        (GenerationKind.NARRATION, MediaKind.SPEECH, MediaFeature.FILM_STUDIO),
    ]
)
def picked_feature(request):
    kind, media_kind, expected_feature = request.param
    parts = build_service()
    parts.service.queue(build_order(kind, media_kind))
    return SimpleNamespace(
        pick_call=parts.provider_service.pick_provider.call_args,
        expected=(media_kind, expected_feature),
    )


def build_routed_service(stored_settings: dict, stored_routes: dict) -> GenerationService:
    app_settings_repository = MagicMock(spec=AppSettingRepository)
    app_settings_repository.find_values.return_value = stored_settings
    provider_repository = MagicMock(spec=ProviderRepository)
    provider_repository.find_route_provider_ids.return_value = stored_routes
    provider_service = ProviderSettingService(
        provider_repository,
        ProviderSettingTools(
            secret_box=MagicMock(),
            connection_tester=MagicMock(),
            extension=MagicMock(),
            queue_counter=MagicMock(),
            claude_cli_check=MagicMock(),
            chosen_provider_settings=AppSettingService(app_settings_repository),
        ),
    )
    repository = MagicMock(spec=GenerationRequestRepository)
    repository.add.side_effect = lambda request: request
    return GenerationService(
        repository, provider_service, {kind: MagicMock() for kind in GenerationKind}, MagicMock()
    )


def queue_providers(service: GenerationService, orders) -> list[str]:
    return [service.queue(build_order(kind, media_kind)).provider for kind, media_kind in orders]


SCENE_IMAGE_ORDER = (GenerationKind.SCENE_IMAGE, MediaKind.IMAGE)
CLONE_SCENE_IMAGE_ORDER = (GenerationKind.CLONE_SCENE_IMAGE, MediaKind.EDIT_IMAGE)
SCENE_CLIP_ORDER = (GenerationKind.SCENE_CLIP, MediaKind.VIDEO)
NARRATION_ORDER = (GenerationKind.NARRATION, MediaKind.SPEECH)
MUSIC_ORDER = (GenerationKind.MUSIC, MediaKind.MUSIC)


@pytest.fixture
def providers_per_step():
    stored_settings = {
        "filmStudioImageProvider": None,
        "filmStudioClipProvider": None,
        "filmCloneImageProvider": None,
    }
    stored_routes = {
        "image": "fal",
        "video": "google_flow",
        "speech": "omnivoice",
        "music": "ace_step",
    }
    service = build_routed_service(stored_settings, stored_routes)
    first_providers = queue_providers(
        service,
        [
            SCENE_IMAGE_ORDER,
            CLONE_SCENE_IMAGE_ORDER,
            SCENE_CLIP_ORDER,
            NARRATION_ORDER,
            MUSIC_ORDER,
        ],
    )
    stored_settings["filmStudioImageProvider"] = "sd_webui"
    second_providers = queue_providers(service, [SCENE_IMAGE_ORDER, CLONE_SCENE_IMAGE_ORDER])
    stored_settings.update(
        filmStudioImageProvider=None,
        filmStudioClipProvider="replicate",
        filmCloneImageProvider="google",
    )
    stored_routes.update(image="openai", speech="google")
    third_providers = queue_providers(
        service, [SCENE_IMAGE_ORDER, CLONE_SCENE_IMAGE_ORDER, SCENE_CLIP_ORDER, NARRATION_ORDER]
    )
    return (first_providers, second_providers, third_providers)


@pytest.fixture
def cancelled():
    parts = build_service()
    parts.service.cancel_queued(
        [
            build_request("queued-1", GenerationStatus.QUEUED),
            build_request("processing-1", GenerationStatus.PROCESSING),
        ]
    )
    return parts


def test_queue_stores_a_queued_request_on_the_picked_provider(queued):
    assert queued.request.status is GenerationStatus.QUEUED
    assert queued.request.provider == "fal"
    assert queued.request.attempts == 0
    assert queued.request.clone_id == "clone-1"
    assert queued.request.clone_asset_id == "asset-1"
    assert queued.request.project_id is None
    assert queued.request.params == {"aspect": "1:1"}
    queued.parts.provider_service.pick_provider.assert_called_once_with(
        MediaKind.IMAGE, MediaFeature.FILM_CLONE
    )


def test_queue_picks_the_provider_for_the_feature_of_the_kind(picked_feature):
    assert picked_feature.pick_call.args == picked_feature.expected


def test_each_request_gets_the_provider_its_feature_setting_or_route_names(providers_per_step):
    assert providers_per_step == (
        ["fal", "fal", "google_flow", "omnivoice", "ace_step"],
        ["sd_webui", "fal"],
        ["openai", "google", "replicate", "google"],
    )


def test_queue_marks_the_target_and_wakes_the_worker(queued):
    queued.parts.target.mark_queued.assert_called_once_with(queued.request)
    queued.parts.notify_worker.assert_called_once_with()


def test_cancel_queued_cancels_only_queued_requests(cancelled):
    cancelled.repository.cancel_queued.assert_called_once_with(["queued-1"])
    assert cancelled.target.mark_cancelled.call_count == 1
    assert cancelled.target.mark_cancelled.call_args.args[0].id == "queued-1"
