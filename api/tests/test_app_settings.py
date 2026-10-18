from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.ai_models.ai_calls import AiModelChoice, AiStepGroup, InputMode
from app.modules.app_settings.errors import InvalidSettingError
from app.modules.app_settings.repository import AppSettingRepository
from app.modules.app_settings.service import AppSettingService
from app.modules.app_settings.setting_rules import ScriptLanguage
from app.modules.providers.provider_catalog import MediaFeature, ProviderId

NO_STEP_MODELS = {"moments": None, "filmAnalysis": None, "filmScript": None, "filmClone": None}
GEMINI_ARGON = {"provider": "google", "model": "gemini-4-argon"}
GPT_LUNA = {"provider": "openai", "model": "gpt-6-luna"}
DEFAULT_SETTINGS = {
    "scriptLanguage": "follow_target_country",
    "aiModel": {"provider": "claude_cli", "model": "default"},
    "aiStepModels": NO_STEP_MODELS,
    "inputMode": "subtitles",
    "filmCloneInputMode": "subtitles",
    "filmCloneImageProvider": None,
    "filmStudioImageProvider": None,
    "filmStudioClipProvider": None,
}
STORED_VALUES = {
    "scriptLanguage": "ja",
    "aiModel": GEMINI_ARGON,
    "aiStepModels": {**NO_STEP_MODELS, "filmClone": GPT_LUNA},
    "inputMode": "whole_video",
    "filmCloneInputMode": "whole_video",
    "filmCloneImageProvider": "openai",
    "filmStudioImageProvider": "sd_webui",
    "filmStudioClipProvider": "replicate",
}


def capture_setting_error(service: AppSettingService, values) -> InvalidSettingError:
    with pytest.raises(InvalidSettingError) as caught:
        service.update_settings(values)
    return caught.value


@pytest.fixture
def empty_repository():
    repository = MagicMock(spec=AppSettingRepository)
    repository.find_values.return_value = {}
    return repository


@pytest.fixture
def japanese_repository():
    repository = MagicMock(spec=AppSettingRepository)
    repository.find_values.return_value = {**STORED_VALUES, "imageSource": "local", "retired": "x"}
    return repository


@pytest.fixture
def default_settings(empty_repository):
    return AppSettingService(empty_repository).get_settings()


@pytest.fixture
def stored_settings(japanese_repository):
    return AppSettingService(japanese_repository).get_settings()


@pytest.fixture
def stored_script_language(japanese_repository):
    return AppSettingService(japanese_repository).get_script_language()


@pytest.fixture
def stored_ai_choice(japanese_repository):
    service = AppSettingService(japanese_repository)
    return (service.get_ai_model(), service.get_ai_step_models(), service.get_input_mode())


@pytest.fixture
def default_ai_choice(empty_repository):
    service = AppSettingService(empty_repository)
    return (service.get_ai_model(), service.get_ai_step_models(), service.get_input_mode())


@pytest.fixture
def stored_input_modes(empty_repository):
    empty_repository.find_values.return_value = {"filmCloneInputMode": "whole_video"}
    service = AppSettingService(empty_repository)
    return (service.get_input_mode(), service.get_film_clone_input_mode())


@pytest.fixture
def default_film_clone_input_mode(empty_repository):
    return AppSettingService(empty_repository).get_film_clone_input_mode()


@pytest.fixture
def stored_chosen_providers(japanese_repository):
    service = AppSettingService(japanese_repository)
    return (
        service.get_chosen_image_provider(MediaFeature.FILM_CLONE),
        service.get_chosen_image_provider(MediaFeature.FILM_STUDIO),
        service.get_chosen_clip_provider(),
    )


@pytest.fixture
def default_chosen_providers(empty_repository):
    service = AppSettingService(empty_repository)
    return (
        service.get_chosen_image_provider(MediaFeature.FILM_CLONE),
        service.get_chosen_image_provider(MediaFeature.FILM_STUDIO),
        service.get_chosen_clip_provider(),
    )


