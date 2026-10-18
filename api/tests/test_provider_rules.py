from dataclasses import dataclass

import pytest

from app.modules.providers.errors import InvalidProviderSettingError
from app.modules.providers.model_catalog import (
    LOCAL_LONGEST_TRACK_S,
    find_catalog_models,
    resolve_model,
)
from app.modules.providers.provider_catalog import (
    PROVIDER_SPECS_BY_ID,
    MediaKind,
    ProviderId,
    default_pacing,
)
from app.modules.providers.provider_rules import (
    ProviderUpdate,
    validate_provider_update,
    validate_routes,
)
from app.modules.providers.secret_box import SecretBox, redact_secret, to_last_visible_chars

FLOW_PROJECT_ID = "6c1b2f4e-91a2-4c5e-9d0f-0a1b2c3d4e5f"


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


def capture_update_error(provider_id: ProviderId, update: ProviderUpdate) -> str:
    with pytest.raises(InvalidProviderSettingError) as caught:
        validate_provider_update(PROVIDER_SPECS_BY_ID[provider_id], update)
    return str(caught.value)


def capture_route_error(routes: dict[str, str]) -> str:
    with pytest.raises(InvalidProviderSettingError) as caught:
        validate_routes(routes)
    return str(caught.value)


@pytest.fixture(
    params=[
        (
            ProviderId.SD_WEBUI,
            ProviderUpdate(api_key="abc"),
            "apiKey does not apply to Stable Diffusion WebUI / Forge",
        ),
        (
            ProviderId.GOOGLE,
            ProviderUpdate(base_url="http://x"),
            "baseUrl does not apply to Google AI (Gemini, Veo)",
        ),
        (
            ProviderId.ACE_STEP,
            ProviderUpdate(models={"music": "x"}),
            "models does not apply to ACE-Step",
        ),
        (
            ProviderId.OPENAI,
            ProviderUpdate(models={"video": "sora"}),
            "models.video does not apply to OpenAI",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(flow_project_id=FLOW_PROJECT_ID),
            "flowProjectId does not apply to fal.ai",
        ),
        (
            ProviderId.OPENAI,
            ProviderUpdate(models={"analysis": "gpt-6-astra"}),
            "models.analysis does not apply to OpenAI",
        ),
        (ProviderId.CLAUDE_CLI, ProviderUpdate(models={}), "models does not apply to Claude CLI"),
        (
            ProviderId.CLAUDE_CLI,
            ProviderUpdate(max_concurrent=2),
            "maxConcurrent does not apply to Claude CLI",
        ),
        (
            ProviderId.CLAUDE_CLI,
            ProviderUpdate(min_interval_s=0),
            "minIntervalS does not apply to Claude CLI",
        ),
        (ProviderId.FAL, ProviderUpdate(api_key="   "), "API key must be 1-500 characters"),
        (ProviderId.FAL, ProviderUpdate(api_key="k" * 501), "API key must be 1-500 characters"),
        (
            ProviderId.SD_WEBUI,
            ProviderUpdate(base_url="localhost:7860"),
            "Base URL must start with http:// or https://",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(models={"image": "midjourney"}),
            "Unknown model 'midjourney' for fal.ai image",
        ),
        (
            ProviderId.GOOGLE_FLOW,
            ProviderUpdate(flow_project_id="not-a-uuid"),
            "Flow project id must be a UUID",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(max_concurrent=0),
            "Concurrent requests must be between 1 and 10",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(max_concurrent=11),
            "Concurrent requests must be between 1 and 10",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(min_interval_s=-1),
            "Interval must be between 0 and 600 seconds",
        ),
        (
            ProviderId.FAL,
            ProviderUpdate(min_interval_s=601),
            "Interval must be between 0 and 600 seconds",
        ),
    ]
)
def rejected_update(request):
    provider_id, update, expected = request.param
    return Outcome(actual=capture_update_error(provider_id, update), expected=expected)


@pytest.fixture(
    params=[
        (
            ProviderId.FAL,
            ProviderUpdate(
                api_key="fal-key", models={"video": "bytedance/seedance-2.5/image-to-video"}
            ),
        ),
        (
            ProviderId.GOOGLE,
            ProviderUpdate(api_key=None, models={"speech": "gemini-3.8-flash-tts"}),
        ),
        (ProviderId.SD_WEBUI, ProviderUpdate(base_url="http://127.0.0.1:7860", max_concurrent=1)),
        (ProviderId.SD_WEBUI, ProviderUpdate(base_url=None)),
        (
            ProviderId.GOOGLE_FLOW,
            ProviderUpdate(flow_project_id=FLOW_PROJECT_ID, min_interval_s=600),
        ),
        (ProviderId.GOOGLE_FLOW, ProviderUpdate(flow_project_id=None, max_concurrent=10)),
    ]
)
def accepted_update(request):
    provider_id, update = request.param
    return validate_provider_update(PROVIDER_SPECS_BY_ID[provider_id], update)


