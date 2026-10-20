from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.app_settings.ai_model_service import (
    AiModelSettingService,
    AiModelSettingsUpdate,
    AiModelSettingsView,
    AiModelSettingTools,
)
from app.modules.app_settings.errors import InvalidSettingError
from app.modules.app_settings.repository import AiModelSettingsSave, AppSettingRepository
from app.modules.app_settings.service import AppSettingService
from app.modules.providers.claude_cli_check import ClaudeCliCheck, ClaudeCliStatus
from app.modules.providers.errors import InvalidProviderSettingError, ProviderNotFoundError
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.models import Provider
from app.modules.providers.provider_catalog import PROVIDER_SPECS
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.secret_box import SecretBox
from app.modules.providers.service import (
    ProviderSettingService,
    ProviderSettingsView,
    ProviderSettingTools,
)

GEMINI_FLASH = {"provider": "google", "model": "gemini-3.8-flash"}
GEMINI_ARGON = {"provider": "google", "model": "gemini-4-argon"}
DEFAULT_ROUTES = {
    "image": "google_flow",
    "video": "google_flow",
    "speech": "omnivoice",
    "music": "ace_step",
}
NO_STEP_MODELS = {
    "moments": None,
    "audio": None,
    "filmAnalysis": None,
    "filmScript": None,
    "filmClone": None,
}


def build_provider_service(
    setting_service: AppSettingService, stored_routes: dict, providers_by_id: dict
) -> ProviderSettingService:
    provider_repository = MagicMock(spec=ProviderRepository)
    provider_repository.find_all.side_effect = lambda: list(providers_by_id.values())
    provider_repository.find_by_id.side_effect = providers_by_id.get
    provider_repository.find_route_provider_ids.return_value = stored_routes
    cli_check = MagicMock(spec=ClaudeCliCheck)
    cli_check.get_recent_status.return_value = ClaudeCliStatus.SIGNED_IN
    queue_counter = MagicMock()
    queue_counter.count_by_provider.return_value = {}
    return ProviderSettingService(
        provider_repository,
        ProviderSettingTools(
            secret_box=SecretBox("test-secret"),
            connection_tester=MagicMock(),
            extension=FlowExtensionBridge(),
            queue_counter=queue_counter,
            claude_cli_check=cli_check,
            chosen_provider_settings=setting_service,
        ),
    )


def build_parts():
    stored_settings: dict = {}
    stored_routes: dict = {}
    providers_by_id = {
        spec.id.value: Provider(id=spec.id.value, models={}, max_concurrent=1, min_interval_s=0)
        for spec in PROVIDER_SPECS
    }
    providers_by_id["google_flow"].models = {"video": "veo_3_1_i2v_lite"}

    def save_into_the_stored_rows(save: AiModelSettingsSave) -> None:
        stored_settings.update(save.setting_values)
        stored_routes.update(save.provider_ids_by_route)
        for provider_id, models in save.models_by_provider_id.items():
            providers_by_id[provider_id].models = models

    setting_repository = MagicMock(spec=AppSettingRepository)
    setting_repository.find_values.return_value = stored_settings
    setting_repository.save_ai_model_settings.side_effect = save_into_the_stored_rows
    setting_service = AppSettingService(setting_repository)
    service = AiModelSettingService(
        AiModelSettingTools(
            repository=setting_repository,
            setting_service=setting_service,
            provider_service=build_provider_service(
                setting_service, stored_routes, providers_by_id
            ),
        )
    )
    return SimpleNamespace(service=service, setting_repository=setting_repository)


def build_update(setting_values=None, routes=None, models=None) -> AiModelSettingsUpdate:
    return AiModelSettingsUpdate(
        setting_values=setting_values or {},
        provider_ids_by_route=routes or {},
        model_ids_by_provider=models or {},
    )


@pytest.fixture
def saved_settings():
    parts = build_parts()
    view = parts.service.update_ai_model_settings(
        build_update(
            {
                "aiModel": GEMINI_FLASH,
                "aiStepModels": {"moments": GEMINI_ARGON, "audio": GEMINI_FLASH},
                "filmAnalysisInputMode": "full_video",
            },
            {"image": "sd_webui", "video": "replicate"},
            {"replicate": {"video": "alibaba/wan-3"}, "google_flow": {"image": "NARWHAL"}},
        )
    )
    providers_by_id = {provider.spec.id.value: provider for provider in view.providers.providers}
    return SimpleNamespace(
        view=view, providers_by_id=providers_by_id, repository=parts.setting_repository
    )


