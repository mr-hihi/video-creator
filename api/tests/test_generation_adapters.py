import base64
import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from app.modules.media_generation.adapters.elevenlabs import ElevenLabsAdapter
from app.modules.media_generation.adapters.fal import FalAdapter
from app.modules.media_generation.adapters.google_ai import GoogleAiAdapter
from app.modules.media_generation.adapters.http_support import download_result
from app.modules.media_generation.adapters.local_audio import LocalAudioAdapter
from app.modules.media_generation.adapters.openai_images import OpenAiImageAdapter
from app.modules.media_generation.adapters.replicate import ReplicateAdapter
from app.modules.media_generation.adapters.sd_composite import build_composite
from app.modules.media_generation.adapters.sd_webui import SdWebUiAdapter, SdWebUiConfig
from app.modules.media_generation.media_task import (
    MediaInputs,
    MediaTask,
    ProviderError,
    ProviderErrorKind,
)
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind

API_KEY = "key-abcd-9876"
RED = (220, 20, 20)
BLUE = (20, 20, 220)
GREEN = (20, 180, 20)
GREY = (128, 128, 128)
PNG_BYTES = b"\x89PNG-result"
NANO = CatalogModel("gemini-3-pro-image", "Nano Banana Pro", max_references=11)
VEO = CatalogModel("veo-3.1-generate-preview", "Veo 3.1", clip_lengths_s=(4, 6, 8))
FAL_NANO = CatalogModel(
    "fal-ai/nano-banana-pro",
    "Nano Banana Pro",
    max_references=14,
    with_references_id="fal-ai/nano-banana-pro/edit",
)
FAL_KONTEXT = CatalogModel("fal-ai/flux-pro/kontext", "Flux Kontext", max_references=0)
KLING = CatalogModel("kwaivgi/kling-v3-video", "Kling 3", clip_lengths_s=(4, 6, 8, 10))
GPT_IMAGE = CatalogModel("gpt-image-2.5-sunburst", "GPT Image 2.5", max_references=4)
LOADED_CHECKPOINT = CatalogModel("", "Loaded checkpoint")
ELEVEN_V4 = CatalogModel("eleven_v4", "Eleven v4")
ELEVEN_MUSIC = CatalogModel("music_v2_5", "Music v2.5", longest_track_s=300)
GEMINI_TTS = CatalogModel("gemini-3.8-flash-tts", "Gemini 3.8 Flash TTS")
LOADED_MODEL = CatalogModel("", "Loaded model")
WAV_BYTES = b"RIFF-wav"
MP3_BYTES = b"ID3-mp3"


@dataclass
class FakeServer:
    answer: Callable[[httpx.Request], httpx.Response]
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        return self.answer(request)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handle))


def build_task(model: CatalogModel, media_kind: MediaKind, **overrides) -> MediaTask:
    fields = {
        "request_id": "request-1",
        "media_kind": media_kind,
        "model": model,
        "api_key": API_KEY,
        "base_url": None,
        "prompt": "A pier at dawn",
        "inputs": MediaInputs(),
    }
    return MediaTask(**{**fields, **overrides})


def write_png(path: Path, color: tuple[int, int, int], size: tuple[int, int]) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def json_body(request: httpx.Request) -> dict:
    return json.loads(request.content)


def capture_error(call: Callable[[], object]) -> ProviderError:
    with pytest.raises(ProviderError) as caught:
        call()
    return caught.value


def decode_png(encoded: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")


@pytest.fixture
def red_png(tmp_path):
    return write_png(tmp_path / "red.png", RED, (100, 200))


@pytest.fixture
def blue_png(tmp_path):
    return write_png(tmp_path / "blue.png", BLUE, (100, 200))


@pytest.fixture
def green_png(tmp_path):
    return write_png(tmp_path / "green.png", GREEN, (320, 180))


@pytest.fixture
def gemini_image_call(red_png):
    server = FakeServer(
        lambda request: httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/jpeg",
                                        "data": base64.b64encode(PNG_BYTES).decode(),
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )
    )
    task = build_task(
        NANO, MediaKind.IMAGE, inputs=MediaInputs(references=(red_png,)), aspect="9:16"
    )
    outcome = GoogleAiAdapter(server.client(), 30).submit(task)
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


