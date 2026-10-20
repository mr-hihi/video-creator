import base64
import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.common.captcha import CaptchaService
from app.main import create_app
from app.modules.ai_models.ai_caller import AiCaller, AiClient
from app.modules.ai_models.ai_calls import (
    AiAsk,
    AiCallError,
    AiLimits,
    AiModelChoice,
    AiProviderNotSetUpError,
    AiStepGroup,
    GoogleModelRequiredError,
    InputMode,
)
from app.modules.ai_models.ai_images import AiImageEncoding, to_ai_jpeg_base64
from app.modules.ai_models.model_choices import (
    to_ai_name,
    to_group_label,
    to_model_choice,
    to_model_label,
    to_provider_name,
    to_step_model_choices,
    to_step_models_value,
)
from app.modules.ai_models.schemas import to_labelled_ai_used
from app.modules.ai_models.step_models import AiStepModels
from app.modules.app_settings.service import AppSettingService
from app.modules.jobs.job_ai import get_job_input_mode
from app.modules.jobs.service import JobService
from app.modules.jobs.storage import JobStorage
from app.modules.providers.provider_catalog import ProviderId

CLI_DEFAULT = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_ARGON = AiModelChoice(ProviderId.GOOGLE, "gemini-4-argon")
GPT_LUNA = AiModelChoice(ProviderId.OPENAI, "gpt-6-luna")
NO_STEP_MODELS = {group: None for group in AiStepGroup}
ENCODING = AiImageEncoding(max_side_px=480, jpeg_quality=60)
LIMITS = AiLimits(timeout_sec=600)
ASK = AiAsk(instructions="Rules", message="Notes")


@pytest.fixture(
    params=[
        ({"provider": "claude_cli", "model": "default"}, CLI_DEFAULT),
        ({"provider": "google", "model": "gemini-4-argon"}, GEMINI_ARGON),
        ({"provider": "openai", "model": "gpt-6-luna"}, GPT_LUNA),
        ("claude", None),
        ({"provider": "google"}, None),
        ({"provider": "google", "model": "gemini-4-argon", "label": "Gemini 4 Argon"}, None),
        ({"provider": "fal", "model": "fal-ai/nano-banana-pro"}, None),
        ({"provider": ["google"], "model": "gemini-4-argon"}, None),
        ({"provider": "google", "model": "gpt-6-astra"}, None),
        ({"provider": "google", "model": ["gemini-4-argon"]}, None),
    ]
)
def model_choice_outcome(request):
    value, expected = request.param
    return SimpleNamespace(actual=to_model_choice(value), expected=expected)


@pytest.fixture(
    params=[
        ({}, NO_STEP_MODELS),
        (
            {"filmClone": {"provider": "openai", "model": "gpt-6-luna"}, "moments": None},
            {**NO_STEP_MODELS, AiStepGroup.FILM_CLONE: GPT_LUNA},
        ),
        ({"filmClone": {"provider": "google", "model": "gemini-9"}}, None),
        ({"subtitles": None}, None),
        ("filmClone", None),
    ]
)
def step_model_choices_outcome(request):
    value, expected = request.param
    return SimpleNamespace(actual=to_step_model_choices(value), expected=expected)


def build_step_models(step_choice: AiModelChoice | None, set_up_providers: set[ProviderId]):
    settings_service = MagicMock(spec=AppSettingService)
    settings_service.get_ai_model.return_value = CLI_DEFAULT
    settings_service.get_ai_step_models.return_value = {
        **NO_STEP_MODELS,
        AiStepGroup.FILM_ANALYSIS: step_choice,
    }
    is_set_up = MagicMock(side_effect=lambda provider: provider in set_up_providers)
    return SimpleNamespace(models=AiStepModels(settings_service, is_set_up), is_set_up=is_set_up)


@pytest.fixture
def found_models():
    step_models = build_step_models(GEMINI_ARGON, set()).models
    return {group: step_models.find_model(group) for group in AiStepGroup}


@pytest.fixture
def checked_set_up_groups():
    rig = build_step_models(GEMINI_ARGON, {ProviderId.CLAUDE_CLI, ProviderId.GOOGLE})
    rig.models.ensure_set_up((AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS))
    return rig.is_set_up


