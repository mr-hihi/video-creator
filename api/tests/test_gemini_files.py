import json
import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AttachedMedia
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.gemini_client import GeminiClient
from app.modules.ai_models.streamed_answers import AiApiTools

API_KEY = "AIza-secret-key"
MODEL = "gemini-4-argon"
ENCODING = AiImageEncoding(max_side_px=480, jpeg_quality=60)
LIMITS = AiLimits(timeout_sec=600)
UPLOAD_START_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
SESSION_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files?upload_id=s1"
FILE_URL = "https://generativelanguage.googleapis.com/v1beta/files/f1"
FILE_URI = "https://generativelanguage.googleapis.com/v1beta/files/f1"
STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-4-argon:streamGenerateContent?alt=sse"
)
SCHEMA = {"type": "object"}


def to_sse_answer(text: str) -> httpx.Response:
    chunk = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return httpx.Response(200, text=f"data: {json.dumps(chunk)}\r\n\r\n")


def to_stored_file(state: str, **values) -> dict:
    return {"name": "files/f1", "uri": FILE_URI, "mimeType": "audio/mp4", "state": state, **values}


@dataclass
class FakeGemini:
    upload_answer: httpx.Response = field(
        default_factory=lambda: httpx.Response(200, json={"file": to_stored_file("PROCESSING")})
    )
    start_answer: httpx.Response = field(
        default_factory=lambda: httpx.Response(200, headers={"x-goog-upload-url": SESSION_URL})
    )
    poll_answer: httpx.Response = field(
        default_factory=lambda: httpx.Response(200, json=to_stored_file("ACTIVE"))
    )
    stream_answer: httpx.Response = field(default_factory=lambda: to_sse_answer('{"ok": true}'))
    delete_answer: httpx.Response = field(default_factory=lambda: httpx.Response(200, json={}))
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        url = str(request.url)
        if request.method == "DELETE":
            return self.delete_answer
        if request.method == "GET":
            return self.poll_answer
        if url == UPLOAD_START_URL:
            return self.start_answer
        if url == SESSION_URL:
            return self.upload_answer
        return self.stream_answer


def ask_with_media(tmp_path, mime_type: str, **ask_values) -> AiAsk:
    path = tmp_path / "part-01.m4a"
    path.write_bytes(b"audio-bytes")
    return AiAsk(
        instructions="Hear P",
        message="This part of the film runs from 00:00 to 30:00.",
        media=[AttachedMedia(label="[audio 00:00–30:00]", path=path, mime_type=mime_type)],
        **ask_values,
    )


def build_client(fake: FakeGemini, poll_interval_sec: float = 0) -> GeminiClient:
    http_client = httpx.Client(transport=httpx.MockTransport(fake.handle))
    tools = AiApiTools(http_client, MagicMock(return_value=API_KEY), ENCODING)
    return GeminiClient(tools, poll_interval_sec)


def capture_call_error(fake: FakeGemini, ask: AiAsk, limits: AiLimits = LIMITS, **client_values):
    with pytest.raises(AiCallError) as caught:
        build_client(fake, **client_values).ask_for_text(MODEL, ask, limits)
    return SimpleNamespace(message=str(caught.value), fake=fake)


def to_calls(fake: FakeGemini) -> list[tuple[str, str]]:
    return [(request.method, str(request.url)) for request in fake.requests]


@pytest.fixture
def audio_call(tmp_path):
    fake = FakeGemini()
    reply = build_client(fake).ask_for_json(
        MODEL, ask_with_media(tmp_path, "audio/mp4", reply_schema=SCHEMA), LIMITS
    )
    return SimpleNamespace(reply=reply, fake=fake, requests=fake.requests)


@pytest.fixture
def video_call(tmp_path):
    fake = FakeGemini(
        upload_answer=httpx.Response(200, json={"file": to_stored_file("ACTIVE")}),
        stream_answer=to_sse_answer("  ## A  "),
    )
    answer = build_client(fake).ask_for_text(MODEL, ask_with_media(tmp_path, "video/mp4"), LIMITS)
    return SimpleNamespace(answer=answer, fake=fake)


