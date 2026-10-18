from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import (
    send,
    to_error_kind,
    to_file_extension,
    to_mime_type,
)
from app.modules.media_generation.media_task import (
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.providers.provider_catalog import MediaKind

AUDIO_FALLBACK_EXTENSION = "wav"
ERROR_TEXT_LIMIT = 500


class LocalAudioAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float, provider_name: str):
        self._http_client = http_client
        self._timeout_sec = timeout_sec
        self._provider_name = provider_name

    def submit(self, task: MediaTask) -> SubmitOutcome:
        if task.media_kind is MediaKind.SPEECH:
            return SubmitOutcome(result=self._call("/speech", task, **self._speech_content(task)))
        if task.media_kind is MediaKind.MUSIC:
            body = {"prompt": task.prompt, "durationS": task.min_length_s, "instrumental": True}
            return SubmitOutcome(result=self._call("/music", task, json=body))
        raise ProviderError(
            f"{self._provider_name} {task.media_kind} is not supported", ProviderErrorKind.FATAL
        )

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        raise ProviderError(f"{self._provider_name} answers at once", ProviderErrorKind.FATAL)

    def _speech_content(self, task: MediaTask) -> dict[str, Any]:
        sample = task.inputs.voice_sample
        if sample is None:
            raise ProviderError(
                "A narration needs the narrator voice sample", ProviderErrorKind.FATAL
            )
        return {
            "data": {
                "text": task.prompt,
                "language": task.language or "",
                "sampleText": task.sample_text or "",
            },
            "files": [("sample", (sample.name, sample.read_bytes(), to_mime_type(sample)))],
        }

    def _call(self, path: str, task: MediaTask, **content: Any) -> MediaResult:
        request = self._http_client.build_request(
            "POST",
            f"{(task.base_url or '').rstrip('/')}{path}",
            timeout=self._timeout_sec,
            **content,
        )
        response = send(self._http_client, request, self._provider_name)
        if not response.is_success:
            raise ProviderError(
                response.text.strip()[:ERROR_TEXT_LIMIT] or f"HTTP {response.status_code}",
                to_error_kind(response.status_code),
            )
        return MediaResult(
            content=response.content,
            file_extension=to_file_extension(
                response.headers.get("content-type", ""), AUDIO_FALLBACK_EXTENSION
            ),
        )