@pytest.fixture
def gemini_blocked_error():
    server = FakeServer(
        lambda request: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    )
    adapter = GoogleAiAdapter(server.client(), 30)
    return capture_error(lambda: adapter.submit(build_task(NANO, MediaKind.IMAGE)))


@pytest.fixture(
    params=[
        (401, ProviderErrorKind.FATAL),
        (409, ProviderErrorKind.FATAL),
        (429, ProviderErrorKind.RETRYABLE),
        (503, ProviderErrorKind.RETRYABLE),
    ]
)
def gemini_http_error(request):
    status_code, expected_kind = request.param
    server = FakeServer(
        lambda _request: httpx.Response(
            status_code, json={"error": {"message": f"bad key {API_KEY}"}}
        )
    )
    adapter = GoogleAiAdapter(server.client(), 30)
    error = capture_error(lambda: adapter.submit(build_task(NANO, MediaKind.IMAGE)))
    return SimpleNamespace(error=error, expected_kind=expected_kind)


def raise_read_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused", request=request)


@pytest.fixture(
    params=[
        (raise_read_timeout, "Google AI timed out: timed out"),
        (raise_connect_error, "Google AI could not be reached: Connection refused"),
    ]
)
def unanswered_send_error(request):
    answer, expected_message = request.param
    adapter = GoogleAiAdapter(FakeServer(answer).client(), 30)
    error = capture_error(lambda: adapter.submit(build_task(NANO, MediaKind.IMAGE)))
    return SimpleNamespace(error=error, expected_message=expected_message)


@pytest.fixture(
    params=[
        (
            lambda request: httpx.Response(503),
            ProviderErrorKind.RETRYABLE,
            "Could not download the result: HTTP 503",
        ),
        (
            lambda request: httpx.Response(404),
            ProviderErrorKind.FATAL,
            "Could not download the result: HTTP 404",
        ),
        (
            raise_read_timeout,
            ProviderErrorKind.NO_ANSWER,
            "Could not download the result: timed out",
        ),
    ]
)
def download_error(request):
    answer, expected_kind, expected_message = request.param
    client = FakeServer(answer).client()
    error = capture_error(
        lambda: download_result(client, "https://cdn.example.com/clip.mp4", "mp4", None)
    )
    return SimpleNamespace(
        error=error, expected_kind=expected_kind, expected_message=expected_message
    )


@pytest.fixture
def veo_start(red_png):
    server = FakeServer(lambda request: httpx.Response(200, json={"name": "operations/op-1"}))
    task = build_task(
        VEO,
        MediaKind.VIDEO,
        inputs=MediaInputs(start_frame=red_png),
        aspect="16:9",
        clip_length_s=6,
    )
    outcome = GoogleAiAdapter(server.client(), 30).submit(task)
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


def answer_veo_operation(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/files/clip.mp4"):
        return httpx.Response(200, content=b"mp4-bytes", headers={"content-type": "video/mp4"})
    return httpx.Response(
        200,
        json={
            "done": True,
            "response": {
                "generateVideoResponse": {
                    "generatedSamples": [
                        {
                            "video": {
                                "uri": "https://generativelanguage.googleapis.com/files/clip.mp4"
                            }
                        }
                    ]
                }
            },
        },
    )


@pytest.fixture
def veo_poll_done():
    server = FakeServer(answer_veo_operation)
    outcome = GoogleAiAdapter(server.client(), 30).poll(
        build_task(VEO, MediaKind.VIDEO), "operations/op-1"
    )
    return SimpleNamespace(outcome=outcome, requests=server.requests)


@pytest.fixture
def veo_poll_pending():
    server = FakeServer(lambda request: httpx.Response(200, json={"done": False}))
    return GoogleAiAdapter(server.client(), 30).poll(
        build_task(VEO, MediaKind.VIDEO), "operations/op-1"
    )


@pytest.fixture
def veo_filtered_error():
    server = FakeServer(
        lambda request: httpx.Response(
            200,
            json={
                "done": True,
                "response": {"generateVideoResponse": {"raiMediaFilteredReasons": ["violence"]}},
            },
        )
    )
    adapter = GoogleAiAdapter(server.client(), 30)
    return capture_error(lambda: adapter.poll(build_task(VEO, MediaKind.VIDEO), "operations/op-1"))


@pytest.fixture
def fal_reference_submit(red_png, blue_png):
    server = FakeServer(
        lambda request: httpx.Response(
            200, json={"response_url": "https://queue.fal.run/fal-ai/requests/r-1"}
        )
    )
    task = build_task(FAL_NANO, MediaKind.IMAGE, inputs=MediaInputs(references=(red_png, blue_png)))
    outcome = FalAdapter(server.client(), 30).submit(task)
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


@pytest.fixture
def fal_kontext_request(red_png):
    server = FakeServer(
        lambda request: httpx.Response(200, json={"response_url": "https://queue.fal.run/r-2"})
    )
    task = build_task(FAL_KONTEXT, MediaKind.EDIT_IMAGE, inputs=MediaInputs(source_image=red_png))
    FalAdapter(server.client(), 30).submit(task)
    return server.requests[0]


def answer_fal_queue(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/status"):
        return httpx.Response(200, json={"status": "COMPLETED"})
    if request.url.host == "cdn.fal.media":
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})
    return httpx.Response(200, json={"images": [{"url": "https://cdn.fal.media/out.png"}]})


