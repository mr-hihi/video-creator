from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.providers.claude_cli_check import ClaudeCliCheck, ClaudeCliStatus
from app.modules.providers.connection_tester import ConnectionOutcome, ProviderConnectionTester
from app.modules.providers.errors import (
    ExtensionNotConnectedError,
    InvalidProviderSettingError,
    ProviderNotFoundError,
    ProviderNotSetUpError,
    SecretKeyMissingError,
)
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.models import Provider
from app.modules.providers.provider_catalog import MediaFeature, MediaKind, ProviderId
from app.modules.providers.provider_rules import ProviderUpdate, Unset
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.secret_box import SecretBox
from app.modules.providers.service import (
    ChosenProviderSettings,
    ConnectionTestResult,
    ProviderQueueCounts,
    ProviderSettingService,
    ProviderSettingTools,
)

SECRET = "test-secret"
TESTED_AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


def build_provider(provider_id: ProviderId, **overrides) -> Provider:
    fields = {
        "id": provider_id.value,
        "api_key_encrypted": None,
        "api_key_last4": None,
        "base_url": None,
        "models": {},
        "max_concurrent": 2,
        "min_interval_s": 0,
        "flow_project_id": None,
        "last_test_at": None,
        "last_test_ok": None,
        "last_test_error": None,
    }
    return Provider(**{**fields, **overrides})


def build_cli_check(status: ClaudeCliStatus) -> MagicMock:
    cli_check = MagicMock(spec=ClaudeCliCheck)
    cli_check.check.return_value = status
    cli_check.get_recent_status.return_value = status
    cli_check.describe_failure.return_value = (
        None if status is ClaudeCliStatus.SIGNED_IN else "Not signed in — run claude auth login"
    )
    return cli_check


def build_service(
    providers: list[Provider],
    secret: str = SECRET,
    routes=None,
    cli_status: ClaudeCliStatus = ClaudeCliStatus.SIGNED_IN,
):
    repository = MagicMock(spec=ProviderRepository)
    providers_by_id = {provider.id: provider for provider in providers}
    repository.find_all.return_value = providers
    repository.find_by_id.side_effect = providers_by_id.get
    repository.find_route_provider_ids.return_value = routes or {}
    tester = MagicMock(spec=ProviderConnectionTester)
    tester.test.return_value = ConnectionOutcome(is_ok=True, error=None)
    extension = FlowExtensionBridge()
    queue_counter = MagicMock()
    queue_counter.count_by_provider.return_value = {
        "fal": ProviderQueueCounts(queued=2, processing=1, failed_last_24h=3)
    }
    cli_check = build_cli_check(cli_status)
    chosen_provider_settings = MagicMock(spec=ChosenProviderSettings)
    chosen_provider_settings.get_chosen_image_provider.return_value = None
    chosen_provider_settings.get_chosen_clip_provider.return_value = None
    service = ProviderSettingService(
        repository,
        ProviderSettingTools(
            secret_box=SecretBox(secret),
            connection_tester=tester,
            extension=extension,
            queue_counter=queue_counter,
            claude_cli_check=cli_check,
            chosen_provider_settings=chosen_provider_settings,
        ),
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        tester=tester,
        extension=extension,
        cli_check=cli_check,
        chosen_provider_settings=chosen_provider_settings,
    )


def capture(error_class, action):
    with pytest.raises(error_class) as caught:
        action()
    return caught.value


@pytest.fixture
def fresh_install():
    parts = build_service([build_provider(ProviderId.GOOGLE)])
    parts.service.ensure_providers()
    return parts


@pytest.fixture
def stored_key():
    return SecretBox(SECRET).encrypt("fal-key-abcd")


@pytest.fixture
def settings_view(stored_key):
    parts = build_service(
        [
            build_provider(ProviderId.GOOGLE_FLOW, flow_project_id="flow-1"),
            build_provider(ProviderId.FAL, api_key_encrypted=stored_key, api_key_last4="abcd"),
            build_provider(
                ProviderId.OPENAI,
                api_key_encrypted=SecretBox("old").encrypt("sk"),
                api_key_last4="x-sk",
            ),
            build_provider(
                ProviderId.SD_WEBUI,
                base_url="http://127.0.0.1:7860",
                last_test_at=TESTED_AT,
                last_test_ok=False,
                last_test_error="down",
            ),
            build_provider(ProviderId.CLAUDE_CLI, max_concurrent=1),
        ],
        routes={"music": "yue"},
    )
    parts.extension.pause_for(60)
    return parts.service.get_settings_view()


