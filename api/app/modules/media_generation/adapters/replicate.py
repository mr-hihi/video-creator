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

REPLICATE_BASE_URL = "https://api.replicate.com/v1"
PROVIDER_NAME = "Replicate"
SUCCEEDED_STATUS = "succeeded"
FAILED_STATUSES = frozenset({"failed", "canceled"})
IMAGE_FALLBACK_EXTENSION = "png"
VIDEO_FALLBACK_EXTENSION = "mp4"
START_FRAME_FIELDS_BY_MODEL = {
    "kwaivgi/kling-v3-video": "start_image",
    "minimax/hailuo-2.3": "first_frame_image",
}
DEFAULT_START_FRAME_FIELD = "image"
SINGLE_IMAGE_EDIT_FIELD = "input_image"
MULTI_IMAGE_FIELD = "image_input"


class ReplicateAdapter:
    def __init__(self, http_client: httpx.Client, timeout_sec: float):
        self._http_client = http_client
        self._timeout_sec = timeout_sec

    def submit(self, task: MediaTask) -> SubmitOutcome:
        response = self._call(
            "POST",
            f"{REPLICATE_BASE_URL}/models/{task.model.id}/predictions",
            task,
            {"input": build_replicate_input(task)},
        )
        return SubmitOutcome(external_id=str(response.json()["id"]))

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        prediction = self._call(
            "GET", f"{REPLICATE_BASE_URL}/predictions/{external_id}", task, None
        ).json()
        prediction_status = prediction.get("status")
        if prediction_status in FAILED_STATUSES:
            raise ProviderError(
                f"{PROVIDER_NAME}: {prediction.get('error') or prediction_status}",
                ProviderErrorKind.FATAL,
            )
        if prediction_status != SUCCEEDED_STATUS:
            return PollOutcome(is_done=False)
        fallback_extension = (
            VIDEO_FALLBACK_EXTENSION
            if task.media_kind is MediaKind.VIDEO
            else IMAGE_FALLBACK_EXTENSION
        )
        return PollOutcome(
            is_done=True,
            result=download_result(
                self._http_client,
                find_replicate_output_url(prediction.get("output")),
                fallback_extension,
                None,
            ),
        )

    def _call(
        self, method: str, url: str, task: MediaTask, body: dict[str, Any] | None
    ) -> httpx.Response:
        request = self._http_client.build_request(
            method,
            url,
            json=body,
            headers={"Authorization": f"Bearer {task.api_key or ''}"},
            timeout=self._timeout_sec,
        )
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, task.api_key)
        return response


def build_replicate_input(task: MediaTask) -> dict[str, Any]:
    model_input: dict[str, Any] = {"prompt": task.prompt}
    if task.aspect:
        model_input["aspect_ratio"] = task.aspect
    if task.media_kind is MediaKind.VIDEO:
        if task.inputs.start_frame is None:
            raise ProviderError("A clip needs a start image", ProviderErrorKind.FATAL)
        start_field = START_FRAME_FIELDS_BY_MODEL.get(task.model.id, DEFAULT_START_FRAME_FIELD)
        model_input[start_field] = to_data_uri(task.inputs.start_frame)
        if task.clip_length_s:
            model_input["duration"] = task.clip_length_s
        return model_input
    image_paths = [
        path for path in (task.inputs.source_image, *task.inputs.references) if path is not None
    ]
    if not image_paths:
        return model_input
    if task.model.max_references == 0:
        return {**model_input, SINGLE_IMAGE_EDIT_FIELD: to_data_uri(image_paths[0])}
    return {**model_input, MULTI_IMAGE_FIELD: [to_data_uri(path) for path in image_paths]}


def find_replicate_output_url(output: Any) -> str:
    if isinstance(output, str) and output:
        return output
    if isinstance(output, list) and output and isinstance(output[0], str):
        return output[0]
    raise ProviderError(f"{PROVIDER_NAME} returned no media", ProviderErrorKind.FATAL)
