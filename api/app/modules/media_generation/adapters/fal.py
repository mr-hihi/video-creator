from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import (
    download_result,
    ensure_success,
    send,
    to_data_uri,
)
from app.modules.media_generation.media_task import (
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.providers.provider_catalog import MediaKind

FAL_QUEUE_BASE_URL = "https://queue.fal.run"
PROVIDER_NAME = "fal.ai"
COMPLETED_STATUS = "COMPLETED"
IMAGE_FALLBACK_EXTENSION = "png"
VIDEO_FALLBACK_EXTENSION = "mp4"


class FalAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float):
        self._http_client = http_client
        self._timeout_sec = timeout_sec

    def submit(self, task: MediaTask) -> SubmitOutcome:
        model_id, model_input = build_fal_input(task)
        response = self._call("POST", f"{FAL_QUEUE_BASE_URL}/{model_id}", task, model_input)
        return SubmitOutcome(external_id=str(response.json()["response_url"]))

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        queue_status = self._call("GET", f"{external_id}/status", task, None).json()
        if queue_status.get("status") != COMPLETED_STATUS:
            return PollOutcome(is_done=False)
        output = self._call("GET", external_id, task, None).json()
        result_url, fallback_extension = find_fal_result_url(output)
        return PollOutcome(
            is_done=True,
            result=download_result(self._http_client, result_url, fallback_extension, None),
        )

    def _call(
        self, method: str, url: str, task: MediaTask, body: dict[str, Any] | None
    ) -> httpx.Response:
        request = self._http_client.build_request(
            method,
            url,
            json=body,
            headers={"Authorization": f"Key {task.api_key or ''}"},
            timeout=self._timeout_sec,
        )
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, task.api_key)
        return response


def build_fal_input(task: MediaTask) -> tuple[str, dict[str, Any]]:
    model = task.model
    model_input: dict[str, Any] = {"prompt": task.prompt}
    if task.aspect:
        model_input["aspect_ratio"] = task.aspect
    if task.media_kind is MediaKind.VIDEO:
        if task.inputs.start_frame is None:
            raise ProviderError("A clip needs a start image", ProviderErrorKind.FATAL)
        model_input["image_url"] = to_data_uri(task.inputs.start_frame)
        if task.clip_length_s:
            model_input["duration"] = str(task.clip_length_s)
        return model.id, model_input
    image_paths = [
        path for path in (task.inputs.source_image, *task.inputs.references) if path is not None
    ]
    if not image_paths:
        return model.id, {**model_input, "num_images": 1}
    if model.max_references == 0:
        return model.id, {**model_input, "image_url": to_data_uri(image_paths[0])}
    return (
        model.with_references_id or model.id,
        {**model_input, "image_urls": [to_data_uri(path) for path in image_paths]},
    )


def find_fal_result_url(output: dict[str, Any]) -> tuple[str, str]:
    images = output.get("images") or []
    if images:
        return str(images[0]["url"]), IMAGE_FALLBACK_EXTENSION
    video = output.get("video")
    if isinstance(video, dict) and video.get("url"):
        return str(video["url"]), VIDEO_FALLBACK_EXTENSION
    raise ProviderError(f"{PROVIDER_NAME} returned no media", ProviderErrorKind.FATAL)