@pytest.fixture
def saved_key_update():
    parts = build_service([build_provider(ProviderId.OPENAI)])
    parts.service.update_provider("openai", ProviderUpdate(api_key="  sk-test-0000abcd  "))
    return parts.repository.update_fields.call_args.args


@pytest.fixture
def removed_key_update(stored_key):
    parts = build_service([build_provider(ProviderId.FAL, api_key_encrypted=stored_key)])
    parts.service.update_provider(
        "fal",
        ProviderUpdate(api_key=None, models={"video": "bytedance/seedance-2.5/image-to-video"}),
    )
    return parts.repository.update_fields.call_args.args


@pytest.fixture
def flow_update():
    parts = build_service([build_provider(ProviderId.GOOGLE_FLOW, models={"image": "NARWHAL"})])
    parts.service.update_provider(
        "google_flow",
        ProviderUpdate(
            models={"video": "veo_3_1_i2v_lite"},
            flow_project_id="6c1b2f4e-91a2-4c5e-9d0f-0a1b2c3d4e5f",
            max_concurrent=3,
            min_interval_s=20,
        ),
    )
    return parts.repository.update_fields.call_args.args


@pytest.fixture
def local_update():
    parts = build_service([build_provider(ProviderId.SD_WEBUI)])
    parts.service.update_provider("sd_webui", ProviderUpdate(base_url="http://127.0.0.1:7860"))
    return parts.repository.update_fields.call_args.args


@pytest.fixture
def missing_secret_error():
    parts = build_service([build_provider(ProviderId.OPENAI)], secret="")
    return capture(
        SecretKeyMissingError,
        lambda: parts.service.update_provider("openai", ProviderUpdate(api_key="sk-1")),
    )


@pytest.fixture
def invalid_update_error():
    parts = build_service([build_provider(ProviderId.SD_WEBUI)])
    return capture(
        InvalidProviderSettingError,
        lambda: parts.service.update_provider("sd_webui", ProviderUpdate(api_key="sk")),
    )


@pytest.fixture(params=["midjourney", "openai"])
def unknown_provider_error(request):
    parts = build_service([])
    return capture(ProviderNotFoundError, lambda: parts.service.get_provider_view(request.param))


@pytest.fixture
def not_set_up_test():
    parts = build_service([build_provider(ProviderId.ELEVENLABS)])
    result = parts.service.test_connection("elevenlabs")
    return SimpleNamespace(result=result, parts=parts)


@pytest.fixture
def set_up_test(stored_key):
    parts = build_service([build_provider(ProviderId.FAL, api_key_encrypted=stored_key)])
    result = parts.service.test_connection("fal")
    return SimpleNamespace(result=result, parts=parts)


CLONE = MediaFeature.FILM_CLONE
STUDIO = MediaFeature.FILM_STUDIO
NO_CHOICE: dict[MediaFeature, ProviderId] = {}
CLONE_CHOOSES_GOOGLE = {CLONE: ProviderId.GOOGLE}
STUDIO_CHOOSES_SD = {STUDIO: ProviderId.SD_WEBUI}


