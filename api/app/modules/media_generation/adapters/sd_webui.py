import base64
from dataclasses import dataclass
from typing import Any

import httpx

from app.modules.media_generation.adapters.http_support import ensure_success, send, to_base64
from app.modules.media_generation.adapters.sd_composite import build_composite
from app.modules.media_generation.media_task import (
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)

PROVIDER_NAME = "Stable Diffusion WebUI / Forge"
IMAGE_EXTENSION = "png"
LANDSCAPE_SIZE = (1344, 768)
PORTRAIT_SIZE = (768, 1344)
PORTRAIT_ASPECT = "9:16"


@dataclass(frozen=True)
class SdWebUiConfig:
    timeout_sec: float
    denoising_strength: float
    composite_denoising_strength: float


class SdWebUiAdapter:
    def __init__(self, http_client: httpx.Client, config: SdWebUiConfig):
        self._http_client = http_client
        self._config = config

    def submit(self, task: MediaTask) -> SubmitOutcome:
        size = PORTRAIT_SIZE if task.aspect == PORTRAIT_ASPECT else LANDSCAPE_SIZE
        body: dict[str, Any] = {"prompt": task.prompt, "width": size[0], "height": size[1]}
        if task.inputs.references:
            endpoint = "/sdapi/v1/img2img"
            composite = build_composite(
                size, task.inputs.source_image, task.inputs.references, task.reference_kinds
            )
            body["init_images"] = [base64.b64encode(composite).decode("ascii")]
            body["denoising_strength"] = self._config.composite_denoising_strength
        elif task.inputs.source_image is not None:
            endpoint = "/sdapi/v1/img2img"
            body["init_images"] = [to_base64(task.inputs.source_image)]
            body["denoising_strength"] = self._config.denoising_strength
        else:
            endpoint = "/sdapi/v1/txt2img"
        request = self._http_client.build_request(
            "POST",
            f"{(task.base_url or '').rstrip('/')}{endpoint}",
            json=body,
            timeout=self._config.timeout_sec,
        )
        response = send(self._http_client, request, PROVIDER_NAME)
        ensure_success(response, PROVIDER_NAME, None)
        return SubmitOutcome(result=sd_answer_to_image(response.json()))

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        raise ProviderError(f"{PROVIDER_NAME} answers at once", ProviderErrorKind.FATAL)


def sd_answer_to_image(answer: dict[str, Any]) -> MediaResult:
    images = answer.get("images") or []
    if not images:
        raise ProviderError(f"{PROVIDER_NAME} returned no image", ProviderErrorKind.FATAL)
    return MediaResult(content=base64.b64decode(images[0]), file_extension=IMAGE_EXTENSION)
