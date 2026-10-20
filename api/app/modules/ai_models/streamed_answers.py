import json
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from app.modules.ai_models.ai_calls import AiCallError, AiLimits
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.providers.connection_tester import describe_error_response
from app.modules.providers.provider_catalog import ProviderId
from app.modules.providers.secret_box import redact_secret

SSE_DATA_PREFIX = "data:"
SSE_DONE_DATA = "[DONE]"
JSON_CONTENT_TYPE = "application/json"
CONNECT_TIMEOUT_SEC = 30.0


@dataclass(frozen=True)
class AiApiTools:
    http_client: httpx.Client
    find_api_key: Callable[[ProviderId], str | None]
    image_encoding: AiImageEncoding


@dataclass(frozen=True)
class SseRequest:
    ai_name: str
    url: str
    body: bytes
    headers: Mapping[str, str]
    api_key: str
    started_at: float | None = None


def stream_sse_events(
    http_client: httpx.Client, request: SseRequest, limits: AiLimits
) -> Iterator[dict[str, Any]]:
    try:
        yield from _read_sse_events(http_client, request, limits)
    except httpx.TimeoutException as error:
        raise AiCallError(to_timeout_message(request.ai_name, limits)) from error
    except httpx.HTTPError as error:
        message = redact_secret(f"{request.ai_name} failed: {error}", request.api_key)
        raise AiCallError(message) from error


def _read_sse_events(
    http_client: httpx.Client, request: SseRequest, limits: AiLimits
) -> Iterator[dict[str, Any]]:
    started_at = time.monotonic() if request.started_at is None else request.started_at
    with http_client.stream(
        "POST",
        request.url,
        content=request.body,
        headers={"Content-Type": JSON_CONTENT_TYPE, **request.headers},
        timeout=to_http_timeout(limits),
    ) as response:
        ensure_success(response, request)
        for line in response.iter_lines():
            event = sse_line_to_event(line, request.ai_name)
            if event is None:
                continue
            limits.on_output()
            if time.monotonic() - started_at > limits.timeout_sec:
                raise AiCallError(f"{request.ai_name} timed out after {limits.timeout_sec:g}s")
            yield event


def to_http_timeout(limits: AiLimits) -> httpx.Timeout:
    read_timeout_sec = limits.silence_limit_sec or limits.timeout_sec
    return httpx.Timeout(read_timeout_sec, connect=CONNECT_TIMEOUT_SEC)


def to_timeout_message(ai_name: str, limits: AiLimits) -> str:
    if limits.silence_limit_sec is not None:
        return f"{ai_name} stopped responding for {limits.silence_limit_sec:g}s"
    return f"{ai_name} timed out after {limits.timeout_sec:g}s"


def ensure_success(response: httpx.Response, request: SseRequest) -> None:
    if response.is_success:
        return
    response.read()
    message = f"{request.ai_name} failed: {describe_error_response(response)}"
    raise AiCallError(redact_secret(message, request.api_key))


def sse_line_to_event(line: str, ai_name: str) -> dict[str, Any] | None:
    if not line.startswith(SSE_DATA_PREFIX):
        return None
    data = line[len(SSE_DATA_PREFIX) :].strip()
    if not data or data == SSE_DONE_DATA:
        return None
    try:
        event = json.loads(data)
    except json.JSONDecodeError as error:
        raise AiCallError(f"{ai_name} returned output that is not JSON") from error
    return event if isinstance(event, dict) else None


def encode_json_body(body: Mapping[str, Any]) -> bytes:
    return json.dumps(body).encode("utf-8")


def answer_to_json(answer: str, ai_name: str) -> dict[str, Any]:
    try:
        reply = json.loads(answer)
    except json.JSONDecodeError as error:
        raise AiCallError(f"{ai_name} returned output that is not JSON") from error
    if not isinstance(reply, dict):
        raise AiCallError(f"{ai_name} returned no structured output")
    return reply


def answer_to_text(answer: str, ai_name: str) -> str:
    text = answer.strip()
    if not text:
        raise AiCallError(f"{ai_name} returned an empty answer")
    return text