@pytest.fixture
def refused_upload(tmp_path):
    fake = FakeGemini(
        start_answer=httpx.Response(
            400, json={"error": {"message": f"File too large for {API_KEY}"}}
        )
    )
    return capture_call_error(fake, ask_with_media(tmp_path, "audio/mp4"))


@pytest.fixture
def failed_file(tmp_path):
    fake = FakeGemini(poll_answer=httpx.Response(200, json=to_stored_file("FAILED")))
    return capture_call_error(fake, ask_with_media(tmp_path, "video/mp4"))


@pytest.fixture(
    params=[
        (httpx.Response(200), "gemini could not take the audio: no upload URL", "start"),
        (
            httpx.Response(200, text="<html>"),
            "gemini could not take the audio: the answer is not JSON",
            "upload",
        ),
        (
            httpx.Response(200, json=[1]),
            "gemini could not take the audio: no file in the answer",
            "upload",
        ),
        (
            httpx.Response(200, json={"file": to_stored_file("ACTIVE", uri="")}),
            "gemini could not take the audio: no file URI in the answer",
            "upload",
        ),
    ]
)
def malformed_files_answer(request, tmp_path):
    answer, expected, answered_step = request.param
    fake = (
        FakeGemini(start_answer=answer)
        if answered_step == "start"
        else FakeGemini(upload_answer=answer)
    )
    outcome = capture_call_error(fake, ask_with_media(tmp_path, "audio/mp4"))
    return SimpleNamespace(message=outcome.message, expected=expected)


@pytest.fixture
def broken_connection(tmp_path):
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"connection refused for {API_KEY}", request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(fail))
    client = GeminiClient(AiApiTools(http_client, MagicMock(return_value=API_KEY), ENCODING), 0)
    with pytest.raises(AiCallError) as caught:
        client.ask_for_text(MODEL, ask_with_media(tmp_path, "audio/mp4"), LIMITS)
    return str(caught.value)


@pytest.fixture
def stalled_upload(tmp_path):
    def stall(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(stall))
    client = GeminiClient(AiApiTools(http_client, MagicMock(return_value=API_KEY), ENCODING), 0)
    with pytest.raises(AiCallError) as caught:
        client.ask_for_text(MODEL, ask_with_media(tmp_path, "audio/mp4"), LIMITS)
    return str(caught.value)


@pytest.fixture
def slow_processing(tmp_path):
    return capture_call_error(
        FakeGemini(),
        ask_with_media(tmp_path, "audio/mp4"),
        AiLimits(timeout_sec=5),
        poll_interval_sec=10,
    )


@pytest.fixture
def no_time_left(tmp_path):
    return capture_call_error(FakeGemini(), ask_with_media(tmp_path, "audio/mp4"), AiLimits(0))


@pytest.fixture
def failed_answer_call(tmp_path):
    fake = FakeGemini(
        stream_answer=httpx.Response(500, json={"error": {"message": "Internal error"}})
    )
    return capture_call_error(fake, ask_with_media(tmp_path, "audio/mp4"))


@pytest.fixture
def undeletable_file_call(tmp_path, caplog):
    fake = FakeGemini(
        delete_answer=httpx.Response(500, json={"error": {"message": "busy"}}),
        stream_answer=to_sse_answer("## A"),
    )
    with caplog.at_level(logging.WARNING):
        answer = build_client(fake).ask_for_text(
            MODEL, ask_with_media(tmp_path, "audio/mp4"), LIMITS
        )
    return SimpleNamespace(answer=answer, log=caplog.text)


def test_a_media_part_is_uploaded_waited_on_used_then_deleted(audio_call):
    assert to_calls(audio_call.fake) == [
        ("POST", UPLOAD_START_URL),
        ("POST", SESSION_URL),
        ("GET", FILE_URL),
        ("POST", STREAM_URL),
        ("DELETE", FILE_URL),
    ]
    assert audio_call.reply == {"ok": True}


