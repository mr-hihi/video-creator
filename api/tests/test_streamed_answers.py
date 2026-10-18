from types import SimpleNamespace

import httpx
import pytest

from app.modules.ai_models import streamed_answers
from app.modules.ai_models.ai_calls import AiCallError, AiLimits
from app.modules.ai_models.streamed_answers import (
    SseRequest,
    sse_line_to_event,
    stream_sse_events,
    to_http_timeout,
)

API_KEY = "sk-secret-key"
LIMITS = AiLimits(timeout_sec=600)
WATCHED_LIMITS = AiLimits(timeout_sec=3600, silence_limit_sec=900)
REQUEST = SseRequest(
    ai_name="openai",
    url="https://api.example.test/v1/stream",
    body=b"{}",
    headers={"Authorization": f"Bearer {API_KEY}"},
    api_key=API_KEY,
)


def capture_stream_error(handler, limits: AiLimits = LIMITS) -> str:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AiCallError) as caught:
        list(stream_sse_events(http_client, REQUEST, limits))
    return str(caught.value)


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError(f"cannot reach with {API_KEY}")


def raise_read_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("read timed out")


@pytest.fixture
def connect_error_message():
    return capture_stream_error(raise_connect_error)


@pytest.fixture(
    params=[
        (LIMITS, "openai timed out after 600s"),
        (WATCHED_LIMITS, "openai stopped responding for 900s"),
    ]
)
def timeout_message(request):
    limits, expected = request.param
    return SimpleNamespace(
        actual=capture_stream_error(raise_read_timeout, limits), expected=expected
    )


@pytest.fixture
def overlong_stream_message(monkeypatch):
    clock = iter([0.0, 700.0])
    monkeypatch.setattr(streamed_answers.time, "monotonic", lambda: next(clock))
    return capture_stream_error(lambda request: httpx.Response(200, text='data: {"a": 1}\n\n'))


@pytest.fixture
def not_json_message():
    return capture_stream_error(lambda request: httpx.Response(200, text="data: {broken\n\n"))


def test_a_transport_error_is_reported_without_the_key(connect_error_message):
    assert connect_error_message == "openai failed: cannot reach with ***"


def test_a_read_timeout_names_the_limit_that_ran_out(timeout_message):
    assert timeout_message.actual == timeout_message.expected


def test_a_stream_longer_than_the_limit_times_out(overlong_stream_message):
    assert overlong_stream_message == "openai timed out after 600s"


def test_a_data_line_that_is_not_json_fails_the_call(not_json_message):
    assert not_json_message == "openai returned output that is not JSON"


def test_read_timeout_is_the_silence_limit_when_one_is_set():
    assert to_http_timeout(WATCHED_LIMITS).read == 900
    assert to_http_timeout(LIMITS).read == 600


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("", None),
        (": keep-alive", None),
        ("event: response.output_text.delta", None),
        ("data:   ", None),
        ("data: [DONE]", None),
        ("data: [1]", None),
        ('data: {"type": "response.completed"}', {"type": "response.completed"}),
    ],
)
def test_only_data_objects_are_events(line, expected):
    assert sse_line_to_event(line, "openai") == expected
