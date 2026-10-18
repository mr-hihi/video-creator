from pathlib import Path
from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import (
    ensure_success,
    send,
    to_file_extension,
    to_mime_type,
)
from app.modules.media_generation.adapters.voice_copies import VoiceCopyCache
from app.modules.media_generation.media_task import (
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.providers.provider_catalog import MediaKind

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
PROVIDER_NAME = "ElevenLabs"
API_KEY_HEADER = "xi-api-key"
AUDIO_FALLBACK_EXTENSION = "mp3"
SPEECH_OUTPUT_FORMAT = "mp3_44100_128"
FALLBACK_VOICE_NAME = "Narrator"
MS_PER_S = 1000


class ElevenLabsAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float):
        self._http_client = http_client
        self._timeout_sec = timeout_sec
        self._voice_copies = VoiceCopyCache()

    def submit(self, task: MediaTask) -> SubmitOutcome:
        if task.media_kind is MediaKind.SPEECH:
            return SubmitOutcome(result=self._speak(task))
        if task.media_kind is MediaKind.MUSIC:
            return SubmitOutcome(result=self._compose(task))
        raise ProviderError(
            f"{PROVIDER_NAME} {task.media_kind} is not supported", ProviderErrorKind.FATAL
        )

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        raise ProviderError(f"{PROVIDER_NAME} answers at once", ProviderErrorKind.FATAL)

    def _speak(self, task: MediaTask) -> MediaResult:
        made_voice_id = None
        voice_id = task.provider_voice_id
        if voice_id is None:
            made_voice_id = self._find_or_make_voice(task)
            voice_id = made_voice_id
        body: dict[str, Any] = {"text": task.prompt, "model_id": task.model.id}
        if task.language:
            body["language_code"] = task.language
        response = self._send(
            self._http_client.build_request(
                "POST",
                f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}",
                params={"output_format": SPEECH_OUTPUT_FORMAT},
                json=body,
                headers={API_KEY_HEADER: task.api_key or ""},
                timeout=self._timeout_sec,
            ),
            task,
        )
        return _to_audio_result(response, made_voice_id)

    def _compose(self, task: MediaTask) -> MediaResult:
        body: dict[str, Any] = {
            "prompt": task.prompt,
            "model_id": task.model.id,
            "force_instrumental": True,
        }
        if task.min_length_s:
            body["music_length_ms"] = task.min_length_s * MS_PER_S
        response = self._send(
            self._http_client.build_request(
                "POST",
                f"{ELEVENLABS_BASE_URL}/music",
                json=body,
                headers={API_KEY_HEADER: task.api_key or ""},
                timeout=self._timeout_sec,
            ),
            task,
        )
        return _to_audio_result(response, None)

    def _find_or_make_voice(self, task: MediaTask) -> str:
        sample = task.inputs.voice_sample
        if sample is None:
            raise ProviderError(
                "A narration needs the narrator voice sample", ProviderErrorKind.FATAL
            )
        return self._voice_copies.find_or_make((sample,), lambda: self._make_voice(task, sample))

    def _make_voice(self, task: MediaTask, sample: Path) -> str:
        response = self._send(
            self._http_client.build_request(
                "POST",
                f"{ELEVENLABS_BASE_URL}/voices/add",
                data={"name": task.voice_name or FALLBACK_VOICE_NAME},
                files=[("files", (sample.name, sample.read_bytes(), to_mime_type(sample)))],
                headers={API_KEY_HEADER: task.api_key or ""},
                timeout=self._timeout_sec,
            ),
            task,
        )
        voice_id = response.json().get("voice_id")
        if not voice_id:
            raise ProviderError(f"{PROVIDER_NAME} made no voice", ProviderErrorKind.FATAL)
        return str(voice_id)

    def _send(self, request: httpx.Request, task: MediaTask) -> httpx.Response:
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, task.api_key)
        return response


def _to_audio_result(response: httpx.Response, made_voice_id: str | None) -> MediaResult:
    return MediaResult(
        content=response.content,
        file_extension=to_file_extension(
            response.headers.get("content-type", ""), AUDIO_FALLBACK_EXTENSION
        ),
        provider_voice_id=made_voice_id,
    )