def test_the_upload_starts_a_resumable_session_with_the_file_size_and_type(audio_call):
    start = audio_call.requests[0]
    assert {
        name: start.headers[name]
        for name in (
            "x-goog-api-key",
            "x-goog-upload-protocol",
            "x-goog-upload-command",
            "x-goog-upload-header-content-length",
            "x-goog-upload-header-content-type",
            "content-type",
        )
    } == {
        "x-goog-api-key": API_KEY,
        "x-goog-upload-protocol": "resumable",
        "x-goog-upload-command": "start",
        "x-goog-upload-header-content-length": "11",
        "x-goog-upload-header-content-type": "audio/mp4",
        "content-type": "application/json",
    }
    assert json.loads(start.content) == {"file": {"display_name": "part-01.m4a"}}


def test_the_upload_sends_the_bytes_and_finalizes(audio_call):
    upload = audio_call.requests[1]
    assert (
        upload.headers["x-goog-upload-command"],
        upload.headers["x-goog-upload-offset"],
        upload.headers["x-goog-api-key"],
        upload.content,
    ) == ("upload, finalize", "0", API_KEY, b"audio-bytes")


def test_the_call_names_the_audio_after_its_time_range(audio_call):
    assert json.loads(audio_call.requests[3].content) == {
        "systemInstruction": {"parts": [{"text": "Hear P"}]},
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "This part of the film runs from 00:00 to 30:00."},
                    {"text": "[audio 00:00–30:00]"},
                    {"fileData": {"mimeType": "audio/mp4", "fileUri": FILE_URI}},
                ],
            }
        ],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": SCHEMA},
    }


def test_a_video_call_asks_for_low_media_resolution(video_call):
    body = json.loads(video_call.fake.requests[2].content)
    assert body["generationConfig"] == {"mediaResolution": "MEDIA_RESOLUTION_LOW"}
    assert body["contents"][0]["parts"][2] == {
        "fileData": {"mimeType": "video/mp4", "fileUri": FILE_URI}
    }
    assert "videoMetadata" not in json.dumps(body)
    assert video_call.answer == "## A"


def test_an_active_file_needs_no_polling(video_call):
    assert [method for method, _url in to_calls(video_call.fake)] == [
        "POST",
        "POST",
        "POST",
        "DELETE",
    ]


def test_a_refused_upload_names_the_media_without_the_key(refused_upload):
    assert refused_upload.message == "gemini could not take the audio: File too large for ***"
    assert to_calls(refused_upload.fake) == [("POST", UPLOAD_START_URL)]


def test_a_file_that_ends_failed_is_refused_and_deleted(failed_file):
    assert failed_file.message == "gemini could not take the video: FAILED"
    assert to_calls(failed_file.fake)[-1] == ("DELETE", FILE_URL)
    assert ("POST", STREAM_URL) not in to_calls(failed_file.fake)


def test_a_malformed_files_answer_is_refused(malformed_files_answer):
    assert malformed_files_answer.message == malformed_files_answer.expected


def test_a_broken_connection_is_refused_without_the_key(broken_connection):
    assert broken_connection == ("gemini could not take the audio: connection refused for ***")


def test_a_stalled_upload_times_out(stalled_upload):
    assert stalled_upload == "gemini timed out after 600s"


def test_a_file_still_processing_at_the_limit_times_out_and_is_deleted(slow_processing):
    assert slow_processing.message == "gemini timed out after 5s"
    assert to_calls(slow_processing.fake)[-1] == ("DELETE", FILE_URL)


def test_no_time_left_sends_nothing(no_time_left):
    assert no_time_left.message == "gemini timed out after 0s"
    assert no_time_left.fake.requests == []


def test_a_failed_call_still_deletes_the_uploaded_file(failed_answer_call):
    assert failed_answer_call.message == "gemini failed: Internal error"
    assert to_calls(failed_answer_call.fake)[-1] == ("DELETE", FILE_URL)


def test_a_delete_error_is_logged_and_never_fails_the_call(undeletable_file_call):
    assert undeletable_file_call.answer == "## A"
    assert "Could not delete Gemini file files/f1" in undeletable_file_call.log
    assert API_KEY not in undeletable_file_call.log
