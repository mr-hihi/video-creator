import base64
from pathlib import Path
from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import (
    download_result,
    ensure_success,
    send,
    to_base64,
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

GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
PROVIDER_NAME = "Google AI"
API_KEY_HEADER = "x-goog-api-key"
IMAGE_FALLBACK_EXTENSION = "png"
VIDEO_FALLBACK_EXTENSION = "mp4"
SPEECH_EXTENSION = "wav"
REPLICATED_VOICE_TYPE = "replicated"
FALLBACK_VOICE_NAME = "Narrator"
MODEL_OUTPUT_STEP = "model_output"
AUDIO_CONTENT = "audio"


class GoogleAiAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float):
        self._http_client = http_client
        self._timeout_sec = timeout_sec
        self._voice_copies = VoiceCopyCache()

    def submit(self, task: MediaTask) -> SubmitOutcome:
        if task.media_kind in (MediaKind.IMAGE, MediaKind.EDIT_IMAGE):
            return SubmitOutcome(result=self._generate_image(task))
        if task.media_kind is MediaKind.VIDEO:
            return SubmitOutcome(external_id=self._start_video(task))
        if task.media_kind is MediaKind.SPEECH:
            return SubmitOutcome(result=self._speak(task))
        raise ProviderError(
            f"{PROVIDER_NAME} {task.media_kind} is not supported", ProviderErrorKind.FATAL
        )

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        response = self._post_or_get("GET", f"{GOOGLE_AI_BASE_URL}/{external_id}", task, None)
        operation = response.json()
        if not operation.get("done"):
            return PollOutcome(is_done=False)
        if "error" in operation:
            raise ProviderError(
                f"{PROVIDER_NAME}: {operation['error'].get('message', 'video failed')}",
                ProviderErrorKind.FATAL,
            )
        return PollOutcome(is_done=True, result=self._download_video(task, operation))

    def _generate_image(self, task: MediaTask) -> MediaResult:
        image_paths = [
            path for path in (task.inputs.source_image, *task.inputs.references) if path is not None
        ]
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": task.prompt}, *map(_to_inline_part, image_paths)]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        if task.aspect:
            body["generationConfig"]["imageConfig"] = {"aspectRatio": task.aspect}
        response = self._post_or_get(
            "POST", f"{GOOGLE_AI_BASE_URL}/models/{task.model.id}:generateContent", task, body
        )
        return gemini_answer_to_image(response.json())

    def _start_video(self, task: MediaTask) -> str:
        if task.inputs.start_frame is None:
            raise ProviderError("A clip needs a start image", ProviderErrorKind.FATAL)
        instance = {
            "prompt": task.prompt,
            "image": {
                "bytesBase64Encoded": to_base64(task.inputs.start_frame),
                "mimeType": to_mime_type(task.inputs.start_frame),
            },
        }
        parameters: dict[str, Any] = {}
        if task.aspect:
            parameters["aspectRatio"] = task.aspect
        if task.clip_length_s:
            parameters["durationSeconds"] = task.clip_length_s
        response = self._post_or_get(
            "POST",
            f"{GOOGLE_AI_BASE_URL}/models/{task.model.id}:predictLongRunning",
            task,
            {"instances": [instance], "parameters": parameters},
        )
        return str(response.json()["name"])

    def _speak(self, task: MediaTask) -> MediaResult:
        made_voice_id = None
        voice_id = task.provider_voice_id
        if voice_id is None:
            made_voice_id = self._find_or_make_voice(task)
            voice_id = made_voice_id
        response = self._post_or_get(
            "POST",
            f"{GOOGLE_AI_BASE_URL}/interactions",
            task,
            {
                "model": task.model.id,
                "input": [
                    {"type": "user_input", "content": [{"type": "text", "text": task.prompt}]}
                ],
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": voice_id}]},
            },
        )
        return MediaResult(
            content=interaction_answer_to_audio(response.json()),
            file_extension=SPEECH_EXTENSION,
            provider_voice_id=made_voice_id,
        )

    def _find_or_make_voice(self, task: MediaTask) -> str:
        sample, consent_clip = task.inputs.voice_sample, task.inputs.consent_clip
        if sample is None or consent_clip is None:
            raise ProviderError(
                "A Google AI voice needs the sample and the consent clip", ProviderErrorKind.FATAL
            )
        return self._voice_copies.find_or_make(
            (sample, consent_clip), lambda: self._make_voice(task, sample, consent_clip)
        )

    def _make_voice(self, task: MediaTask, sample: Path, consent_clip: Path) -> str:
        response = self._post_or_get(
            "POST",
            f"{GOOGLE_AI_BASE_URL}/voices",
            task,
            {
                "store": True,
                "voice": {
                    "model": task.model.id,
                    "type": REPLICATED_VOICE_TYPE,
                    "display_name": task.voice_name or FALLBACK_VOICE_NAME,
                    "replicated": {
                        "source_audio": _to_audio_part(sample),
                        "consent_audio": _to_audio_part(consent_clip),
                    },
                },
            },
        )
        voice_id = response.json().get("id")
        if not voice_id:
            raise ProviderError(f"{PROVIDER_NAME} made no voice", ProviderErrorKind.FATAL)
        return str(voice_id)

    def _download_video(self, task: MediaTask, operation: dict[str, Any]) -> MediaResult:
        video_response = operation.get("response", {}).get("generateVideoResponse", {})
        samples = video_response.get("generatedSamples") or []
        if not samples:
            filtered_reasons = video_response.get("raiMediaFilteredReasons") or ["no video"]
            raise ProviderError(
                f"Blocked by the content filter: {'; '.join(filtered_reasons)}",
                ProviderErrorKind.FATAL,
            )
        return download_result(
            self._http_client,
            samples[0]["video"]["uri"],
            VIDEO_FALLBACK_EXTENSION,
            {API_KEY_HEADER: task.api_key or ""},
        )

    def _post_or_get(
        self, method: str, url: str, task: MediaTask, body: dict[str, Any] | None
    ) -> httpx.Response:
        request = self._http_client.build_request(
            method,
            url,
            json=body,
            headers={API_KEY_HEADER: task.api_key or ""},
            timeout=self._timeout_sec,
        )
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, task.api_key)
        return response