@pytest.fixture
def not_set_up_error():
    rig = build_step_models(GEMINI_ARGON, {ProviderId.CLAUDE_CLI})
    with pytest.raises(AiProviderNotSetUpError) as caught:
        rig.models.ensure_set_up((AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS))
    return caught.value


def capture_google_check_error(step_choice: AiModelChoice, set_up_providers: set[ProviderId]):
    rig = build_step_models(step_choice, set_up_providers)
    with pytest.raises(AiCallError) as caught:
        rig.models.ensure_set_up(
            (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS), (AiStepGroup.FILM_ANALYSIS,)
        )
    return caught.value


@pytest.fixture
def google_group_on_another_provider_error():
    return capture_google_check_error(GPT_LUNA, {ProviderId.CLAUDE_CLI, ProviderId.OPENAI})


@pytest.fixture
def google_group_not_set_up_error():
    return capture_google_check_error(GEMINI_ARGON, {ProviderId.CLAUDE_CLI})


@pytest.fixture
def checked_google_groups():
    rig = build_step_models(GEMINI_ARGON, {ProviderId.CLAUDE_CLI, ProviderId.GOOGLE})
    rig.models.ensure_set_up(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS), (AiStepGroup.FILM_ANALYSIS,)
    )
    return rig.is_set_up


@pytest.fixture
def found_google_model():
    return build_step_models(GEMINI_ARGON, set()).models.find_google_model(
        AiStepGroup.FILM_ANALYSIS
    )


@pytest.fixture
def google_model_refusal():
    with pytest.raises(GoogleModelRequiredError) as caught:
        build_step_models(GEMINI_ARGON, set()).models.find_google_model(AiStepGroup.AUDIO)
    return caught.value


@pytest.fixture
def caller_google_model():
    step_models = MagicMock(spec=AiStepModels)
    step_models.find_google_model.return_value = GEMINI_ARGON
    caller = AiCaller({}, step_models)
    return SimpleNamespace(
        model=caller.find_google_model(AiStepGroup.AUDIO), step_models=step_models
    )


@pytest.fixture
def refused_google_upload_response():
    job_service = MagicMock(spec=JobService)
    job_service.create_video_to_markdown_job.side_effect = GoogleModelRequiredError("Audio")
    captcha_service = MagicMock(spec=CaptchaService)
    captcha_service.verify.return_value = True
    app = create_app()
    app.state.container = SimpleNamespace(job_service=job_service, captcha_service=captcha_service)
    return TestClient(app).post(
        "/jobs/video-to-markdown",
        files={"file": ("clip.mp4", b"video", "video/mp4")},
        headers={"X-Captcha-Token": "token-1"},
    )


@pytest.fixture
def ai_caller_calls():
    claude_client = MagicMock(spec=AiClient)
    claude_client.ask_for_text.return_value = "## Character A"
    gemini_client = MagicMock(spec=AiClient)
    gemini_client.ask_for_json.return_value = {"moments": []}
    step_models = MagicMock(spec=AiStepModels)
    step_models.find_model.return_value = GEMINI_ARGON
    caller = AiCaller(
        {ProviderId.CLAUDE_CLI: claude_client, ProviderId.GOOGLE: gemini_client}, step_models
    )
    return SimpleNamespace(
        model=caller.find_model(AiStepGroup.MOMENTS),
        json_reply=caller.ask_for_json(GEMINI_ARGON, ASK, LIMITS),
        text_reply=caller.ask_for_text(CLI_DEFAULT, ASK, LIMITS),
        claude_client=claude_client,
        gemini_client=gemini_client,
        step_models=step_models,
    )


def to_decoded_image(encoded: str) -> SimpleNamespace:
    data = base64.b64decode(encoded)
    with Image.open(io.BytesIO(data)) as image:
        return SimpleNamespace(size=image.size, format=image.format, data=data)


@pytest.fixture
def wide_frame(tmp_path):
    path = tmp_path / "frame.png"
    Image.new("RGBA", (2000, 1000), (10, 20, 30, 255)).save(path)
    return path


@pytest.fixture
def scaled_wide_frame(wide_frame):
    return to_decoded_image(to_ai_jpeg_base64(wide_frame, ENCODING))


