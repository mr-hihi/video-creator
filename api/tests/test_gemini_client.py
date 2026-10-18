import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from PIL import Image

from app.modules.ai_models import gemini_client
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AttachedImage
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.gemini_client import (
    GeminiClient,
    build_request_body,
    ensure_within_request_limit,
)
from app.modules.ai_models.streamed_answers import AiApiTools
from app.modules.providers.provider_catalog import ProviderId

API_KEY = "AIza-secret-key"
MODEL = "gemini-4-argon"
ENCODING = AiImageEncoding(max_side_px=480, jpeg_quality=60)
LIMITS = AiLimits(timeout_sec=600)
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}}
JSON_ASK = AiAsk(instructions="Rules", message="Notes", reply_schema=SCHEMA)
TEXT_ASK = AiAsk(instructions="Rules", message="Notes")
BYTES_PER_MB = 1024 * 1024


def to_sse(*chunks: dict) -> str:
    return "".join(f"data: {json.dumps(chunk)}\r\n\r\n" for chunk in chunks)


def text_chunk(text: str, **part_values) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text, **part_values}]}}]}


def build_client(handler, api_key: str | None = API_KEY):
    seen_requests: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return handler(request)

    http_client = httpx.Client(transport=httpx.MockTransport(recording_handler))
    find_api_key = MagicMock(return_value=api_key)
    client = GeminiClient(AiApiTools(http_client, find_api_key, ENCODING))
    return SimpleNamespace(client=client, seen=seen_requests, find_api_key=find_api_key)


def answer_with(body: str, status_code: int = 200):
    return lambda request: httpx.Response(status_code, text=body)


def capture_call_error(action) -> str:
    with pytest.raises(AiCallError) as caught:
        action()
    return str(caught.value)


@pytest.fixture
def json_call():
    rig = build_client(
        answer_with(
            to_sse(
                text_chunk("thinking", thought=True),
                text_chunk('{"title": '),
                {"candidates": [{"content": {"parts": [{"text": '"Tour"}'}]}}]},
            )
        )
    )
    outputs: list[str] = []
    limits = AiLimits(timeout_sec=600, on_output=lambda: outputs.append("chunk"))
    reply = rig.client.ask_for_json(MODEL, JSON_ASK, limits)
    return SimpleNamespace(reply=reply, request=rig.seen[0], outputs=outputs, rig=rig)


@pytest.fixture
def text_answer():
    rig = build_client(answer_with(to_sse(text_chunk("  ## Character A\n"))))
    return rig.client.ask_for_text(MODEL, TEXT_ASK, LIMITS)


@pytest.fixture(
    params=[
        (to_sse(text_chunk("not json")), "gemini returned output that is not JSON"),
        (to_sse(text_chunk("[1, 2]")), "gemini returned no structured output"),
        (
            to_sse({"promptFeedback": {"blockReason": "SAFETY"}}),
            "gemini returned no answer: SAFETY",
        ),
        (
            to_sse({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]}),
            "gemini returned no answer: MAX_TOKENS",
        ),
        (to_sse({"candidates": []}), "gemini returned no answer: UNKNOWN"),
        ("data: {broken\n\n", "gemini returned output that is not JSON"),
    ]
)
def json_call_failure(request):
    body, expected_message = request.param
    rig = build_client(answer_with(body))
    return SimpleNamespace(
        message=capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS)),
        expected_message=expected_message,
    )


@pytest.fixture
def empty_text_message():
    rig = build_client(answer_with(to_sse(text_chunk("   "))))
    return capture_call_error(lambda: rig.client.ask_for_text(MODEL, TEXT_ASK, LIMITS))


@pytest.fixture
def not_set_up_call():
    rig = build_client(answer_with(""), api_key=None)
    message = capture_call_error(lambda: rig.client.ask_for_text(MODEL, TEXT_ASK, LIMITS))
    return SimpleNamespace(message=message, seen=rig.seen, find_api_key=rig.find_api_key)


@pytest.fixture
def rejected_call_message():
    body = json.dumps({"error": {"message": f"Resource has been exhausted for {API_KEY}"}})
    rig = build_client(answer_with(body, status_code=429))
    return capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS))


@pytest.fixture
def oversized_call(monkeypatch):
    monkeypatch.setattr(gemini_client, "MAX_REQUEST_MB", 0)
    rig = build_client(answer_with(to_sse(text_chunk("{}"))))
    message = capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS))
    return SimpleNamespace(message=message, seen=rig.seen)


@pytest.fixture
def over_limit_message():
    return capture_call_error(lambda: ensure_within_request_limit(b"x" * (21 * BYTES_PER_MB)))


@pytest.fixture
def body_with_frame(tmp_path):
    path = tmp_path / "frame.png"
    Image.new("RGB", (2000, 1000)).save(path)
    return build_request_body(
        AiAsk(
            instructions="Rules",
            message="Notes",
            images=[AttachedImage(label="images/moment-01.jpg", path=path)],
        ),
        ENCODING,
    )


def test_ask_for_json_posts_to_the_streaming_endpoint_of_the_model_with_the_key_header(json_call):
    assert str(json_call.request.url) == (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-4-argon:streamGenerateContent?alt=sse"
    )
    assert json_call.request.headers["x-goog-api-key"] == API_KEY
    assert json_call.request.headers["content-type"] == "application/json"
    assert API_KEY not in str(json_call.request.url)
    json_call.rig.find_api_key.assert_called_once_with(ProviderId.GOOGLE)


def test_ask_for_json_sends_the_prompt_message_and_schema(json_call):
    assert json.loads(json_call.request.content) == {
        "systemInstruction": {"parts": [{"text": "Rules"}]},
        "contents": [{"role": "user", "parts": [{"text": "Notes"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": SCHEMA},
    }


def test_ask_for_json_joins_the_answer_chunks_without_thoughts(json_call):
    assert json_call.reply == {"title": "Tour"}


def test_every_chunk_is_a_sign_of_life(json_call):
    assert json_call.outputs == ["chunk", "chunk", "chunk"]


def test_ask_for_text_trims_the_answer(text_answer):
    assert text_answer == "## Character A"


def test_ask_for_json_reports_each_bad_answer(json_call_failure):
    assert json_call_failure.message == json_call_failure.expected_message


def test_ask_for_text_rejects_a_blank_answer(empty_text_message):
    assert empty_text_message == "gemini returned an empty answer"


def test_a_call_without_a_google_key_sends_nothing(not_set_up_call):
    assert not_set_up_call.message == "Google AI (Gemini, Veo) is not set up — open Settings"
    assert not_set_up_call.seen == []


def test_an_http_error_status_reports_the_api_message_without_the_key(rejected_call_message):
    assert rejected_call_message == "gemini failed: Resource has been exhausted for ***"


def test_a_request_over_the_inline_limit_is_not_sent(oversized_call):
    assert oversized_call.message.startswith("gemini takes at most 20 MB per call; this call is")
    assert oversized_call.seen == []


def test_the_size_message_names_the_request_size_with_one_decimal(over_limit_message):
    assert over_limit_message == (
        "gemini takes at most 20 MB per call; this call is 21.0 MB — lower Max frames or pick "
        "another model"
    )


def test_each_image_follows_its_label_and_no_schema_means_free_text(body_with_frame):
    parts = body_with_frame["contents"][0]["parts"]
    assert [part.get("text") for part in parts] == ["Notes", "images/moment-01.jpg", None]
    assert parts[2]["inlineData"]["mimeType"] == "image/jpeg"
    assert "generationConfig" not in body_with_frame