def gemini_answer_to_image(answer: dict[str, Any]) -> MediaResult:
    for candidate in answer.get("candidates") or []:
        for part in candidate.get("content", {}).get("parts") or []:
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data:
                return MediaResult(
                    content=base64.b64decode(inline_data["data"]),
                    file_extension=to_file_extension(
                        inline_data.get("mimeType", ""), IMAGE_FALLBACK_EXTENSION
                    ),
                )
    block_reason = answer.get("promptFeedback", {}).get("blockReason")
    if block_reason:
        raise ProviderError(
            f"Blocked by the content filter: {block_reason}", ProviderErrorKind.FATAL
        )
    raise ProviderError(f"{PROVIDER_NAME} returned no image", ProviderErrorKind.FATAL)


def interaction_answer_to_audio(answer: dict[str, Any]) -> bytes:
    for step in answer.get("steps") or []:
        if step.get("type") != MODEL_OUTPUT_STEP:
            continue
        for content in step.get("content") or []:
            if content.get("type") == AUDIO_CONTENT and content.get("data"):
                return base64.b64decode(content["data"])
    raise ProviderError(f"{PROVIDER_NAME} returned no audio", ProviderErrorKind.FATAL)


def _to_audio_part(path: Path) -> dict[str, str]:
    return {"mime_type": to_mime_type(path), "data": to_base64(path)}


def _to_inline_part(path: Path) -> dict[str, Any]:
    return {"inlineData": {"mimeType": to_mime_type(path), "data": to_base64(path)}}
