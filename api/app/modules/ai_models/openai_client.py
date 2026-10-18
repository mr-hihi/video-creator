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
    AiApiTools,
    SseRequest,
    answer_to_json,
    answer_to_text,
    encode_json_body,
    stream_sse_events,
)
from app.modules.providers.provider_catalog import ProviderId

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
REPLY_FORMAT_NAME = "reply"
TEXT_DELTA_EVENT = "response.output_text.delta"
REFUSAL_DELTA_EVENT = "response.refusal.delta"
INCOMPLETE_EVENT = "response.incomplete"
FAILURE_EVENTS = frozenset({"response.failed", "error"})
REFUSAL_REASON = "refusal"
UNKNOWN_REASON = "unknown"
OPENAI_AI_NAME = to_ai_name(ProviderId.OPENAI)


@dataclass
class _StreamedAnswer:
    texts: list[str] = field(default_factory=list)
    stop_reason: str | None = None

    def add_event(self, event: Mapping[str, Any]) -> None:
        event_type = event.get("type")
        if event_type in FAILURE_EVENTS:
            raise AiCallError(f"{OPENAI_AI_NAME} failed: {to_failure_message(event)}")
        if event_type == TEXT_DELTA_EVENT and isinstance(event.get("delta"), str):
            self.texts.append(event["delta"])
        elif event_type == REFUSAL_DELTA_EVENT:
            self.stop_reason = REFUSAL_REASON
        elif event_type == INCOMPLETE_EVENT:
            incomplete_details = (event.get("response") or {}).get("incomplete_details") or {}
            self.stop_reason = incomplete_details.get("reason") or self.stop_reason

    def to_text(self) -> str:
        if not self.texts:
            raise AiCallError(
                f"{OPENAI_AI_NAME} returned no answer: {self.stop_reason or UNKNOWN_REASON}"
            )
        return "".join(self.texts)


class OpenAiClient:
    def __init__(self, tools: AiApiTools):
        self._tools = tools

    def ask_for_json(self, model: str, ask: AiAsk, limits: AiLimits) -> dict[str, Any]:
        return answer_to_json(self._stream_answer(model, ask, limits), OPENAI_AI_NAME)

    def ask_for_text(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        return answer_to_text(self._stream_answer(model, ask, limits), OPENAI_AI_NAME)

    def _stream_answer(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        api_key = self._tools.find_api_key(ProviderId.OPENAI)
        if api_key is None:
            raise AiProviderNotSetUpError(to_provider_name(ProviderId.OPENAI))
        answer = _StreamedAnswer()
        request = SseRequest(
            ai_name=OPENAI_AI_NAME,
            url=OPENAI_RESPONSES_URL,
            body=encode_json_body(build_request_body(model, ask, self._tools.image_encoding)),
            headers={"Authorization": f"Bearer {api_key}"},
            api_key=api_key,
        )
        for event in stream_sse_events(self._tools.http_client, request, limits):
            answer.add_event(event)
        return answer.to_text()


def build_request_body(model: str, ask: AiAsk, encoding: AiImageEncoding) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "input_text", "text": ask.message}]
    for image in ask.images:
        content.append({"type": "input_text", "text": image.label})
        content.append(
            {
                "type": "input_image",
                "image_url": (
                    f"data:{AI_IMAGE_MEDIA_TYPE};base64,{to_ai_jpeg_base64(image.path, encoding)}"
                ),
            }
        )
    body: dict[str, Any] = {
        "model": model,
        "instructions": ask.instructions,
        "input": [{"role": "user", "content": content}],
        "stream": True,
        "store": False,
    }
    if ask.reply_schema is not None:
        body["text"] = {
            "format": {
                "type": "json_schema",
                "name": REPLY_FORMAT_NAME,
                "schema": ask.reply_schema,
                "strict": False,
            }
        }
    return body


def to_failure_message(event: Mapping[str, Any]) -> str:
    response_error = (event.get("response") or {}).get("error") or {}
    return response_error.get("message") or event.get("message") or UNKNOWN_REASON