@pytest.fixture(
    params=[
        ({"setting_values": {"scriptLanguage": "ja"}}, "Unknown setting 'scriptLanguage'"),
        (
            {"setting_values": {"filmCloneInputMode": "whole_video"}},
            "Unknown setting 'filmCloneInputMode'",
        ),
        ({"setting_values": {"theme": "dark"}}, "Unknown setting 'theme'"),
        (
            {"setting_values": {"aiModel": {"provider": "google", "model": "gpt-6-astra"}}},
            "Invalid value for 'aiModel'",
        ),
        (
            {"setting_values": {"aiStepModels": {"subtitles": None}}},
            "Invalid value for 'aiStepModels'",
        ),
        (
            {"setting_values": {"filmAnalysisInputMode": "frames"}},
            "Invalid value for 'filmAnalysisInputMode'",
        ),
        (
            {"setting_values": {"inputMode": "full_video"}},
            "Invalid value for 'inputMode'",
        ),
        (
            {
                "setting_values": {"inputMode": "frames"},
                "routes": {"image": "fal"},
                "models": {"fal": {"image": "no-such-model"}},
            },
            "Invalid value for 'inputMode'",
        ),
    ]
)
def rejected_settings(request):
    update_fields, expected = request.param
    parts = build_parts()
    with pytest.raises(InvalidSettingError) as caught:
        parts.service.update_ai_model_settings(build_update(**update_fields))
    return SimpleNamespace(
        message=str(caught.value), expected=expected, repository=parts.setting_repository
    )


@pytest.fixture(
    params=[
        (
            {
                "setting_values": {"inputMode": "whole_video"},
                "routes": {"image": "fal", "video": "openai"},
            },
            "OpenAI cannot serve video",
        ),
        (
            {
                "setting_values": {"filmAnalysisInputMode": "full_video"},
                "routes": {"video": "openai"},
            },
            "OpenAI cannot serve video",
        ),
        ({"routes": {"apiImage": "google"}}, "Unknown route 'apiImage'"),
        ({"routes": {"video": "sd_webui"}}, "Stable Diffusion WebUI / Forge cannot serve video"),
        (
            {
                "setting_values": {"inputMode": "whole_video"},
                "routes": {"image": "fal"},
                "models": {"fal": {"image": "no-such-model"}},
            },
            "Unknown model 'no-such-model' for fal.ai image",
        ),
        ({"models": {"openai": {"video": "sora-2"}}}, "models.video does not apply to OpenAI"),
        (
            {"models": {"sd_webui": {"image": "flux1-dev"}}},
            "models does not apply to Stable Diffusion WebUI / Forge",
        ),
        (
            {"models": {"google": {"analysis": "gemini-4-argon"}}},
            "models.analysis does not apply to Google AI (Gemini, Veo)",
        ),
    ]
)
def rejected_providers(request):
    update_fields, expected = request.param
    parts = build_parts()
    with pytest.raises(InvalidProviderSettingError) as caught:
        parts.service.update_ai_model_settings(build_update(**update_fields))
    return SimpleNamespace(
        message=str(caught.value), expected=expected, repository=parts.setting_repository
    )


@pytest.fixture
def unknown_provider():
    parts = build_parts()
    with pytest.raises(ProviderNotFoundError) as caught:
        parts.service.update_ai_model_settings(
            build_update(
                {"inputMode": "whole_video"},
                {"image": "fal"},
                {"replicate": {"video": "alibaba/wan-3"}, "midjourney": {"image": "v7"}},
            )
        )
    return SimpleNamespace(message=str(caught.value), repository=parts.setting_repository)


def test_ai_model_settings_are_saved_together(saved_settings):
    saved_settings.repository.save_ai_model_settings.assert_called_once_with(
        AiModelSettingsSave(
            setting_values={
                "aiModel": GEMINI_FLASH,
                "aiStepModels": {
                    **NO_STEP_MODELS,
                    "moments": GEMINI_ARGON,
                    "audio": GEMINI_FLASH,
                },
                "filmAnalysisInputMode": "full_video",
            },
            provider_ids_by_route={"image": "sd_webui", "video": "replicate"},
            models_by_provider_id={
                "replicate": {"video": "alibaba/wan-3"},
                "google_flow": {"video": "veo_3_1_i2v_lite", "image": "NARWHAL"},
            },
        )
    )


def test_the_answer_holds_the_saved_settings_and_providers(saved_settings):
    assert saved_settings.view.settings["aiModel"] == GEMINI_FLASH
    assert saved_settings.view.settings["inputMode"] == "subtitles"
    assert saved_settings.view.settings["filmAnalysisInputMode"] == "full_video"
    assert saved_settings.view.providers.provider_ids_by_route == {
        **DEFAULT_ROUTES,
        "image": "sd_webui",
        "video": "replicate",
    }
    assert saved_settings.providers_by_id["replicate"].models == {"video": "alibaba/wan-3"}
    assert saved_settings.providers_by_id["google_flow"].models == {
        "video": "veo_3_1_i2v_lite",
        "image": "NARWHAL",
    }


