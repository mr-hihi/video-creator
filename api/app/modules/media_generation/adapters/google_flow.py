import hashlib
import logging
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.modules.media_generation.adapters.flow_project_owners import (
    FlowProjectOwner,
    FlowProjectOwners,
)
from app.modules.media_generation.adapters.google_flow_rpc import (
    IMAGE_ASPECT_LANDSCAPE,
    IMAGE_ASPECT_PORTRAIT,
    VIDEO_ASPECT_LANDSCAPE,
    VIDEO_ASPECT_PORTRAIT,
    FlowAnswerError,
    FlowOperation,
    FlowRpc,
    FlowRpcError,
    ImageGeneration,
    ImageUpload,
    VideoGeneration,
    build_create_project_rpc,
    build_image_rpc,
    build_media_rpc,
    build_operation_rpc,
    build_project_media_rpc,
    build_upload_rpc,
    build_video_rpc,
    find_media_id_in_listing,
    read_created_project_id,
    read_image_url,
    read_operation,
    read_payload,
    read_uploaded_media_id,
    read_video_url,
)
from app.modules.media_generation.adapters.http_support import (
    download_result,
    to_base64,
    to_mime_type,
)
from app.modules.media_generation.media_task import (
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.media_generation.worker import FLOW_SUBMIT_GAP_SEC
from app.modules.providers.errors import ExtensionNotConnectedError
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.model_catalog import CLIP_LENGTH_PLACEHOLDER
from app.modules.providers.provider_catalog import MediaKind

BATCH_RPC_METHOD = "batch_rpc"
ERROR_KEY = "error"
DATA_KEY = "data"
PORTRAIT_ASPECT = "9:16"
IMAGE_FALLBACK_EXTENSION = "jpg"
VIDEO_FALLBACK_EXTENSION = "mp4"
EXTERNAL_ID_SEPARATOR = "|"
LISTING_EVERY_POLL_ROUNDS = 3
NOT_FOUND_RPC_CODE = 5
DETAIL_TEXT_LIMIT = 160
LONG_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_\-.]{40,}")
LONG_TOKEN_REPLACEMENT = "…"
NO_FLOW_PROJECT_MESSAGE = "No Flow project — create one in Flow and enter its id in Settings"
INPUT_EXPIRED_MESSAGE = "Google Flow no longer has an uploaded input — it is uploaded again"
MISSING_INPUT_MESSAGE = "Google Flow could not find the Flow project or an input it was sent"
UNKNOWN_OPERATION_MESSAGE = "Unknown Google Flow operation id"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FailureRule:
    markers: tuple[str, ...]
    kind: ProviderErrorKind
    message: str


FAILURE_RULES = (
    FailureRule(
        ("extension_hijack",),
        ProviderErrorKind.NOT_CONNECTED,
        "Google Flow flagged the captcha (extension_hijack_detected)",
    ),
    FailureRule(
        ("public_error_unusual_activity", "unusual activity"),
        ProviderErrorKind.UNUSUAL_ACTIVITY,
        "Google Flow reported unusual activity",
    ),
    FailureRule(
        ("unsupported_on_batch_api", "public_error_model_access_denied"),
        ProviderErrorKind.FATAL,
        "Google Flow cannot do this: {detail}",
    ),
    FailureRule(
        ("public_error_unsafe_generation",),
        ProviderErrorKind.FATAL,
        "Blocked by the content filter: PUBLIC_ERROR_UNSAFE_GENERATION",
    ),
    FailureRule(("captcha",), ProviderErrorKind.CAPTCHA, "Google Flow captcha failed: {detail}"),
    FailureRule(
        ("not found", f"[rpc code {NOT_FOUND_RPC_CODE}]"),
        ProviderErrorKind.INPUT_EXPIRED,
        INPUT_EXPIRED_MESSAGE,
    ),
)


@dataclass(frozen=True)
class FlowFailure:
    search_text: str
    detail: str


