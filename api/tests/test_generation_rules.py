from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.media_generation.media_task import ProviderError, ProviderErrorKind
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.retry_policy import RetryAction, decide_retry
from app.modules.media_generation.task_builder import (
    build_media_task,
    build_pass_task,
    build_segment_task,
    split_references,
)
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind, ProviderId
from app.modules.providers.service import ProviderAccess

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
VEO = CatalogModel("veo-3.1-generate-preview", "Veo 3.1", clip_lengths_s=(4, 6, 8))
NANO = CatalogModel("gemini-3-pro-image", "Nano Banana Pro", max_references=2)
MUSIC = CatalogModel("music_v1", "Music v1", longest_track_s=300)
KONTEXT = CatalogModel("fal-ai/flux-pro/kontext", "Flux Kontext", max_references=0)
LOADED_CHECKPOINT = CatalogModel("", "Loaded checkpoint")


def build_request(media_kind: MediaKind, **overrides) -> GenerationRequest:
    fields = {
        "id": "request-1",
        "kind": GenerationKind.CLONE_SCENE_IMAGE,
        "media_kind": media_kind,
        "provider": ProviderId.GOOGLE.value,
        "prompt": "A pier at dawn",
        "input_paths": {},
        "params": {},
        "status": GenerationStatus.PROCESSING,
        "attempts": 0,
    }
    return GenerationRequest(**{**fields, **overrides})


def build_access(
    model: CatalogModel, media_kind: MediaKind, provider_id: ProviderId = ProviderId.GOOGLE
) -> ProviderAccess:
    return ProviderAccess(
        provider_id=provider_id,
        name="Google AI (Gemini, Veo)",
        api_key="key-1",
        base_url=None,
        models={media_kind: model},
        flow_project_id=None,
    )


def capture_task_error(request: GenerationRequest, access: ProviderAccess) -> ProviderError:
    with pytest.raises(ProviderError) as caught:
        build_media_task(request, access)
    return caught.value


@pytest.fixture(
    params=[
        (ProviderErrorKind.INPUT_EXPIRED, 2, (RetryAction.REQUEUE, 2, NOW, False)),
        (ProviderErrorKind.NOT_CONNECTED, 0, (RetryAction.REQUEUE, 0, NOW, False)),
        (ProviderErrorKind.UNUSUAL_ACTIVITY, 0, (RetryAction.FAIL, 1, None, True)),
        (ProviderErrorKind.FATAL, 1, (RetryAction.FAIL, 2, None, False)),
        (ProviderErrorKind.NO_ANSWER, 0, (RetryAction.FAIL, 1, None, False)),
        (
            ProviderErrorKind.RETRYABLE,
            0,
            (RetryAction.REQUEUE, 1, NOW + timedelta(seconds=20), False),
        ),
        (ProviderErrorKind.RETRYABLE, 4, (RetryAction.FAIL, 5, None, False)),
        (
            ProviderErrorKind.RETRYABLE,
            3,
            (RetryAction.REQUEUE, 4, NOW + timedelta(seconds=160), False),
        ),
        (
            ProviderErrorKind.CAPTCHA,
            4,
            (RetryAction.REQUEUE, 5, NOW + timedelta(seconds=300), False),
        ),
        (ProviderErrorKind.CAPTCHA, 9, (RetryAction.FAIL, 10, None, False)),
    ]
)
def retry_decision(request):
    error_kind, attempts, expected = request.param
    decision = decide_retry(error_kind, attempts, 5, NOW)
    return SimpleNamespace(
        actual=(
            decision.action,
            decision.attempts,
            decision.next_attempt_at,
            decision.pauses_google_flow,
        ),
        expected=expected,
    )


@pytest.fixture
def image_task():
    request = build_request(
        MediaKind.IMAGE,
        input_paths={"references": ["a.png", "b.png", "c.png"], "sourceImage": "src.png"},
        params={"aspect": "9:16", "referenceNames": ["Ann", "Bao", "Chi"]},
    )
    return build_media_task(request, build_access(NANO, MediaKind.IMAGE))