@pytest.fixture
def expected_wide_frame_bytes(wide_frame):
    with Image.open(wide_frame) as image:
        expected_image = image.convert("RGB")
    expected_image.thumbnail((480, 480))
    buffer = io.BytesIO()
    expected_image.save(buffer, format="JPEG", quality=60)
    return buffer.getvalue()


@pytest.fixture
def small_frame(tmp_path):
    path = tmp_path / "small.jpg"
    Image.new("RGB", (100, 50)).save(path)
    return to_decoded_image(to_ai_jpeg_base64(path, ENCODING))


@pytest.fixture
def refused_upload_response():
    job_service = MagicMock(spec=JobService)
    job_service.create_video_to_markdown_job.side_effect = AiProviderNotSetUpError("OpenAI")
    captcha_service = MagicMock(spec=CaptchaService)
    captcha_service.verify.return_value = True
    app = create_app()
    app.state.container = SimpleNamespace(job_service=job_service, captcha_service=captcha_service)
    return TestClient(app).post(
        "/jobs/video-to-markdown",
        files={"file": ("clip.mp4", b"video", "video/mp4")},
        headers={"X-Captcha-Token": "token-1"},
    )


@pytest.fixture
def emptied_samples(tmp_path):
    storage = JobStorage(tmp_path, max_upload_bytes=1)
    storage.samples_dir("job-1").mkdir(parents=True)
    (storage.samples_dir("job-1") / "sample-00000.jpg").write_bytes(b"x")
    storage.delete_samples("job-1")
    return storage


def test_a_model_value_is_a_provider_and_one_of_its_analysis_models(model_choice_outcome):
    assert model_choice_outcome.actual == model_choice_outcome.expected


def test_step_models_read_a_missing_group_as_null(step_model_choices_outcome):
    assert step_model_choices_outcome.actual == step_model_choices_outcome.expected


def test_step_models_are_stored_with_every_group():
    assert to_step_models_value({**NO_STEP_MODELS, AiStepGroup.MOMENTS: GPT_LUNA}) == {
        "moments": {"provider": "openai", "model": "gpt-6-luna"},
        "audio": None,
        "filmAnalysis": None,
        "filmScript": None,
        "filmClone": None,
    }


@pytest.mark.parametrize(
    ("choice", "expected"),
    [
        (CLI_DEFAULT, "Claude (CLI default)"),
        (GEMINI_ARGON, "Gemini 4 Argon"),
        (AiModelChoice(ProviderId.OPENAI, "gpt-retired"), "gpt-retired"),
    ],
)
def test_a_model_label_comes_from_the_catalog_or_falls_back_to_the_id(choice, expected):
    assert to_model_label(choice) == expected


def test_each_provider_has_an_ai_name_for_messages():
    assert [to_ai_name(provider) for provider in (ProviderId.CLAUDE_CLI, ProviderId.GOOGLE)] == [
        "claude",
        "gemini",
    ]
    assert to_ai_name(ProviderId.OPENAI) == "openai"
    assert to_provider_name(ProviderId.GOOGLE) == "Google AI (Gemini, Veo)"


def test_a_group_without_its_own_model_uses_the_model_of_all_steps(found_models):
    assert found_models == {
        AiStepGroup.MOMENTS: CLI_DEFAULT,
        AiStepGroup.AUDIO: CLI_DEFAULT,
        AiStepGroup.FILM_ANALYSIS: GEMINI_ARGON,
        AiStepGroup.FILM_SCRIPT: CLI_DEFAULT,
        AiStepGroup.FILM_CLONE: CLI_DEFAULT,
    }


def test_set_up_providers_pass_the_creation_check(checked_set_up_groups):
    assert [call.args[0] for call in checked_set_up_groups.call_args_list] == [
        ProviderId.CLAUDE_CLI,
        ProviderId.GOOGLE,
    ]


def test_a_group_whose_provider_is_not_set_up_names_the_provider(not_set_up_error):
    assert str(not_set_up_error) == "Google AI (Gemini, Veo) is not set up — open Settings"