@pytest.fixture
def legacy_settings(empty_repository):
    empty_repository.find_values.return_value = {
        "aiModel": "gemini",
        "aiStepModels": {"filmClone": {"provider": "google", "model": "gemini-1"}},
        "filmCloneInputMode": "frames",
        "filmCloneImageProvider": "dall-e",
        "filmStudioClipProvider": "sd_webui",
    }
    return AppSettingService(empty_repository).get_settings()


@pytest.fixture
def updated_settings(empty_repository):
    empty_repository.find_values.side_effect = [{"scriptLanguage": "en"}]
    return AppSettingService(empty_repository).update_settings({"scriptLanguage": "en"})


@pytest.fixture
def updated_media_settings(empty_repository):
    AppSettingService(empty_repository).update_settings(
        {
            "filmCloneInputMode": "whole_video",
            "filmCloneImageProvider": None,
            "filmStudioImageProvider": "google_flow",
            "filmStudioClipProvider": "fal",
        }
    )
    return empty_repository.save_values.call_args.args[0]


@pytest.fixture
def updated_ai_settings(empty_repository):
    AppSettingService(empty_repository).update_settings(
        {"aiModel": GPT_LUNA, "aiStepModels": {"moments": GEMINI_ARGON}}
    )
    return empty_repository.save_values.call_args.args[0]


@pytest.fixture(
    params=[
        ({"theme": "dark"}, "Unknown setting 'theme'"),
        ({"scriptLanguage": "de"}, "Invalid value for 'scriptLanguage'"),
        ({"scriptLanguage": "ja", "theme": "dark"}, "Unknown setting 'theme'"),
        ({"scriptLanguage": ["ja"]}, "Invalid value for 'scriptLanguage'"),
        ({"aiModel": "claude"}, "Invalid value for 'aiModel'"),
        (
            {"aiModel": {"provider": "openai", "model": "gemini-4-argon"}},
            "Invalid value for 'aiModel'",
        ),
        ({"aiStepModels": {"subtitles": None}}, "Invalid value for 'aiStepModels'"),
        ({"aiStepModels": {"moments": "default"}}, "Invalid value for 'aiStepModels'"),
        ({"inputMode": "audio"}, "Invalid value for 'inputMode'"),
        ({"inputMode": None}, "Invalid value for 'inputMode'"),
        ({"filmCloneInputMode": "frames"}, "Invalid value for 'filmCloneInputMode'"),
        ({"filmCloneImageProvider": "dall-e"}, "Invalid value for 'filmCloneImageProvider'"),
        ({"filmCloneImageProvider": "elevenlabs"}, "Invalid value for 'filmCloneImageProvider'"),
        ({"filmStudioImageProvider": 3}, "Invalid value for 'filmStudioImageProvider'"),
        ({"filmStudioClipProvider": "sd_webui"}, "Invalid value for 'filmStudioClipProvider'"),
        ({"filmStudioClipProvider": "openai"}, "Invalid value for 'filmStudioClipProvider'"),
        ({"imageSource": "local"}, "Unknown setting 'imageSource'"),
        ({"clipSource": "api"}, "Unknown setting 'clipSource'"),
    ]
)
def rejected_update(request, empty_repository):
    values, expected_message = request.param
    error = capture_setting_error(AppSettingService(empty_repository), values)
    return SimpleNamespace(
        message=str(error), expected_message=expected_message, repository=empty_repository
    )


@pytest.fixture
def setting_service():
    service = MagicMock(spec=AppSettingService)
    service.get_settings.return_value = DEFAULT_SETTINGS
    service.update_settings.return_value = {"scriptLanguage": "ja"}
    return service


@pytest.fixture
def client(setting_service):
    app = create_app()
    app.state.container = SimpleNamespace(app_setting_service=setting_service)
    return TestClient(app)


@pytest.fixture
def get_response(client):
    return client.get("/settings")


@pytest.fixture
def patch_response(client):
    return client.patch("/settings", json={"scriptLanguage": "ja"})


@pytest.fixture
def patch_list_response(client):
    return client.patch("/settings", json=["ja"])