@pytest.fixture
def fal_poll_done():
    server = FakeServer(answer_fal_queue)
    outcome = FalAdapter(server.client(), 30).poll(
        build_task(FAL_NANO, MediaKind.IMAGE), "https://queue.fal.run/fal-ai/requests/r-1"
    )
    return SimpleNamespace(outcome=outcome, requests=server.requests)


@pytest.fixture
def fal_poll_pending():
    server = FakeServer(lambda request: httpx.Response(200, json={"status": "IN_PROGRESS"}))
    return FalAdapter(server.client(), 30).poll(
        build_task(FAL_NANO, MediaKind.IMAGE), "https://queue.fal.run/fal-ai/requests/r-1"
    )


@pytest.fixture
def replicate_clip_submit(red_png):
    server = FakeServer(lambda request: httpx.Response(201, json={"id": "pred-1"}))
    task = build_task(
        KLING, MediaKind.VIDEO, inputs=MediaInputs(start_frame=red_png), clip_length_s=10
    )
    outcome = ReplicateAdapter(server.client(), 30).submit(task)
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


def answer_replicate_prediction(request: httpx.Request) -> httpx.Response:
    if request.url.host == "replicate.delivery":
        return httpx.Response(200, content=b"mp4-bytes", headers={"content-type": "video/mp4"})
    return httpx.Response(
        200, json={"status": "succeeded", "output": ["https://replicate.delivery/clip.mp4"]}
    )


@pytest.fixture
def replicate_poll_done():
    server = FakeServer(answer_replicate_prediction)
    return ReplicateAdapter(server.client(), 30).poll(build_task(KLING, MediaKind.VIDEO), "pred-1")


@pytest.fixture
def replicate_failed_error():
    server = FakeServer(
        lambda request: httpx.Response(200, json={"status": "failed", "error": "GPU lost"})
    )
    adapter = ReplicateAdapter(server.client(), 30)
    return capture_error(lambda: adapter.poll(build_task(KLING, MediaKind.VIDEO), "pred-1"))


def answer_openai_image(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode()}]})


@pytest.fixture
def openai_generation():
    server = FakeServer(answer_openai_image)
    outcome = OpenAiImageAdapter(server.client(), 30).submit(
        build_task(GPT_IMAGE, MediaKind.IMAGE, aspect="9:16")
    )
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


@pytest.fixture
def openai_edit_request(red_png, blue_png):
    server = FakeServer(answer_openai_image)
    OpenAiImageAdapter(server.client(), 30).submit(
        build_task(
            GPT_IMAGE,
            MediaKind.EDIT_IMAGE,
            inputs=MediaInputs(source_image=red_png, references=(blue_png,)),
        )
    )
    return server.requests[0]


def answer_sd(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"images": [base64.b64encode(PNG_BYTES).decode()]})


def submit_to_sd(task: MediaTask) -> SimpleNamespace:
    server = FakeServer(answer_sd)
    adapter = SdWebUiAdapter(
        server.client(),
        SdWebUiConfig(timeout_sec=60, denoising_strength=0.6, composite_denoising_strength=0.75),
    )
    outcome = adapter.submit(task)
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