@pytest.fixture
def first_pass_task(image_task):
    return build_pass_task(image_task, 1, None)


@pytest.fixture
def third_pass_task(image_task):
    return build_pass_task(image_task, 3, Path("image.pass2.png"))


@pytest.fixture
def kontext_task():
    request = build_request(
        MediaKind.EDIT_IMAGE,
        input_paths={"references": ["a.png", "b.png"], "sourceImage": "src.png"},
    )
    return build_media_task(request, build_access(KONTEXT, MediaKind.EDIT_IMAGE, ProviderId.FAL))


@pytest.fixture
def composite_task():
    request = build_request(
        MediaKind.IMAGE,
        input_paths={"references": ["a.png", "b.png", "c.png"]},
        params={"referenceKinds": ["character", "location", "character"]},
    )
    return build_media_task(
        request, build_access(LOADED_CHECKPOINT, MediaKind.IMAGE, ProviderId.SD_WEBUI)
    )


@pytest.fixture
def video_task():
    request = build_request(
        MediaKind.VIDEO,
        input_paths={"startFrame": "frame.png"},
        params={"clipLengthS": 6, "aspect": "16:9"},
    )
    return build_media_task(request, build_access(VEO, MediaKind.VIDEO))


@pytest.fixture
def long_scene_task():
    request = build_request(
        MediaKind.VIDEO, input_paths={"startFrame": "frame.png"}, params={"clipLengthS": 15}
    )
    return build_media_task(request, build_access(VEO, MediaKind.VIDEO))


@pytest.fixture
def second_segment_task(long_scene_task):
    return build_segment_task(long_scene_task, 2, Path("segments/1-last.png"))


@pytest.fixture(params=[(400, 300), (120, 120)])
def capped_track(request):
    asked_s, expected = request.param
    built = build_media_task(
        build_request(MediaKind.MUSIC, params={"minLengthS": asked_s}),
        build_access(MUSIC, MediaKind.MUSIC),
    )
    return SimpleNamespace(actual=built.task.min_length_s, expected=expected)


def test_decide_retry_follows_the_retry_table(retry_decision):
    assert retry_decision.actual == retry_decision.expected


def test_image_task_past_the_reference_limit_runs_one_pass_per_reference(image_task):
    assert image_task.pass_count == 3
    assert [str(path) for path in image_task.task.inputs.references] == [
        "a.png",
        "b.png",
        "c.png",
    ]
    assert image_task.task.aspect == "9:16"
    assert image_task.sent_params == {
        "aspect": "9:16",
        "referenceNames": ["Ann", "Bao", "Chi"],
        "model": "gemini-3-pro-image",
    }


def test_first_pass_sends_the_request_with_the_first_reference(first_pass_task):
    assert first_pass_task.prompt == "A pier at dawn"
    assert [str(path) for path in first_pass_task.inputs.references] == ["a.png"]
    assert str(first_pass_task.inputs.source_image) == "src.png"


def test_later_pass_edits_the_previous_result_with_the_next_reference(third_pass_task):
    assert third_pass_task.prompt == (
        "Keep the scene, the framing and everyone else unchanged. Make Chi look like the "
        "reference image."
    )
    assert [str(path) for path in third_pass_task.inputs.references] == ["c.png"]
    assert str(third_pass_task.inputs.source_image) == "image.pass2.png"


def test_model_taking_no_reference_gets_the_source_only(kontext_task):
    assert kontext_task.pass_count == 1
    assert kontext_task.task.inputs.references == ()
    assert str(kontext_task.task.inputs.source_image) == "src.png"
    assert kontext_task.sent_params["droppedReferences"] == ["a.png", "b.png"]


def test_stable_diffusion_keeps_every_reference_in_one_pass(composite_task):
    assert composite_task.pass_count == 1
    assert len(composite_task.task.inputs.references) == 3
    assert composite_task.task.reference_kinds == ("character", "location", "character")


def test_video_task_carries_the_clip_length_and_start_frame(video_task):
    assert video_task.task.clip_length_s == 6
    assert str(video_task.task.inputs.start_frame) == "frame.png"
    assert "droppedReferences" not in video_task.sent_params


