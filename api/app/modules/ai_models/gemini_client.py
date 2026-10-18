from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AiProviderNotSetUpError
from app.modules.ai_models.ai_images import (
    AI_IMAGE_MEDIA_TYPE,
    AiImageEncoding,
    to_ai_jpeg_base64,
)
from app.modules.ai_models.model_choices import to_ai_name, to_provider_name
from app.modules.ai_models.streamed_answers import (
    JSON_CONTENT_TYPE,
    AiApiTools,
    SseRequest,
    answer_to_json,
    answer_to_text,
    encode_json_body,
    stream_sse_events,
)
from app.modules.providers.provider_catalog import ProviderId

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
API_KEY_HEADER = "x-goog-api-key"
UNKNOWN_REASON = "UNKNOWN"
BYTES_PER_MB = 1024 * 1024
MAX_REQUEST_MB = 20
TOO_LARGE_MESSAGE = (
    "gemini takes at most 20 MB per call; this call is {size_mb:.1f} MB — lower Max frames "
    "or pick another model"
)
GEMINI_AI_NAME = to_ai_name(ProviderId.GOOGLE)


@dataclass
class _StreamedAnswer:
    texts: list[str] = field(default_factory=list)
    stop_reason: str | None = None

    def add_chunk(self, chunk: Mapping[str, Any]) -> None:
        block_reason = chunk.get("promptFeedback", {}).get("blockReason")
        if block_reason:
            self.stop_reason = block_reason
        for candidate in chunk.get("candidates") or []:
            self.stop_reason = candidate.get("finishReason") or self.stop_reason
            for part in candidate.get("content", {}).get("parts") or []:
                if isinstance(part.get("text"), str) and not part.get("thought"):
                    self.texts.append(part["text"])

    def to_text(self) -> str:
        if not self.texts:
            raise AiCallError(
                f"{GEMINI_AI_NAME} returned no answer: {self.stop_reason or UNKNOWN_REASON}"
            )
        return "".join(self.texts)


class GeminiClient:
    def __init__(self, tools: AiApiTools):
        self._tools = tools

    def ask_for_json(self, model: str, ask: AiAsk, limits: AiLimits) -> dict[str, Any]:
        return answer_to_json(self._stream_answer(model, ask, limits), GEMINI_AI_NAME)

    def ask_for_text(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        return answer_to_text(self._stream_answer(model, ask, limits), GEMINI_AI_NAME)

    def _stream_answer(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        api_key = self._tools.find_api_key(ProviderId.GOOGLE)
        if api_key is None:
            raise AiProviderNotSetUpError(to_provider_name(ProviderId.GOOGLE))
        body = encode_json_body(build_request_body(ask, self._tools.image_encoding))
        ensure_within_request_limit(body)
        answer = _StreamedAnswer()
        request = SseRequest(
            ai_name=GEMINI_AI_NAME,
            url=to_stream_url(model),
            body=body,
            headers={API_KEY_HEADER: api_key},
            api_key=api_key,
        )
        for chunk in stream_sse_events(self._tools.http_client, request, limits):
            answer.add_chunk(chunk)
        return answer.to_text()


def to_stream_url(model: str) -> str:
    return f"{GEMINI_BASE_URL}/models/{model}:streamGenerateContent?alt=sse"


def ensure_within_request_limit(body: bytes) -> None:
    size_mb = len(body) / BYTES_PER_MB
    if size_mb > MAX_REQUEST_MB:
        raise AiCallError(TOO_LARGE_MESSAGE.format(size_mb=size_mb))


def build_request_body(ask: AiAsk, encoding: AiImageEncoding) -> dict[str, Any]:
    parts: list[dict[str, Any]] = [{"text": ask.message}]
    for image in ask.images:
        parts.append({"text": image.label})
        parts.append(
            {
                "inlineData": {
                    "mimeType": AI_IMAGE_MEDIA_TYPE,
                    "data": to_ai_jpeg_base64(image.path, encoding),
                }
            }
        )
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": ask.instructions}]},
        "contents": [{"role": "user", "parts": parts}],
    }
    if ask.reply_schema is not None:
        body["generationConfig"] = {
            "responseMimeType": JSON_CONTENT_TYPE,
            "responseJsonSchema": ask.reply_schema,
        }
    return body
