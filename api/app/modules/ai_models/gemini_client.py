import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AiProviderNotSetUpError
from app.modules.ai_models.ai_images import (
    AI_IMAGE_MEDIA_TYPE,
    AiImageEncoding,
    to_ai_jpeg_base64,
)
from app.modules.ai_models.gemini_files import (
    API_KEY_HEADER,
    FILE_POLL_INTERVAL_SEC,
    GEMINI_AI_NAME,
    GEMINI_BASE_URL,
    FileCall,
    GeminiFiles,
    UploadedFile,
    to_media_word,
)
from app.modules.ai_models.model_choices import to_provider_name
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

UNKNOWN_REASON = "UNKNOWN"
BYTES_PER_MB = 1024 * 1024
MAX_REQUEST_MB = 20
TOO_LARGE_MESSAGE = (
    "gemini takes at most 20 MB per call; this call is {size_mb:.1f} MB — lower Max frames "
    "or pick another model"
)
VIDEO_MEDIA_WORD = "video"
LOW_MEDIA_RESOLUTION = "MEDIA_RESOLUTION_LOW"


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
    def __init__(self, tools: AiApiTools, file_poll_interval_sec: float = FILE_POLL_INTERVAL_SEC):
        self._tools = tools
        self._files = GeminiFiles(tools.http_client, file_poll_interval_sec)

    def ask_for_json(self, model: str, ask: AiAsk, limits: AiLimits) -> dict[str, Any]:
        return answer_to_json(self._answer(model, ask, limits), GEMINI_AI_NAME)

    def ask_for_text(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        return answer_to_text(self._answer(model, ask, limits), GEMINI_AI_NAME)

    def _answer(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        api_key = self._tools.find_api_key(ProviderId.GOOGLE)
        if api_key is None:
            raise AiProviderNotSetUpError(to_provider_name(ProviderId.GOOGLE))
        call = FileCall(api_key=api_key, limits=limits, started_at=time.monotonic())
        uploaded_files: list[UploadedFile] = []
        try:
            for media in ask.media:
                uploaded_files.append(self._files.upload(media, call))
            body = build_request_body(ask, self._tools.image_encoding, uploaded_files)
            return self._stream_answer(model, body, call)
        finally:
            for uploaded_file in uploaded_files:
                self._files.delete(uploaded_file.name, api_key)

    def _stream_answer(self, model: str, body_values: Mapping[str, Any], call: FileCall) -> str:
        body = encode_json_body(body_values)
        ensure_within_request_limit(body)
        answer = _StreamedAnswer()
        request = SseRequest(
            ai_name=GEMINI_AI_NAME,
            url=to_stream_url(model),
            body=body,
            headers={API_KEY_HEADER: call.api_key},
            api_key=call.api_key,
            started_at=call.started_at,
        )
        for chunk in stream_sse_events(self._tools.http_client, request, call.limits):
            answer.add_chunk(chunk)
        return answer.to_text()


def to_stream_url(model: str) -> str:
    return f"{GEMINI_BASE_URL}/models/{model}:streamGenerateContent?alt=sse"


def ensure_within_request_limit(body: bytes) -> None:
    size_mb = len(body) / BYTES_PER_MB
    if size_mb > MAX_REQUEST_MB:
        raise AiCallError(TOO_LARGE_MESSAGE.format(size_mb=size_mb))


def build_request_body(
    ask: AiAsk, encoding: AiImageEncoding, uploaded_files: Sequence[UploadedFile] = ()
) -> dict[str, Any]:
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
    for uploaded_file in uploaded_files:
        parts.append({"text": uploaded_file.media.label})
        parts.append(
            {"fileData": {"mimeType": uploaded_file.media.mime_type, "fileUri": uploaded_file.uri}}
        )
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": ask.instructions}]},
        "contents": [{"role": "user", "parts": parts}],
    }
    generation_config = build_generation_config(ask, uploaded_files)
    if generation_config:
        body["generationConfig"] = generation_config
    return body


def build_generation_config(ask: AiAsk, uploaded_files: Sequence[UploadedFile]) -> dict[str, Any]:
    generation_config: dict[str, Any] = {}
    if ask.reply_schema is not None:
        generation_config["responseMimeType"] = JSON_CONTENT_TYPE
        generation_config["responseJsonSchema"] = ask.reply_schema
    if any(to_media_word(uploaded.media) == VIDEO_MEDIA_WORD for uploaded in uploaded_files):
        generation_config["mediaResolution"] = LOW_MEDIA_RESOLUTION
    return generation_config