def test_a_setting_rule_failure_saves_nothing(rejected_settings):
    assert rejected_settings.message == rejected_settings.expected
    rejected_settings.repository.save_ai_model_settings.assert_not_called()


def test_a_route_or_model_rule_failure_saves_nothing(rejected_providers):
    assert rejected_providers.message == rejected_providers.expected
    rejected_providers.repository.save_ai_model_settings.assert_not_called()


def test_an_unknown_provider_saves_nothing(unknown_provider):
    assert unknown_provider.message == "Provider midjourney not found"
    unknown_provider.repository.save_ai_model_settings.assert_not_called()


@pytest.fixture
def mocked_service():
    service = MagicMock(spec=AiModelSettingService)
    service.update_ai_model_settings.return_value = AiModelSettingsView(
        settings={"inputMode": "whole_video"},
        providers=ProviderSettingsView(
            provider_ids_by_route=DEFAULT_ROUTES, providers=[], is_secret_key_set=False
        ),
    )
    return service


@pytest.fixture
def client(mocked_service):
    app = create_app()
    app.state.container = SimpleNamespace(ai_model_setting_service=mocked_service)
    return TestClient(app)


@pytest.fixture
def patch_response(client):
    return client.patch(
        "/settings/ai-models",
        json={
            "inputMode": "whole_video",
            "theme": "dark",
            "routes": {"image": "fal"},
            "models": {"fal": {"image": "fal-ai/nano-banana-pro"}},
        },
    )


@pytest.fixture
def empty_patch_response(client):
    return client.patch("/settings/ai-models", json={})


@pytest.fixture(params=[["whole_video"], {"routes": ["fal"]}, {"models": {"fal": "x"}}])
def malformed_patch_response(request, client):
    return client.patch("/settings/ai-models", json=request.param)


@pytest.fixture(
    params=[
        (InvalidSettingError("Unknown setting 'theme'"), 400),
        (InvalidProviderSettingError("OpenAI cannot serve video"), 400),
        (ProviderNotFoundError("midjourney"), 404),
    ]
)
def refused_patch_response(request, client, mocked_service):
    error, expected_status = request.param
    mocked_service.update_ai_model_settings.side_effect = error
    response = client.patch("/settings/ai-models", json={})
    return SimpleNamespace(
        actual=(response.status_code, response.json()),
        expected=(expected_status, {"detail": str(error)}),
    )


@pytest.fixture
def saved_through_the_route():
    app = create_app()
    app.state.container = SimpleNamespace(ai_model_setting_service=build_parts().service)
    response = TestClient(app).patch(
        "/settings/ai-models",
        json={"inputMode": "whole_video", "routes": {"image": "sd_webui", "video": "replicate"}},
    )
    return SimpleNamespace(status_code=response.status_code, body=response.json())


def test_patch_route_splits_the_body_into_settings_routes_and_models(
    patch_response, mocked_service
):
    assert patch_response.status_code == 200
    mocked_service.update_ai_model_settings.assert_called_once_with(
        AiModelSettingsUpdate(
            setting_values={"inputMode": "whole_video", "theme": "dark"},
            provider_ids_by_route={"image": "fal"},
            model_ids_by_provider={"fal": {"image": "fal-ai/nano-banana-pro"}},
        )
    )


def test_patch_route_answers_the_settings_and_the_providers(patch_response):
    assert patch_response.json() == {
        "settings": {"inputMode": "whole_video"},
        "providers": {"routes": DEFAULT_ROUTES, "providers": [], "secretKeySet": False},
    }


def test_an_empty_body_changes_nothing(empty_patch_response, mocked_service):
    assert empty_patch_response.status_code == 200
    mocked_service.update_ai_model_settings.assert_called_once_with(build_update())


def test_patch_route_answers_422_for_a_body_of_the_wrong_shape(malformed_patch_response):
    assert malformed_patch_response.status_code == 422


def test_patch_route_maps_the_rule_errors(refused_patch_response):
    assert refused_patch_response.actual == refused_patch_response.expected


def test_patch_route_returns_what_was_saved(saved_through_the_route):
    assert saved_through_the_route.status_code == 200
    assert saved_through_the_route.body["settings"]["inputMode"] == "whole_video"
    assert saved_through_the_route.body["providers"]["routes"] == {
        "image": "sd_webui",
        "video": "replicate",
        "speech": "omnivoice",
        "music": "ace_step",
    }