def test_a_google_group_on_another_provider_is_refused_with_its_label(
    google_group_on_another_provider_error,
):
    assert isinstance(google_group_on_another_provider_error, GoogleModelRequiredError)
    assert (
        str(google_group_on_another_provider_error)
        == "Film analysis needs a Google AI model — open Settings"
    )


def test_a_google_group_whose_key_is_missing_names_the_provider(google_group_not_set_up_error):
    assert isinstance(google_group_not_set_up_error, AiProviderNotSetUpError)
    assert (
        str(google_group_not_set_up_error)
        == "Google AI (Gemini, Veo) is not set up — open Settings"
    )


def test_a_google_group_with_a_set_up_google_model_passes(checked_google_groups):
    assert [call.args[0] for call in checked_google_groups.call_args_list] == [
        ProviderId.CLAUDE_CLI,
        ProviderId.GOOGLE,
    ]


def test_find_google_model_returns_a_google_model(found_google_model):
    assert found_google_model == GEMINI_ARGON


def test_find_google_model_refuses_another_provider(google_model_refusal):
    assert str(google_model_refusal) == "Audio needs a Google AI model — open Settings"


def test_the_ai_caller_reads_the_google_model_of_a_group(caller_google_model):
    assert caller_google_model.model == GEMINI_ARGON
    caller_google_model.step_models.find_google_model.assert_called_once_with(AiStepGroup.AUDIO)


def test_every_group_has_a_screen_label():
    assert [to_group_label(group) for group in AiStepGroup] == [
        "Key moments",
        "Audio",
        "Film analysis",
        "Film script",
        "Film clone",
    ]


def test_a_creation_refused_for_want_of_a_google_model_answers_409(
    refused_google_upload_response,
):
    assert refused_google_upload_response.status_code == 409
    assert refused_google_upload_response.json() == {
        "detail": "Audio needs a Google AI model — open Settings"
    }


def test_the_ai_caller_reads_the_step_model(ai_caller_calls):
    assert ai_caller_calls.model == GEMINI_ARGON
    ai_caller_calls.step_models.find_model.assert_called_once_with(AiStepGroup.MOMENTS)


def test_the_ai_caller_sends_each_call_to_the_client_of_its_provider(ai_caller_calls):
    ai_caller_calls.gemini_client.ask_for_json.assert_called_once_with(
        "gemini-4-argon", ASK, LIMITS
    )
    ai_caller_calls.claude_client.ask_for_text.assert_called_once_with("default", ASK, LIMITS)
    assert (ai_caller_calls.json_reply, ai_caller_calls.text_reply) == (
        {"moments": []},
        "## Character A",
    )


def test_an_image_is_scaled_to_the_longest_side_and_sent_as_jpeg(scaled_wide_frame):
    assert (scaled_wide_frame.size, scaled_wide_frame.format) == ((480, 240), "JPEG")


def test_an_image_is_encoded_at_the_set_quality(scaled_wide_frame, expected_wide_frame_bytes):
    assert scaled_wide_frame.data == expected_wide_frame_bytes


def test_a_small_image_is_never_upscaled(small_frame):
    assert small_frame.size == (100, 50)


def test_ai_used_entries_carry_the_model_label():
    assert to_labelled_ai_used(
        {"picking_moments": {"provider": "openai", "model": "gpt-6-luna"}}
    ) == {"picking_moments": {"provider": "openai", "model": "gpt-6-luna", "label": "GPT-6 Luna"}}


def test_ai_used_of_a_run_not_yet_saved_is_empty():
    assert to_labelled_ai_used(None) == {}


def test_a_refused_creation_answers_409(refused_upload_response):
    assert refused_upload_response.status_code == 409
    assert refused_upload_response.json() == {"detail": "OpenAI is not set up — open Settings"}


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({}, InputMode.SUBTITLES),
        ({"inputMode": "whole_video"}, InputMode.WHOLE_VIDEO),
        ({"inputMode": "full_video"}, InputMode.FULL_VIDEO),
    ],
)
def test_a_job_without_an_input_mode_uses_subtitles(options, expected):
    assert get_job_input_mode(options) == expected


def test_delete_samples_removes_the_folder(emptied_samples):
    assert not emptied_samples.samples_dir("job-1").exists()