@pytest.fixture
def sd_text_call():
    return submit_to_sd(
        build_task(LOADED_CHECKPOINT, MediaKind.IMAGE, base_url="http://127.0.0.1:7860/")
    )


@pytest.fixture
def sd_source_call(red_png):
    return submit_to_sd(
        build_task(
            LOADED_CHECKPOINT,
            MediaKind.EDIT_IMAGE,
            base_url="http://127.0.0.1:7860",
            inputs=MediaInputs(source_image=red_png),
        )
    )


@pytest.fixture
def sd_composite_call(red_png, blue_png):
    call = submit_to_sd(
        build_task(
            LOADED_CHECKPOINT,
            MediaKind.IMAGE,
            base_url="http://127.0.0.1:7860",
            inputs=MediaInputs(references=(red_png, blue_png)),
        )
    )
    body = json_body(call.request)
    return SimpleNamespace(
        request=call.request, body=body, init_image=decode_png(body["init_images"][0])
    )


@pytest.fixture
def grey_composite(red_png, blue_png):
    return Image.open(
        io.BytesIO(build_composite((1344, 768), None, (red_png, blue_png), ("character",) * 2))
    )


@pytest.fixture
def location_composite(red_png, green_png):
    return Image.open(
        io.BytesIO(
            build_composite((768, 1344), None, (red_png, green_png), ("character", "location"))
        )
    )


@pytest.fixture
def edit_composite(red_png, green_png, blue_png):
    return Image.open(
        io.BytesIO(
            build_composite((1344, 768), blue_png, (red_png, green_png), ("character", "location"))
        )
    )


def test_gemini_image_sends_prompt_references_and_aspect(gemini_image_call):
    body = json_body(gemini_image_call.request)
    parts = body["contents"][0]["parts"]
    assert str(gemini_image_call.request.url).endswith("/models/gemini-3-pro-image:generateContent")
    assert gemini_image_call.request.headers["x-goog-api-key"] == API_KEY
    assert parts[0] == {"text": "A pier at dawn"}
    assert parts[1]["inlineData"]["mimeType"] == "image/png"
    assert body["generationConfig"]["imageConfig"] == {"aspectRatio": "9:16"}
    assert gemini_image_call.outcome.result.content == PNG_BYTES
    assert gemini_image_call.outcome.result.file_extension == "jpg"


def test_gemini_blocked_prompt_fails_at_once(gemini_blocked_error):
    assert str(gemini_blocked_error) == "Blocked by the content filter: SAFETY"
    assert gemini_blocked_error.kind is ProviderErrorKind.FATAL


def test_gemini_http_error_hides_the_key_and_picks_the_retry_kind(gemini_http_error):
    assert API_KEY not in str(gemini_http_error.error)
    assert gemini_http_error.error.kind is gemini_http_error.expected_kind


def test_send_without_an_answer_fails_without_a_retry(unanswered_send_error):
    assert str(unanswered_send_error.error) == unanswered_send_error.expected_message
    assert unanswered_send_error.error.kind is ProviderErrorKind.NO_ANSWER


def test_download_error_is_retried_only_on_a_server_error(download_error):
    assert str(download_error.error) == download_error.expected_message
    assert download_error.error.kind is download_error.expected_kind


def test_veo_start_sends_the_start_frame_and_returns_the_operation(veo_start):
    body = json_body(veo_start.request)
    assert str(veo_start.request.url).endswith(
        "/models/veo-3.1-generate-preview:predictLongRunning"
    )
    assert body["instances"][0]["image"]["mimeType"] == "image/png"
    assert body["parameters"] == {"aspectRatio": "16:9", "durationSeconds": 6}
    assert veo_start.outcome.external_id == "operations/op-1"


def test_veo_poll_downloads_the_clip_with_the_key(veo_poll_done):
    assert veo_poll_done.outcome.is_done is True
    assert veo_poll_done.outcome.result.content == b"mp4-bytes"
    assert veo_poll_done.outcome.result.file_extension == "mp4"
    assert veo_poll_done.requests[1].headers["x-goog-api-key"] == API_KEY


def test_veo_poll_not_done_keeps_waiting(veo_poll_pending):
    assert veo_poll_pending.is_done is False


def test_veo_filtered_clip_fails_at_once(veo_filtered_error):
    assert str(veo_filtered_error) == "Blocked by the content filter: violence"
    assert veo_filtered_error.kind is ProviderErrorKind.FATAL