@pytest.fixture
def invalid_patch_response(client, setting_service):
    setting_service.update_settings.side_effect = InvalidSettingError("Unknown setting 'theme'")
    return client.patch("/settings", json={"theme": "dark"})


def test_get_settings_fills_defaults(default_settings):
    assert default_settings == DEFAULT_SETTINGS


def test_get_settings_returns_stored_values_and_drops_unknown_rows(stored_settings):
    assert stored_settings == STORED_VALUES


def test_the_ai_settings_are_read_as_model_choices(stored_ai_choice):
    assert stored_ai_choice == (
        AiModelChoice(ProviderId.GOOGLE, "gemini-4-argon"),
        {
            AiStepGroup.MOMENTS: None,
            AiStepGroup.FILM_ANALYSIS: None,
            AiStepGroup.FILM_SCRIPT: None,
            AiStepGroup.FILM_CLONE: AiModelChoice(ProviderId.OPENAI, "gpt-6-luna"),
        },
        InputMode.WHOLE_VIDEO,
    )


def test_the_ai_settings_default_to_the_claude_cli_and_subtitles(default_ai_choice):
    assert default_ai_choice == (
        AiModelChoice(ProviderId.CLAUDE_CLI, "default"),
        {group: None for group in AiStepGroup},
        InputMode.SUBTITLES,
    )


def test_film_clone_reads_its_own_input_mode(stored_input_modes):
    assert stored_input_modes == (InputMode.SUBTITLES, InputMode.WHOLE_VIDEO)


def test_the_film_clone_input_mode_defaults_to_subtitles(default_film_clone_input_mode):
    assert default_film_clone_input_mode is InputMode.SUBTITLES


def test_the_chosen_providers_are_read_per_feature(stored_chosen_providers):
    assert stored_chosen_providers == (ProviderId.OPENAI, ProviderId.SD_WEBUI, ProviderId.REPLICATE)


def test_no_provider_is_chosen_by_default(default_chosen_providers):
    assert default_chosen_providers == (None, None, None)


def test_the_media_settings_are_stored_with_null_for_the_route(updated_media_settings):
    assert updated_media_settings == {
        "filmCloneInputMode": "whole_video",
        "filmCloneImageProvider": None,
        "filmStudioImageProvider": "google_flow",
        "filmStudioClipProvider": "fal",
    }


def test_a_stored_value_that_no_longer_fits_reads_as_the_default(legacy_settings):
    assert legacy_settings == DEFAULT_SETTINGS


def test_ai_models_are_stored_with_every_step_group(updated_ai_settings):
    assert updated_ai_settings == {
        "aiModel": GPT_LUNA,
        "aiStepModels": {**NO_STEP_MODELS, "moments": GEMINI_ARGON},
    }


def test_get_script_language_reads_the_setting(stored_script_language):
    assert stored_script_language is ScriptLanguage.JAPANESE


def test_update_settings_saves_and_returns_the_new_values(updated_settings, empty_repository):
    assert updated_settings == {**DEFAULT_SETTINGS, "scriptLanguage": "en"}
    empty_repository.save_values.assert_called_once_with({"scriptLanguage": "en"})


def test_update_settings_rejects_without_saving(rejected_update):
    assert rejected_update.message == rejected_update.expected_message
    rejected_update.repository.save_values.assert_not_called()


def test_get_route_returns_the_settings(get_response):
    assert get_response.json() == DEFAULT_SETTINGS


def test_patch_route_forwards_the_values(patch_response, setting_service):
    assert patch_response.json() == {"scriptLanguage": "ja"}
    setting_service.update_settings.assert_called_once_with({"scriptLanguage": "ja"})


def test_patch_route_answers_422_for_a_list(patch_list_response):
    assert patch_list_response.status_code == 422


def test_patch_route_answers_400_for_an_invalid_setting(invalid_patch_response):
    assert invalid_patch_response.status_code == 400
    assert invalid_patch_response.json() == {"detail": "Unknown setting 'theme'"}
