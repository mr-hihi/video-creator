import base64
from pathlib import Path
from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import (
    ensure_success,
    send,
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

OPENAI_BASE_URL = "https://api.openai.com/v1"
PROVIDER_NAME = "OpenAI"
IMAGE_EXTENSION = "png"
LANDSCAPE_SIZE = "1536x864"
PORTRAIT_SIZE = "864x1536"
PORTRAIT_ASPECT = "9:16"


class OpenAiImageAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float):
        self._http_client = http_client
        self._timeout_sec = timeout_sec

    def submit(self, task: MediaTask) -> SubmitOutcome:
        image_paths = [
            path for path in (task.inputs.source_image, *task.inputs.references) if path is not None
        ]
        size = PORTRAIT_SIZE if task.aspect == PORTRAIT_ASPECT else LANDSCAPE_SIZE
        if image_paths:
            response = self._send(
                "/images/edits",
                task,
                data={"model": task.model.id, "prompt": task.prompt, "size": size},
                files=[_to_upload(path) for path in image_paths],
            )
        else:
            response = self._send(
                "/images/generations",
                task,
                json={"model": task.model.id, "prompt": task.prompt, "size": size, "n": 1},
            )
        return SubmitOutcome(result=openai_answer_to_image(response.json()))

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        raise ProviderError(f"{PROVIDER_NAME} images answer at once", ProviderErrorKind.FATAL)

    def _send(self, path: str, task: MediaTask, **content: Any) -> httpx.Response:
        request = self._http_client.build_request(
            "POST",
            f"{OPENAI_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {task.api_key or ''}"},
            timeout=self._timeout_sec,
            **content,
        )
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, task.api_key)
        return response


def openai_answer_to_image(answer: dict[str, Any]) -> MediaResult:
    images = answer.get("data") or []
    if not images or not images[0].get("b64_json"):
        raise ProviderError(f"{PROVIDER_NAME} returned no image", ProviderErrorKind.FATAL)
    return MediaResult(
        content=base64.b64decode(images[0]["b64_json"]), file_extension=IMAGE_EXTENSION
    )


def _to_upload(path: Path) -> tuple[str, tuple[str, bytes, str]]:
    return ("image[]", (path.name, path.read_bytes(), to_mime_type(path)))