def test_fal_image_with_references_uses_the_reference_model(fal_reference_submit):
    body = json_body(fal_reference_submit.request)
    assert str(fal_reference_submit.request.url) == (
        "https://queue.fal.run/fal-ai/nano-banana-pro/edit"
    )
    assert fal_reference_submit.request.headers["authorization"] == f"Key {API_KEY}"
    assert len(body["image_urls"]) == 2
    assert body["image_urls"][0].startswith("data:image/png;base64,")
    assert fal_reference_submit.outcome.external_id == ("https://queue.fal.run/fal-ai/requests/r-1")


def test_fal_kontext_gets_one_source_image(fal_kontext_request):
    body = json_body(fal_kontext_request)
    assert str(fal_kontext_request.url) == "https://queue.fal.run/fal-ai/flux-pro/kontext"
    assert body["image_url"].startswith("data:image/png;base64,")
    assert "image_urls" not in body


def test_fal_poll_downloads_the_finished_image(fal_poll_done):
    assert [str(request.url) for request in fal_poll_done.requests] == [
        "https://queue.fal.run/fal-ai/requests/r-1/status",
        "https://queue.fal.run/fal-ai/requests/r-1",
        "https://cdn.fal.media/out.png",
    ]
    assert fal_poll_done.outcome.result.content == PNG_BYTES


def test_fal_poll_in_progress_keeps_waiting(fal_poll_pending):
    assert fal_poll_pending.is_done is False


def test_replicate_clip_uses_the_model_start_frame_field(replicate_clip_submit):
    body = json_body(replicate_clip_submit.request)
    assert str(replicate_clip_submit.request.url) == (
        "https://api.replicate.com/v1/models/kwaivgi/kling-v3-video/predictions"
    )
    assert body["input"]["start_image"].startswith("data:image/png;base64,")
    assert body["input"]["duration"] == 10
    assert replicate_clip_submit.outcome.external_id == "pred-1"


def test_replicate_poll_downloads_the_first_output(replicate_poll_done):
    assert replicate_poll_done.result.content == b"mp4-bytes"
    assert replicate_poll_done.result.file_extension == "mp4"


def test_replicate_failed_prediction_fails_at_once(replicate_failed_error):
    assert str(replicate_failed_error) == "Replicate: GPU lost"
    assert replicate_failed_error.kind is ProviderErrorKind.FATAL


def test_openai_without_images_calls_generations(openai_generation):
    assert str(openai_generation.request.url) == "https://api.openai.com/v1/images/generations"
    assert json_body(openai_generation.request) == {
        "model": "gpt-image-2.5-sunburst",
        "prompt": "A pier at dawn",
        "size": "864x1536",
        "n": 1,
    }
    assert openai_generation.outcome.result.content == PNG_BYTES


def test_openai_with_images_calls_edits_with_every_image(openai_edit_request):
    assert str(openai_edit_request.url) == "https://api.openai.com/v1/images/edits"
    assert openai_edit_request.headers["authorization"] == f"Bearer {API_KEY}"
    assert openai_edit_request.content.count(b'name="image[]"') == 2


def test_sd_without_images_calls_txt2img(sd_text_call):
    assert str(sd_text_call.request.url) == "http://127.0.0.1:7860/sdapi/v1/txt2img"
    assert json_body(sd_text_call.request) == {
        "prompt": "A pier at dawn",
        "width": 1344,
        "height": 768,
    }
    assert sd_text_call.outcome.result.content == PNG_BYTES


def test_sd_source_without_references_uses_the_source_as_init_image(sd_source_call, red_png):
    body = json_body(sd_source_call.request)
    assert str(sd_source_call.request.url) == "http://127.0.0.1:7860/sdapi/v1/img2img"
    assert base64.b64decode(body["init_images"][0]) == red_png.read_bytes()
    assert body["denoising_strength"] == 0.6


def test_sd_references_send_one_composite(sd_composite_call):
    assert str(sd_composite_call.request.url) == "http://127.0.0.1:7860/sdapi/v1/img2img"
    assert sd_composite_call.body["denoising_strength"] == 0.75
    assert sd_composite_call.init_image.size == (1344, 768)


