import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from PIL import Image

from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AttachedImage
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.openai_client import OpenAiClient, build_request_body
from app.modules.ai_models.streamed_answers import AiApiTools
from app.modules.providers.provider_catalog import ProviderId

API_KEY = "sk-secret-key"
MODEL = "gpt-6-astra"
ENCODING = AiImageEncoding(max_side_px=480, jpeg_quality=60)
LIMITS = AiLimits(timeout_sec=600)
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}}
JSON_ASK = AiAsk(instructions="Rules", message="Notes", reply_schema=SCHEMA)
TEXT_ASK = AiAsk(instructions="Rules", message="Notes")
COMPLETED = {"type": "response.completed", "response": {"status": "completed"}}


def to_sse(*events: dict) -> str:
    return "".join(f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events)


def text_delta(text) -> dict:
    return {"type": "response.output_text.delta", "delta": text}


def build_client(handler, api_key: str | None = API_KEY):
    seen_requests: list[httpx.Request] = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return handler(request)

    http_client = httpx.Client(transport=httpx.MockTransport(recording_handler))
    find_api_key = MagicMock(return_value=api_key)
    client = OpenAiClient(AiApiTools(http_client, find_api_key, ENCODING))
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
        answer_with(to_sse(text_delta('{"title": '), text_delta('"Tour"}'), COMPLETED))
    )
    outputs: list[str] = []
    limits = AiLimits(timeout_sec=600, on_output=lambda: outputs.append("event"))
    reply = rig.client.ask_for_json(MODEL, JSON_ASK, limits)
    return SimpleNamespace(reply=reply, request=rig.seen[0], outputs=outputs, rig=rig)


@pytest.fixture
def text_call():
    rig = build_client(answer_with(to_sse(text_delta("  ## Character A\n"), COMPLETED)))
    answer = rig.client.ask_for_text(MODEL, TEXT_ASK, LIMITS)
    return SimpleNamespace(answer=answer, body=json.loads(rig.seen[0].content))


@pytest.fixture(
    params=[
        (to_sse(text_delta("not json"), COMPLETED), "openai returned output that is not JSON"),
        (to_sse(text_delta("[1]"), COMPLETED), "openai returned no structured output"),
        (
            to_sse({"type": "response.failed", "response": {"error": {"message": "Overloaded"}}}),
            "openai failed: Overloaded",
        ),
        (
            to_sse({"type": "error", "message": "Rate limit reached"}),
            "openai failed: Rate limit reached",
        ),
        (to_sse({"type": "error"}), "openai failed: unknown"),
        (
            to_sse(
                {
                    "type": "response.incomplete",
                    "response": {"incomplete_details": {"reason": "content_filter"}},
                }
            ),
            "openai returned no answer: content_filter",
        ),
        (
            to_sse({"type": "response.incomplete", "response": {}}),
            "openai returned no answer: unknown",
        ),
        (
            to_sse({"type": "response.refusal.delta", "delta": "I can't help"}, COMPLETED),
            "openai returned no answer: refusal",
        ),
        (to_sse(text_delta(None), COMPLETED), "openai returned no answer: unknown"),
    ]
)
def json_call_failure(request):
    body, expected = request.param
    rig = build_client(answer_with(body))
    return SimpleNamespace(
        actual=capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS)),
        expected=expected,
    )


@pytest.fixture
def empty_text_message():
    rig = build_client(answer_with(to_sse(text_delta("  "), COMPLETED)))
    return capture_call_error(lambda: rig.client.ask_for_text(MODEL, TEXT_ASK, LIMITS))


@pytest.fixture
def not_set_up_call():
    rig = build_client(answer_with(""), api_key=None)
    message = capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS))
    return SimpleNamespace(message=message, seen=rig.seen)


@pytest.fixture
def rejected_call_message():
    body = json.dumps({"error": {"message": f"Incorrect API key provided: {API_KEY}"}})
    rig = build_client(answer_with(body, status_code=401))
    return capture_call_error(lambda: rig.client.ask_for_json(MODEL, JSON_ASK, LIMITS))


@pytest.fixture
def body_with_frame(tmp_path):
    path = tmp_path / "frame.png"
    Image.new("RGB", (1000, 500)).save(path)
    return build_request_body(
        MODEL,
        AiAsk(
            instructions="Rules",
            message="Notes",
            images=[AttachedImage(label="images/moment-01.jpg", path=path)],
        ),
        ENCODING,
    )


def test_ask_for_json_posts_to_the_responses_endpoint_with_a_bearer_key(json_call):
    assert str(json_call.request.url) == "https://api.openai.com/v1/responses"
    assert json_call.request.headers["authorization"] == f"Bearer {API_KEY}"
    json_call.rig.find_api_key.assert_called_once_with(ProviderId.OPENAI)


def test_ask_for_json_streams_without_storing_and_asks_for_the_schema(json_call):
    assert json.loads(json_call.request.content) == {
        "model": MODEL,
        "instructions": "Rules",
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "Notes"}]}],
        "stream": True,
        "store": False,
        "text": {
            "format": {"type": "json_schema", "name": "reply", "schema": SCHEMA, "strict": False}
        },
    }


def test_ask_for_json_joins_the_text_deltas(json_call):
    assert json_call.reply == {"title": "Tour"}


def test_every_event_is_a_sign_of_life(json_call):
    assert json_call.outputs == ["event", "event", "event"]


def test_ask_for_text_trims_the_answer_and_sends_no_format(text_call):
    assert text_call.answer == "## Character A"
    assert "text" not in text_call.body


def test_ask_for_json_reports_each_bad_answer(json_call_failure):
    assert json_call_failure.actual == json_call_failure.expected


def test_ask_for_text_rejects_a_blank_answer(empty_text_message):
    assert empty_text_message == "openai returned an empty answer"


def test_a_call_without_an_openai_key_sends_nothing(not_set_up_call):
    assert not_set_up_call.message == "OpenAI is not set up — open Settings"
    assert not_set_up_call.seen == []


def test_an_http_error_status_reports_the_api_message_without_the_key(rejected_call_message):
    assert rejected_call_message == "openai failed: Incorrect API key provided: ***"


def test_each_image_is_a_jpeg_data_url_after_its_label(body_with_frame):
    content = body_with_frame["input"][0]["content"]
    assert [part["type"] for part in content] == ["input_text", "input_text", "input_image"]
    assert content[1]["text"] == "images/moment-01.jpg"
    assert content[2]["image_url"].startswith("data:image/jpeg;base64,")