@pytest.fixture(
    params=[
        (MediaKind.SPEECH, STUDIO, NO_CHOICE, None, {}, ProviderId.OMNIVOICE),
        (MediaKind.SPEECH, STUDIO, NO_CHOICE, None, {"speech": "google"}, ProviderId.GOOGLE),
        (MediaKind.MUSIC, STUDIO, NO_CHOICE, ProviderId.FAL, {}, ProviderId.ACE_STEP),
        (MediaKind.MUSIC, STUDIO, NO_CHOICE, None, {"music": "yue"}, ProviderId.YUE),
        (MediaKind.IMAGE, STUDIO, NO_CHOICE, None, {}, ProviderId.GOOGLE_FLOW),
        (MediaKind.IMAGE, CLONE, NO_CHOICE, None, {"image": "fal"}, ProviderId.FAL),
        (MediaKind.IMAGE, STUDIO, NO_CHOICE, None, {"image": "openai"}, ProviderId.OPENAI),
        (MediaKind.IMAGE, CLONE, CLONE_CHOOSES_GOOGLE, None, {"image": "fal"}, ProviderId.GOOGLE),
        (MediaKind.IMAGE, STUDIO, CLONE_CHOOSES_GOOGLE, None, {"image": "fal"}, ProviderId.FAL),
        (MediaKind.EDIT_IMAGE, STUDIO, STUDIO_CHOOSES_SD, None, {}, ProviderId.SD_WEBUI),
        (MediaKind.EDIT_IMAGE, CLONE, STUDIO_CHOOSES_SD, None, {}, ProviderId.GOOGLE_FLOW),
        (MediaKind.VIDEO, STUDIO, STUDIO_CHOOSES_SD, None, {}, ProviderId.GOOGLE_FLOW),
        (MediaKind.VIDEO, STUDIO, NO_CHOICE, None, {"video": "replicate"}, ProviderId.REPLICATE),
        (MediaKind.VIDEO, STUDIO, NO_CHOICE, ProviderId.FAL, {"video": "google"}, ProviderId.FAL),
    ]
)
def picked_provider(request):
    media_kind, feature, chosen_images, chosen_clip, routes, expected = request.param
    parts = build_service([], routes=routes)
    parts.chosen_provider_settings.get_chosen_image_provider.side_effect = chosen_images.get
    parts.chosen_provider_settings.get_chosen_clip_provider.return_value = chosen_clip
    return SimpleNamespace(
        actual=parts.service.pick_provider(media_kind, feature), expected=expected
    )


@pytest.fixture
def fal_access(stored_key):
    parts = build_service(
        [
            build_provider(
                ProviderId.FAL,
                api_key_encrypted=stored_key,
                models={"edit_image": "fal-ai/flux-pro/kontext"},
            )
        ]
    )
    return parts.service.get_access(ProviderId.FAL)


@pytest.fixture
def unreadable_key_access_error():
    parts = build_service(
        [build_provider(ProviderId.FAL, api_key_encrypted=SecretBox("old").encrypt("k"))]
    )
    return capture(ProviderNotSetUpError, lambda: parts.service.get_access(ProviderId.FAL))


@pytest.fixture
def local_access_error():
    parts = build_service([build_provider(ProviderId.OMNIVOICE)])
    return capture(ProviderNotSetUpError, lambda: parts.service.get_access(ProviderId.OMNIVOICE))


@pytest.fixture
def resumed_flow():
    parts = build_service([build_provider(ProviderId.GOOGLE_FLOW)])
    parts.extension.pause_for(120)
    return parts.service.resume_google_flow()


@pytest.fixture
def open_tab_without_extension_error():
    parts = build_service([])
    return capture(ExtensionNotConnectedError, parts.service.open_flow_tab)


@pytest.fixture
def opened_tab_commands():
    parts = build_service([])
    commands = []
    parts.extension.register_connection(commands.append)
    parts.service.open_flow_tab()
    return commands


@pytest.fixture
def stored_models():
    parts = build_service(
        [
            build_provider(ProviderId.GOOGLE_FLOW, models={"video": "veo_3_1_i2v_lite"}),
            build_provider(ProviderId.REPLICATE),
        ]
    )
    return SimpleNamespace(
        result=parts.service.to_stored_models(
            {"google_flow": {"image": "NARWHAL"}, "replicate": {"video": "alibaba/wan-3"}}
        ),
        repository=parts.repository,
    )