@dataclass(frozen=True)
class UploadKey:
    project_id: str
    content_sha256: str


@dataclass(frozen=True)
class OperationLocation:
    project_id: str
    operation_id: str


@dataclass(frozen=True)
class PacerClock:
    read_seconds: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


class CaptchaRpcPacer:
    def __init__(self, clock: PacerClock | None = None):
        self._clock = clock or PacerClock()
        self._last_call_at: float | None = None

    def wait_turn(self) -> None:
        if self._last_call_at is not None:
            remaining_sec = FLOW_SUBMIT_GAP_SEC - (self._clock.read_seconds() - self._last_call_at)
            if remaining_sec > 0:
                self._clock.sleep(remaining_sec)
        self._last_call_at = self._clock.read_seconds()


@dataclass(frozen=True)
class GoogleFlowTools:
    bridge: FlowExtensionBridge
    http_client: httpx.Client
    owners: FlowProjectOwners


class GoogleFlowAdapter:
    def __init__(self, tools: GoogleFlowTools, pacer: CaptchaRpcPacer | None = None):
        self._tools = tools
        self._pacer = pacer or CaptchaRpcPacer()
        self._media_ids_by_upload: dict[UploadKey, str] = {}
        self._media_ids_by_operation: dict[str, str] = {}
        self._poll_rounds_by_operation: dict[str, int] = {}

    def submit(self, task: MediaTask) -> SubmitOutcome:
        input_paths = to_input_paths(task)
        project_id = self._find_flow_project_id(task)
        upload_keys = [UploadKey(project_id, _hash_file(path)) for path in input_paths]
        reused_keys = [key for key in upload_keys if key in self._media_ids_by_upload]
        try:
            media_ids = [
                self._find_or_upload(key, path)
                for key, path in zip(upload_keys, input_paths, strict=True)
            ]
            return self._start_generation(task, project_id, media_ids)
        except ProviderError as error:
            if error.kind is not ProviderErrorKind.INPUT_EXPIRED:
                raise
            if not reused_keys:
                raise ProviderError(MISSING_INPUT_MESSAGE) from error
            self._forget_uploads(reused_keys)
            raise

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        location = to_operation_location(external_id)
        try:
            video_url = self._find_video_url(location)
            if video_url is None:
                return PollOutcome(is_done=False)
            result = download_result(
                self._tools.http_client, video_url, VIDEO_FALLBACK_EXTENSION, None
            )
        except ProviderError as error:
            logger.warning("Google Flow poll of request %s failed: %s", task.request_id, error)
            return PollOutcome(is_done=False)
        self._media_ids_by_operation.pop(location.operation_id, None)
        self._poll_rounds_by_operation.pop(location.operation_id, None)
        return PollOutcome(is_done=True, result=result)

    def _find_flow_project_id(self, task: MediaTask) -> str:
        owner = self._tools.owners.find_owner(task.request_id)
        if owner is not None and owner.flow_project_id:
            return owner.flow_project_id
        created_project_id = None if owner is None else self._create_flow_project(owner)
        project_id = created_project_id or task.flow_project_id
        if not project_id:
            raise ProviderError(NO_FLOW_PROJECT_MESSAGE, ProviderErrorKind.FATAL)
        return project_id

    def _create_flow_project(self, owner: FlowProjectOwner) -> str | None:
        try:
            project_id = self._run_rpc(
                build_create_project_rpc(owner.name), read_created_project_id
            )
        except ProviderError as error:
            if error.kind is ProviderErrorKind.NOT_CONNECTED:
                raise
            logger.warning(
                "Could not create a Flow project for %s %s: %s", owner.kind, owner.owner_id, error
            )
            return None
        self._tools.owners.save_flow_project_id(owner, project_id)
        logger.info("Created Flow project %s for %s %s", project_id, owner.kind, owner.owner_id)
        return project_id

    def _find_or_upload(self, key: UploadKey, path: Path) -> str:
        cached_media_id = self._media_ids_by_upload.get(key)
        if cached_media_id is not None:
            return cached_media_id
        upload = ImageUpload(key.project_id, to_base64(path), to_mime_type(path), path.name)
        media_id = self._run_rpc(build_upload_rpc(upload), read_uploaded_media_id)
        self._media_ids_by_upload[key] = media_id
        return media_id

    def _forget_uploads(self, upload_keys: list[UploadKey]) -> None:
        for key in upload_keys:
            self._media_ids_by_upload.pop(key, None)

    def _start_generation(
        self, task: MediaTask, project_id: str, media_ids: list[str]
    ) -> SubmitOutcome:
        if task.media_kind is MediaKind.VIDEO:
            operation = self._run_rpc(
                build_video_rpc(to_video_generation(task, project_id, media_ids[0])),
                read_operation,
            )
            return SubmitOutcome(external_id=to_external_id(project_id, operation.operation_id))
        image_url = self._run_rpc(
            build_image_rpc(to_image_generation(task, project_id, media_ids)), read_image_url
        )
        return SubmitOutcome(
            result=download_result(
                self._tools.http_client, image_url, IMAGE_FALLBACK_EXTENSION, None
            )
        )

    def _find_video_url(self, location: OperationLocation) -> str | None:
        media_id = self._find_operation_media_id(location)
        if media_id is None:
            return None
        try:
            return self._run_rpc(build_media_rpc(media_id), read_video_url)
        except ProviderError:
            self._media_ids_by_operation.pop(location.operation_id, None)
            raise

    def _find_operation_media_id(self, location: OperationLocation) -> str | None:
        cached_media_id = self._media_ids_by_operation.get(location.operation_id)
        if cached_media_id is not None:
            return cached_media_id
        poll_round = self._poll_rounds_by_operation.get(location.operation_id, 0) + 1
        self._poll_rounds_by_operation[location.operation_id] = poll_round
        if not is_worth_listing(self._read_operation(location.operation_id), poll_round):
            return None
        listing_text = self._call_extension(
            build_project_media_rpc(location.project_id, location.operation_id)
        )
        media_id = find_media_id_in_listing(listing_text, location.operation_id)
        if media_id is not None:
            self._media_ids_by_operation[location.operation_id] = media_id
        return media_id

    def _read_operation(self, operation_id: str) -> FlowOperation | None:
        try:
            return self._run_rpc(build_operation_rpc(operation_id), read_operation)
        except ProviderError as error:
            logger.debug("Google Flow operation %s is unreadable: %s", operation_id, error)
            return None

    def _run_rpc[T](self, rpc: FlowRpc, read_answer: Callable[[Any], T]) -> T:
        answer_text = self._call_extension(rpc)
        try:
            return read_answer(read_payload(answer_text, rpc.rpc_id))
        except FlowRpcError as error:
            raise to_provider_error(to_rpc_failure(error, answer_text)) from error
        except FlowAnswerError as error:
            failure = FlowFailure(answer_text.lower(), str(error))
            raise to_provider_error(failure) from error

    def _call_extension(self, rpc: FlowRpc) -> str:
        if rpc.captcha_action is not None:
            self._pacer.wait_turn()
        try:
            reply = self._tools.bridge.call(BATCH_RPC_METHOD, rpc.to_params(), rpc.timeout_sec)
        except ExtensionNotConnectedError as error:
            raise ProviderError(str(error), ProviderErrorKind.NOT_CONNECTED) from error
        except TimeoutError as error:
            raise ProviderError(
                f"Google Flow did not answer within {rpc.timeout_sec:g} s",
                ProviderErrorKind.NO_ANSWER,
            ) from error
        return read_reply_text(reply)