def test_composite_without_location_pastes_references_on_grey(grey_composite):
    assert grey_composite.size == (1344, 768)
    assert grey_composite.getpixel((5, 5)) == GREY
    assert grey_composite.getpixel((672 - 100, 700)) == RED
    assert grey_composite.getpixel((672 + 100, 700)) == BLUE


def test_composite_uses_the_location_reference_as_the_base(location_composite):
    assert location_composite.size == (768, 1344)
    assert location_composite.getpixel((5, 5)) == GREEN
    assert location_composite.getpixel((384, 1300)) == RED


def test_composite_of_an_edit_uses_the_current_image_as_the_base(edit_composite):
    assert edit_composite.getpixel((5, 5)) == BLUE
    assert edit_composite.getpixel((5, 760)) == BLUE


@pytest.fixture
def voice_sample(tmp_path):
    sample = tmp_path / "sample.wav"
    sample.write_bytes(b"RIFF-sample")
    return sample


@pytest.fixture
def consent_clip(tmp_path):
    clip = tmp_path / "consent.wav"
    clip.write_bytes(b"RIFF-consent")
    return clip


def answer_elevenlabs(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v1/voices/add":
        return httpx.Response(200, json={"voice_id": "el-voice-1", "requires_verification": False})
    return httpx.Response(200, content=MP3_BYTES, headers={"content-type": "audio/mpeg"})


@pytest.fixture
def elevenlabs_two_narrations(voice_sample):
    server = FakeServer(answer_elevenlabs)
    adapter = ElevenLabsAdapter(server.client(), 30)
    task = build_task(
        ELEVEN_V4,
        MediaKind.SPEECH,
        prompt="Ngày xưa có một làng chài",
        inputs=MediaInputs(voice_sample=voice_sample),
        voice_name="VT-LONG",
        language="vi",
    )
    outcomes = [adapter.submit(task), adapter.submit(task)]
    return SimpleNamespace(outcomes=outcomes, requests=server.requests)


@pytest.fixture
def elevenlabs_known_voice_requests(voice_sample):
    server = FakeServer(answer_elevenlabs)
    ElevenLabsAdapter(server.client(), 30).submit(
        build_task(
            ELEVEN_V4,
            MediaKind.SPEECH,
            inputs=MediaInputs(voice_sample=voice_sample),
            provider_voice_id="el-voice-stored",
        )
    )
    return server.requests


@pytest.fixture
def elevenlabs_music():
    server = FakeServer(answer_elevenlabs)
    outcome = ElevenLabsAdapter(server.client(), 30).submit(
        build_task(ELEVEN_MUSIC, MediaKind.MUSIC, prompt="Calm sea shanty", min_length_s=300)
    )
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


def answer_gemini_speech(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/voices"):
        return httpx.Response(200, json={"id": "voice_abc"})
    return httpx.Response(
        200,
        json={
            "steps": [
                {"type": "user_input"},
                {
                    "type": "model_output",
                    "content": [{"type": "audio", "data": base64.b64encode(WAV_BYTES).decode()}],
                },
            ]
        },
    )


@pytest.fixture
def gemini_narration(voice_sample, consent_clip):
    server = FakeServer(answer_gemini_speech)
    outcome = GoogleAiAdapter(server.client(), 30).submit(
        build_task(
            GEMINI_TTS,
            MediaKind.SPEECH,
            prompt="Once upon a time",
            inputs=MediaInputs(voice_sample=voice_sample, consent_clip=consent_clip),
            voice_name="VT-MID",
        )
    )
    return SimpleNamespace(outcome=outcome, requests=server.requests)


def answer_local_audio(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=WAV_BYTES, headers={"content-type": "audio/wav"})


@pytest.fixture
def omnivoice_narration(voice_sample):
    server = FakeServer(answer_local_audio)
    outcome = LocalAudioAdapter(server.client(), 1800, "OmniVoice").submit(
        build_task(
            LOADED_MODEL,
            MediaKind.SPEECH,
            base_url="http://127.0.0.1:8010/",
            prompt="Ngày xưa",
            inputs=MediaInputs(voice_sample=voice_sample),
            language="vi",
            sample_text="Xin chào các bạn",
        )
    )
    return SimpleNamespace(outcome=outcome, request=server.requests[0])


@pytest.fixture
def ace_step_music_request():
    server = FakeServer(answer_local_audio)
    LocalAudioAdapter(server.client(), 1800, "ACE-Step").submit(
        build_task(
            LOADED_MODEL,
            MediaKind.MUSIC,
            base_url="http://127.0.0.1:8001",
            prompt="Calm sea shanty",
            min_length_s=95,
        )
    )
    return server.requests[0]


@pytest.fixture
def local_server_error(voice_sample):
    server = FakeServer(lambda request: httpx.Response(500, text="CUDA out of memory\n"))
    adapter = LocalAudioAdapter(server.client(), 1800, "OmniVoice")
    task = build_task(
        LOADED_MODEL,
        MediaKind.SPEECH,
        base_url="http://127.0.0.1:8010",
        inputs=MediaInputs(voice_sample=voice_sample),
    )
    return capture_error(lambda: adapter.submit(task))


def test_elevenlabs_makes_the_voice_copy_once(elevenlabs_two_narrations):
    paths = [request.url.path for request in elevenlabs_two_narrations.requests]
    assert paths == [
        "/v1/voices/add",
        "/v1/text-to-speech/el-voice-1",
        "/v1/text-to-speech/el-voice-1",
    ]
    assert elevenlabs_two_narrations.requests[0].headers["xi-api-key"] == API_KEY
    assert b'name="files"' in elevenlabs_two_narrations.requests[0].content
    assert json_body(elevenlabs_two_narrations.requests[1]) == {
        "text": "Ngày xưa có một làng chài",
        "model_id": "eleven_v4",
        "language_code": "vi",
    }
    assert [outcome.result.provider_voice_id for outcome in elevenlabs_two_narrations.outcomes] == [
        "el-voice-1",
        "el-voice-1",
    ]
    assert elevenlabs_two_narrations.outcomes[0].result.file_extension == "mp3"


def test_elevenlabs_reuses_the_stored_voice_copy(elevenlabs_known_voice_requests):
    assert [request.url.path for request in elevenlabs_known_voice_requests] == [
        "/v1/text-to-speech/el-voice-stored"
    ]


def test_elevenlabs_music_asks_for_an_instrumental_of_the_length(elevenlabs_music):
    assert elevenlabs_music.request.url.path == "/v1/music"
    assert json_body(elevenlabs_music.request) == {
        "prompt": "Calm sea shanty",
        "model_id": "music_v2_5",
        "force_instrumental": True,
        "music_length_ms": 300000,
    }
    assert elevenlabs_music.outcome.result.content == MP3_BYTES


def test_gemini_narration_replicates_the_voice_then_speaks(gemini_narration):
    voice_request, speech_request = gemini_narration.requests
    voice = json_body(voice_request)["voice"]
    assert voice_request.url.path == "/v1beta/voices"
    assert voice["type"] == "replicated"
    assert voice["display_name"] == "VT-MID"
    assert voice["replicated"]["consent_audio"]["mime_type"] == "audio/x-wav"
    assert speech_request.url.path == "/v1beta/interactions"
    assert json_body(speech_request)["generation_config"] == {
        "speech_config": [{"voice": "voice_abc"}]
    }
    assert gemini_narration.outcome.result.content == WAV_BYTES
    assert gemini_narration.outcome.result.provider_voice_id == "voice_abc"


def test_omnivoice_gets_text_language_sample_and_sample_text(omnivoice_narration):
    content = omnivoice_narration.request.content
    assert str(omnivoice_narration.request.url) == "http://127.0.0.1:8010/speech"
    assert 'name="text"\r\n\r\nNgày xưa'.encode() in content
    assert b'name="language"\r\n\r\nvi' in content
    assert 'name="sampleText"\r\n\r\nXin chào các bạn'.encode() in content
    assert b'name="sample"; filename="sample.wav"' in content
    assert omnivoice_narration.outcome.result.file_extension == "wav"


def test_local_music_sends_prompt_length_and_instrumental(ace_step_music_request):
    assert str(ace_step_music_request.url) == "http://127.0.0.1:8001/music"
    assert json_body(ace_step_music_request) == {
        "prompt": "Calm sea shanty",
        "durationS": 95,
        "instrumental": True,
    }


def test_local_server_error_text_is_retried(local_server_error):
    assert str(local_server_error) == "CUDA out of memory"
    assert local_server_error.kind is ProviderErrorKind.RETRYABLE