@pytest.fixture(
    params=[
        (
            {"openai": {"video": "sora-2"}},
            InvalidProviderSettingError,
            "models.video does not apply to OpenAI",
        ),
        (
            {"openai": {"image": "gpt-image-9"}},
            InvalidProviderSettingError,
            "Unknown model 'gpt-image-9' for OpenAI image",
        ),
        (
            {"sd_webui": {"image": "flux1-dev"}},
            InvalidProviderSettingError,
            "models does not apply to Stable Diffusion WebUI / Forge",
        ),
        (
            {"claude_cli": {"analysis": "opus"}},
            InvalidProviderSettingError,
            "models does not apply to Claude CLI",
        ),
        ({"midjourney": {"image": "mj-7"}}, ProviderNotFoundError, "Provider midjourney not found"),
    ]
)
def rejected_models(request):
    model_ids_by_provider, error_class, expected = request.param
    parts = build_service(
        [
            build_provider(ProviderId.OPENAI),
            build_provider(ProviderId.SD_WEBUI),
            build_provider(ProviderId.CLAUDE_CLI),
        ]
    )
    error = capture(error_class, lambda: parts.service.to_stored_models(model_ids_by_provider))
    return SimpleNamespace(message=str(error), expected=expected, repository=parts.repository)


def test_ensure_providers_adds_the_missing_rows_with_default_pacing(fresh_install):
    added = fresh_install.repository.add_all.call_args.args[0]
    assert [provider.id for provider in added] == [
        "google_flow",
        "fal",
        "replicate",
        "openai",
        "elevenlabs",
        "sd_webui",
        "omnivoice",
        "ace_step",
        "yue",
        "claude_cli",
    ]
    assert (added[0].max_concurrent, added[0].min_interval_s) == (5, 10)
    assert (added[1].max_concurrent, added[1].min_interval_s) == (2, 0)
    assert (added[5].max_concurrent, added[5].min_interval_s) == (1, 0)


def test_settings_view_reports_keys_status_queue_and_flow(settings_view):
    flow, fal, openai, sd, claude_cli = settings_view.providers
    assert settings_view.provider_ids_by_route == {
        "image": "google_flow",
        "video": "google_flow",
        "speech": "omnivoice",
        "music": "yue",
    }
    assert settings_view.is_secret_key_set is True
    assert (fal.has_key, fal.is_set_up, fal.api_key_last4) == (True, True, "abcd")
    assert fal.queue == ProviderQueueCounts(queued=2, processing=1, failed_last_24h=3)
    assert (openai.has_key, openai.is_key_unreadable, openai.is_set_up) == (True, True, False)
    assert sd.is_set_up is True
    assert sd.catalog == {}
    assert sd.last_test == ConnectionTestResult(is_ok=False, error="down", tested_at=TESTED_AT)
    assert flow.flow.flow_project_id == "flow-1"
    assert flow.flow.is_extension_connected is False
    assert flow.flow.paused_until is not None
    assert fal.flow is None
    assert [model.id for model in fal.catalog[MediaKind.VIDEO]] == [
        "fal-ai/kling-video/v3/pro/image-to-video",
        "bytedance/seedance-2.5/image-to-video",
    ]


def test_the_claude_cli_is_set_up_and_reports_its_sign_in_status(settings_view):
    claude_cli = settings_view.providers[4]
    assert (claude_cli.is_set_up, claude_cli.cli_status) == (True, ClaudeCliStatus.SIGNED_IN)
    assert [model.id for model in claude_cli.catalog[MediaKind.ANALYSIS]] == [
        "default",
        "fable",
        "opus",
        "sonnet",
        "haiku",
    ]
    assert settings_view.providers[1].cli_status is None


def test_saving_a_key_stores_it_encrypted_with_its_last_chars(saved_key_update):
    provider_id, values = saved_key_update
    assert provider_id == ProviderId.OPENAI
    assert values["api_key_last4"] == "abcd"
    assert SecretBox(SECRET).decrypt(values["api_key_encrypted"]) == "sk-test-0000abcd"


def test_removing_a_key_clears_it_and_merges_models(removed_key_update):
    assert removed_key_update[1] == {
        "api_key_encrypted": None,
        "api_key_last4": None,
        "models": {"video": "bytedance/seedance-2.5/image-to-video"},
    }


def test_flow_update_merges_models_and_stores_project_and_pacing(flow_update):
    assert flow_update[1] == {
        "models": {"image": "NARWHAL", "video": "veo_3_1_i2v_lite"},
        "flow_project_id": "6c1b2f4e-91a2-4c5e-9d0f-0a1b2c3d4e5f",
        "max_concurrent": 3,
        "min_interval_s": 20,
    }


def test_local_update_stores_the_base_url(local_update):
    assert local_update[1] == {"base_url": "http://127.0.0.1:7860"}