def to_input_paths(task: MediaTask) -> list[Path]:
    if task.media_kind is MediaKind.IMAGE:
        return list(task.inputs.references)
    if task.media_kind is MediaKind.EDIT_IMAGE:
        if task.inputs.source_image is None:
            raise ProviderError("An edit needs the image to edit", ProviderErrorKind.FATAL)
        return [task.inputs.source_image, *task.inputs.references]
    if task.media_kind is MediaKind.VIDEO:
        if task.inputs.start_frame is None:
            raise ProviderError("A clip needs a start image", ProviderErrorKind.FATAL)
        return [task.inputs.start_frame]
    raise ProviderError(f"Google Flow does not make {task.media_kind}", ProviderErrorKind.FATAL)


def to_image_generation(task: MediaTask, project_id: str, media_ids: list[str]) -> ImageGeneration:
    is_edit = task.media_kind is MediaKind.EDIT_IMAGE
    return ImageGeneration(
        prompt=task.prompt,
        project_id=project_id,
        model_id=task.model.id,
        aspect=IMAGE_ASPECT_PORTRAIT if task.aspect == PORTRAIT_ASPECT else IMAGE_ASPECT_LANDSCAPE,
        reference_media_ids=tuple(media_ids[1:] if is_edit else media_ids),
        base_media_id=media_ids[0] if is_edit else None,
    )