@pytest.fixture(
    params=[
        ({"speech": "midjourney"}, "midjourney cannot serve speech"),
        ({"video": "openai"}, "OpenAI cannot serve video"),
        ({"video": "sd_webui"}, "Stable Diffusion WebUI / Forge cannot serve video"),
        ({"speech": "fal"}, "fal.ai cannot serve speech"),
        ({"image": "elevenlabs"}, "ElevenLabs cannot serve image"),
        ({"lyrics": "yue"}, "Unknown route 'lyrics'"),
        ({"apiImage": "google"}, "Unknown route 'apiImage'"),
        ({"analysis": "google"}, "Unknown route 'analysis'"),
    ]
)
def rejected_route(request):
    routes, expected = request.param
    return Outcome(actual=capture_route_error(routes), expected=expected)


@pytest.fixture
def accepted_routes():
    return validate_routes(
        {"image": "sd_webui", "video": "google_flow", "speech": "elevenlabs", "music": "yue"}
    )


@pytest.fixture(
    params=[
        (ProviderId.SD_WEBUI, MediaKind.IMAGE, None, ("", None)),
        (ProviderId.ACE_STEP, MediaKind.MUSIC, None, ("", None)),
        (ProviderId.FAL, MediaKind.EDIT_IMAGE, None, ("fal-ai/nano-banana-pro/edit", 14)),
        (
            ProviderId.FAL,
            MediaKind.EDIT_IMAGE,
            "fal-ai/flux-pro/kontext",
            ("fal-ai/flux-pro/kontext", 0),
        ),
        (
            ProviderId.FAL,
            MediaKind.EDIT_IMAGE,
            "retired-model",
            ("fal-ai/nano-banana-pro/edit", 14),
        ),
    ]
)
def resolved_model(request):
    provider_id, media_kind, chosen, expected = request.param
    model = resolve_model(provider_id, media_kind, chosen)
    return Outcome(actual=(model.id, model.max_references), expected=expected)


@pytest.fixture
def omni_flash_id():
    model = next(
        model
        for model in find_catalog_models(ProviderId.GOOGLE_FLOW, MediaKind.VIDEO)
        if model.label == "Omni Flash"
    )
    return model.id_for_clip_length(6)


@pytest.fixture(
    params=[
        (ProviderId.GOOGLE_FLOW, (5, 10)),
        (ProviderId.REPLICATE, (2, 0)),
        (ProviderId.YUE, (1, 0)),
    ]
)
def pacing_defaults(request):
    provider_id, expected = request.param
    pacing = default_pacing(PROVIDER_SPECS_BY_ID[provider_id])
    return Outcome(actual=(pacing.max_concurrent, pacing.min_interval_s), expected=expected)


@pytest.fixture
def secret_round_trip():
    box = SecretBox("my passphrase")
    return box.decrypt(box.encrypt("sk-test-0000000000abcd"))


@pytest.fixture
def token_read_with_another_secret():
    return SecretBox("secret B").decrypt(SecretBox("secret A").encrypt("sk-test"))


@pytest.fixture
def box_without_secret():
    return SecretBox("")


@pytest.fixture
def encrypt_without_secret_error(box_without_secret):
    with pytest.raises(RuntimeError) as caught:
        box_without_secret.encrypt("sk-test")
    return str(caught.value)


def test_validate_provider_update_rejects(rejected_update):
    assert rejected_update.actual == rejected_update.expected


def test_validate_provider_update_accepts_fitting_fields(accepted_update):
    assert accepted_update is None


def test_validate_routes_rejects(rejected_route):
    assert rejected_route.actual == rejected_route.expected


def test_validate_routes_accepts_every_choice(accepted_routes):
    assert accepted_routes is None


def test_resolve_model_picks_local_chosen_or_default(resolved_model):
    assert resolved_model.actual == resolved_model.expected


def test_local_music_models_cap_tracks_at_600_s():
    assert (
        resolve_model(ProviderId.YUE, MediaKind.MUSIC, None).longest_track_s
        == LOCAL_LONGEST_TRACK_S
    )


def test_omni_flash_id_carries_the_clip_length(omni_flash_id):
    assert omni_flash_id == "abra_i2v_6s"


def test_default_pacing_per_kind(pacing_defaults):
    assert pacing_defaults.actual == pacing_defaults.expected


def test_secret_box_round_trips_a_key(secret_round_trip):
    assert secret_round_trip == "sk-test-0000000000abcd"


def test_secret_box_cannot_read_a_key_saved_with_another_secret(token_read_with_another_secret):
    assert token_read_with_another_secret is None


def test_secret_box_without_secret_is_not_ready(box_without_secret, encrypt_without_secret_error):
    assert box_without_secret.is_ready is False
    assert box_without_secret.decrypt(b"anything") is None
    assert encrypt_without_secret_error == "SecretBox has no secret key"


def test_redact_secret_and_last_chars():
    assert redact_secret("bad key sk-1234 sent", "sk-1234") == "bad key *** sent"
    assert redact_secret("no key", None) == "no key"
    assert to_last_visible_chars("sk-test-abcd") == "abcd"