def test_saving_a_key_without_a_secret_is_refused(missing_secret_error):
    assert str(missing_secret_error) == (
        "Set SETTINGS_SECRET_KEY in api/.env before saving API keys"
    )


def test_update_runs_the_rules(invalid_update_error):
    assert str(invalid_update_error) == "apiKey does not apply to Stable Diffusion WebUI / Forge"


def test_unknown_provider_is_404(unknown_provider_error):
    assert "not found" in str(unknown_provider_error)


def test_test_connection_without_set_up_skips_the_call(not_set_up_test):
    assert (not_set_up_test.result.is_ok, not_set_up_test.result.error) == (False, "Not set up")
    not_set_up_test.parts.tester.test.assert_not_called()
    stored = not_set_up_test.parts.repository.update_fields.call_args.args[1]
    assert (stored["last_test_ok"], stored["last_test_error"]) == (False, "Not set up")


def test_test_connection_calls_the_tester_with_the_key(set_up_test):
    check = set_up_test.parts.tester.test.call_args.args[0]
    assert set_up_test.result.is_ok is True
    assert check.api_key == "fal-key-abcd"


def test_pick_provider_follows_the_chosen_providers_and_routes(picked_provider):
    assert picked_provider.actual == picked_provider.expected


@pytest.fixture
def ai_provider_states(stored_key):
    parts = build_service(
        [
            build_provider(ProviderId.GOOGLE, api_key_encrypted=stored_key),
            build_provider(ProviderId.OPENAI),
            build_provider(ProviderId.CLAUDE_CLI),
        ]
    )
    return {
        provider_id: (
            parts.service.is_set_up(provider_id),
            parts.service.find_api_key(provider_id),
        )
        for provider_id in (ProviderId.GOOGLE, ProviderId.OPENAI, ProviderId.CLAUDE_CLI)
    }


@pytest.fixture
def analysis_model_error():
    parts = build_service([build_provider(ProviderId.GOOGLE)])
    return capture(
        InvalidProviderSettingError,
        lambda: parts.service.update_provider(
            "google", ProviderUpdate(models={"analysis": "gemini-4-argon"})
        ),
    )


@pytest.fixture(
    params=[
        (ClaudeCliStatus.SIGNED_IN, (True, None)),
        (ClaudeCliStatus.NOT_SIGNED_IN, (False, "Not signed in — run claude auth login")),
    ]
)
def claude_cli_test(request):
    status, expected = request.param
    parts = build_service([build_provider(ProviderId.CLAUDE_CLI)], cli_status=status)
    result = parts.service.test_connection("claude_cli")
    return SimpleNamespace(
        status=status, actual=(result.is_ok, result.error), expected=expected, parts=parts
    )


def test_ai_providers_report_whether_they_are_set_up_and_their_key(ai_provider_states):
    assert ai_provider_states == {
        ProviderId.GOOGLE: (True, "fal-key-abcd"),
        ProviderId.OPENAI: (False, None),
        ProviderId.CLAUDE_CLI: (True, None),
    }


def test_the_analysis_model_is_not_set_on_a_provider(analysis_model_error):
    assert str(analysis_model_error) == (
        "models.analysis does not apply to Google AI (Gemini, Veo)"
    )


def test_the_claude_cli_test_runs_the_sign_in_check(claude_cli_test):
    assert claude_cli_test.actual == claude_cli_test.expected
    claude_cli_test.parts.cli_check.describe_failure.assert_called_once_with(claude_cli_test.status)
    claude_cli_test.parts.tester.test.assert_not_called()


def test_get_access_resolves_chosen_and_default_models(fal_access):
    assert fal_access.api_key == "fal-key-abcd"
    assert fal_access.models[MediaKind.EDIT_IMAGE].id == "fal-ai/flux-pro/kontext"
    assert fal_access.models[MediaKind.IMAGE].id == "fal-ai/nano-banana-pro"


def test_get_access_refuses_a_provider_not_set_up(unreadable_key_access_error, local_access_error):
    assert str(unreadable_key_access_error) == "fal.ai is not set up — open Settings"
    assert str(local_access_error) == "OmniVoice is not set up — open Settings"


def test_resume_ends_the_flow_pause(resumed_flow):
    assert resumed_flow.flow.paused_until is None