def to_video_generation(task: MediaTask, project_id: str, start_media_id: str) -> VideoGeneration:
    model_id = (
        task.model.id
        if task.clip_length_s is None
        else task.model.id_for_clip_length(task.clip_length_s)
    )
    if CLIP_LENGTH_PLACEHOLDER in model_id:
        raise ProviderError(f"{task.model.label} needs a clip length", ProviderErrorKind.FATAL)
    return VideoGeneration(
        prompt=task.prompt,
        project_id=project_id,
        model_id=model_id,
        aspect=VIDEO_ASPECT_PORTRAIT if task.aspect == PORTRAIT_ASPECT else VIDEO_ASPECT_LANDSCAPE,
        start_media_id=start_media_id,
    )


def to_external_id(project_id: str, operation_id: str) -> str:
    return f"{project_id}{EXTERNAL_ID_SEPARATOR}{operation_id}"


def to_operation_location(external_id: str) -> OperationLocation:
    project_id, separator, operation_id = external_id.partition(EXTERNAL_ID_SEPARATOR)
    if not separator or not project_id or not operation_id:
        raise ProviderError(UNKNOWN_OPERATION_MESSAGE, ProviderErrorKind.FATAL)
    return OperationLocation(project_id, operation_id)


def is_worth_listing(operation: FlowOperation | None, poll_round: int) -> bool:
    return (
        operation is None
        or operation.is_done
        or operation.has_complaint
        or poll_round % LISTING_EVERY_POLL_ROUNDS == 0
    )


def read_reply_text(reply: Mapping[str, Any]) -> str:
    error_text = str(reply.get(ERROR_KEY) or "")
    data = reply.get(DATA_KEY)
    data_text = data if isinstance(data, str) else ""
    if error_text:
        failure = FlowFailure(f"{error_text} {data_text}".lower(), shorten_detail(error_text))
        raise to_provider_error(failure)
    return data_text


def to_rpc_failure(error: FlowRpcError, answer_text: str) -> FlowFailure:
    return FlowFailure(
        f"{answer_text} [rpc code {error.code}]".lower(),
        shorten_detail(f"{error.rpc_id} answered error code {error.detail!r}"),
    )


def to_provider_error(failure: FlowFailure) -> ProviderError:
    for rule in FAILURE_RULES:
        if any(marker in failure.search_text for marker in rule.markers):
            return ProviderError(rule.message.format(detail=failure.detail), rule.kind)
    return ProviderError(f"Google Flow failed: {failure.detail}")


def shorten_detail(text: str) -> str:
    first_line = " ".join(text.strip().partition("\n")[0].split())
    return LONG_TOKEN_PATTERN.sub(LONG_TOKEN_REPLACEMENT, first_line)[:DETAIL_TEXT_LIMIT]


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