def test_a_scene_longer_than_any_clip_asks_for_the_longest_clip_first(long_scene_task):
    assert long_scene_task.task.clip_length_s == 8
    assert long_scene_task.clip_plan.segment_lengths_s == (8, 8)


def test_a_later_segment_starts_from_the_last_frame_with_its_window(second_segment_task):
    assert second_segment_task.prompt == (
        "Part 2 of 2. Show 8-15s of this shot. Continue from the start image.\nA pier at dawn"
    )
    assert second_segment_task.inputs.start_frame == Path("segments/1-last.png")
    assert second_segment_task.clip_length_s == 8


def test_a_scene_one_clip_covers_keeps_the_task_as_built(video_task):
    assert build_segment_task(video_task, 1, None) is video_task.task


def test_a_task_without_a_clip_length_has_no_segments(composite_task):
    assert composite_task.clip_plan is None
    assert build_segment_task(composite_task, 1, None) is composite_task.task


def test_music_length_is_capped_at_the_longest_track(capped_track):
    assert capped_track.actual == capped_track.expected


def test_split_references_without_a_limit_keeps_all():
    assert split_references(["a", "b"], None) == (["a", "b"], [])


ELEVEN_V4 = CatalogModel("eleven_v4", "Eleven v4")
GEMINI_TTS = CatalogModel("gemini-3.8-flash-tts", "Gemini 3.8 Flash TTS")
VT_SHORT = {"voiceName": "VT-SHORT", "sampleDurationS": 20.4}
VT_LONG = {"voiceName": "VT-LONG", "sampleDurationS": 70}


@pytest.fixture(
    params=[
        (
            ProviderId.ELEVENLABS,
            VT_SHORT,
            {},
            "ElevenLabs needs a voice sample of at least 60 s; 'VT-SHORT' is 20 s",
        ),
        (
            ProviderId.GOOGLE,
            VT_SHORT,
            {},
            "Google AI needs a consent clip for 'VT-SHORT' — add it in the library",
        ),
        (
            ProviderId.GOOGLE,
            VT_LONG,
            {"consentClip": "consent.wav"},
            "Google AI needs a voice sample of 10-30 s; 'VT-LONG' is 70 s",
        ),
    ]
)
def refused_voice(request):
    provider_id, params, input_paths, expected = request.param
    model = ELEVEN_V4 if provider_id is ProviderId.ELEVENLABS else GEMINI_TTS
    error = capture_task_error(
        build_request(
            MediaKind.SPEECH,
            params=params,
            input_paths={"voiceSample": "sample.wav", **input_paths},
        ),
        build_access(model, MediaKind.SPEECH, provider_id),
    )
    return SimpleNamespace(error=error, expected=expected)


@pytest.fixture(
    params=[
        (ProviderId.ELEVENLABS, ELEVEN_V4, VT_LONG, {}),
        (
            ProviderId.GOOGLE,
            GEMINI_TTS,
            {**VT_SHORT, "sampleDurationS": 25},
            {"consentClip": "c.wav"},
        ),
        (ProviderId.OMNIVOICE, CatalogModel("", "Loaded model"), VT_SHORT, {}),
    ]
)
def accepted_voice_task(request):
    provider_id, model, params, input_paths = request.param
    return build_media_task(
        build_request(
            MediaKind.SPEECH,
            params={**params, "providerVoiceId": "voice-9", "sampleText": "Xin chào"},
            input_paths={"voiceSample": "sample.wav", **input_paths},
        ),
        build_access(model, MediaKind.SPEECH, provider_id),
    )


def test_voice_short_of_the_provider_needs_fails_at_once(refused_voice):
    assert str(refused_voice.error) == refused_voice.expected
    assert refused_voice.error.kind is ProviderErrorKind.FATAL


def test_voice_that_fits_carries_the_sample_and_the_provider_copy(accepted_voice_task):
    assert str(accepted_voice_task.task.inputs.voice_sample) == "sample.wav"
    assert accepted_voice_task.task.provider_voice_id == "voice-9"
    assert accepted_voice_task.task.sample_text == "Xin chào"