def test_open_flow_tab_needs_the_extension(open_tab_without_extension_error, opened_tab_commands):
    assert str(open_tab_without_extension_error) == "The Google Flow extension is not connected"
    assert opened_tab_commands == [{"type": "open_flow_tab"}]


def test_stored_models_merge_the_new_models_into_each_provider(stored_models):
    assert stored_models.result == {
        "google_flow": {"video": "veo_3_1_i2v_lite", "image": "NARWHAL"},
        "replicate": {"video": "alibaba/wan-3"},
    }
    stored_models.repository.update_fields.assert_not_called()


def test_stored_models_run_the_model_rules(rejected_models):
    assert rejected_models.message == rejected_models.expected
    rejected_models.repository.update_fields.assert_not_called()


@pytest.fixture
def provider_service_mock(settings_view):
    service = MagicMock(spec=ProviderSettingService)
    service.get_settings_view.return_value = settings_view
    service.get_provider_view.return_value = settings_view.providers[1]
    service.update_provider.return_value = settings_view.providers[1]
    service.resume_google_flow.return_value = settings_view.providers[0]
    service.test_connection.return_value = ConnectionTestResult(
        is_ok=False, error="Not set up", tested_at=TESTED_AT
    )
    return service


@pytest.fixture
def client(provider_service_mock):
    app = create_app()
    app.state.container = SimpleNamespace(provider_setting_service=provider_service_mock)
    return TestClient(app)


@pytest.fixture
def list_response(client):
    return client.get("/settings/providers")


@pytest.fixture
def patch_response(client):
    return client.patch(
        "/settings/providers/fal",
        json={"apiKey": None, "maxConcurrent": 3, "models": {"image": "x"}},
    )


@pytest.fixture
def removed_routes_response():
    app = create_app()
    app.state.container = SimpleNamespace(provider_setting_service=build_service([]).service)
    return TestClient(app).patch("/settings/providers/routes", json={"image": "fal"})


@pytest.fixture
def test_response(client):
    return client.post("/settings/providers/elevenlabs/test")


@pytest.fixture
def resume_response(client):
    return client.post("/settings/providers/google_flow/resume")


@pytest.fixture
def open_tab_response(client, provider_service_mock):
    provider_service_mock.open_flow_tab.side_effect = ExtensionNotConnectedError()
    return client.post("/settings/providers/google_flow/open-tab")


def test_list_route_returns_camel_case_providers(list_response):
    body = list_response.json()
    flow, fal = body["providers"][0], body["providers"][1]
    assert body["secretKeySet"] is True
    assert fal["queue"] == {"queued": 2, "processing": 1, "failedLast24h": 3}
    assert fal["catalog"]["video"][0] == {
        "id": "fal-ai/kling-video/v3/pro/image-to-video",
        "label": "Kling 3 Pro",
        "isDefault": True,
        "clipLengths": [4, 6, 8, 10],
        "maxReferences": None,
    }
    assert fal["extensionConnected"] is None
    assert flow["flowProjectId"] == "flow-1"
    assert body["providers"][4]["cliStatus"] == "signedIn"
    assert fal["cliStatus"] is None
    assert body["providers"][3]["lastTest"]["error"] == "down"


def test_patch_route_passes_only_the_given_fields(patch_response, provider_service_mock):
    update = provider_service_mock.update_provider.call_args.args[1]
    assert patch_response.status_code == 200
    assert update.api_key is None
    assert update.max_concurrent == 3
    assert isinstance(update.models, Unset)
    assert type(update.base_url).__name__ == "Unset"
    assert type(update.flow_project_id).__name__ == "Unset"


def test_the_routes_are_no_longer_saved_on_the_provider_routes(removed_routes_response):
    assert removed_routes_response.status_code == 404
    assert removed_routes_response.json() == {"detail": "Provider routes not found"}


def test_test_and_resume_routes(test_response, resume_response):
    assert test_response.json() == {
        "ok": False,
        "error": "Not set up",
        "testedAt": "2026-10-11T09:00:00Z",
    }
    assert resume_response.json()["id"] == "google_flow"


def test_open_tab_without_extension_is_409(open_tab_response):
    assert open_tab_response.status_code == 409
