import json
import random
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

RPC_CREATE_PROJECT = "jHPbke"
RPC_UPLOAD_IMAGE = "maseQ"
RPC_GENERATE_IMAGE = "ogiZ0b"
RPC_GENERATE_VIDEO = "eb1hJf"
RPC_OPERATION = "jwpduf"
RPC_PROJECT_MEDIA = "Zzl0ze"
RPC_MEDIA = "as29s"

CAPTCHA_IMAGE = "IMAGE_GENERATION"
CAPTCHA_VIDEO = "VIDEO_GENERATION"
CAPTCHA_SLOT = "__CAPTCHA__"

CREATE_PROJECT_TIMEOUT_SEC = 60.0
UPLOAD_TIMEOUT_SEC = 120.0
GENERATE_IMAGE_TIMEOUT_SEC = 300.0
GENERATE_VIDEO_TIMEOUT_SEC = 120.0
OPERATION_TIMEOUT_SEC = 60.0
PROJECT_MEDIA_TIMEOUT_SEC = 120.0
MEDIA_TIMEOUT_SEC = 60.0

SURFACE_ID = 22
CAPTCHA_CONTEXT_FLAG = 1
IMAGE_BATCH_FLAG = 1
UPLOAD_FLAG = 1
VIDEO_CLIENT_DESCRIPTOR_TYPE = 2
PROJECT_MEDIA_PAGE = (1,)
REFERENCE_INPUT_TYPE = 1
BASE_IMAGE_INPUT_TYPE = 2
FULL_FRAME_CROP = (None, None, 1, 1)
MAX_SEED = 10**9

IMAGE_ASPECT_PORTRAIT = 2
IMAGE_ASPECT_LANDSCAPE = 3
VIDEO_ASPECT_PORTRAIT = 1
VIDEO_ASPECT_LANDSCAPE = 2

DEFAULT_PROJECT_TITLE = "video-tool project"
PROJECT_TITLE_LIMIT = 160
FLOW_PROJECT_ID_MAX_LENGTH = 36
ANSWER_SENTINEL = ")]}'"
ENVELOPE_TAG = "wrb.fr"
ENVELOPE_RPC_SLOT = 1
ENVELOPE_PAYLOAD_SLOT = 2
ENVELOPE_ERROR_SLOT = 5
MEDIA_HOST = "flow-content.google"
IMAGE_URL_PART = f"{MEDIA_HOST}/image/"
VIDEO_URL_PART = f"{MEDIA_HOST}/video/"
OPERATION_DONE_STATUS = "CAE"
COMPLAINT_OUTCOME = 4
OPERATION_RECORDS_SLOT = 2
OPERATION_PROJECT_SLOT = 1
OPERATION_STATUS_SLOT = 3
OPERATION_DETAIL_SLOT = 5
OPERATION_OUTCOME_SLOT = 8
LISTING_WINDOW_CHARS = 800
LISTING_MEDIA_SLOT_PATTERN = re.compile(r'null,null,\\?"([0-9a-fA-F-]{36})\\?"')
COMPLAINT_FALLBACK = "operation failed without a message"


class FlowAnswerError(Exception):
    pass


class FlowRpcError(Exception):
    def __init__(self, rpc_id: str, detail: Any):
        super().__init__(f"{rpc_id} failed: {detail!r}")
        self.rpc_id = rpc_id
        self.detail = detail

    @property
    def code(self) -> Any:
        if isinstance(self.detail, list) and self.detail:
            return self.detail[0]
        return self.detail


@dataclass(frozen=True)
class FlowRpc:
    rpc_id: str
    freq: str
    timeout_sec: float
    captcha_action: str | None = None
    match: str | None = None

    def to_params(self) -> dict[str, str]:
        params = {"rpcid": self.rpc_id, "freq": self.freq}
        if self.captcha_action is not None:
            params["captchaAction"] = self.captcha_action
        if self.match is not None:
            params["match"] = self.match
        return params


@dataclass(frozen=True)
class ImageUpload:
    project_id: str
    image_base64: str
    mime_type: str
    file_name: str


@dataclass(frozen=True)
class ImageGeneration:
    prompt: str
    project_id: str
    model_id: str
    aspect: int
    reference_media_ids: tuple[str, ...]
    base_media_id: str | None = None


@dataclass(frozen=True)
class VideoGeneration:
    prompt: str
    project_id: str
    model_id: str
    aspect: int
    start_media_id: str


@dataclass(frozen=True)
class FlowOperation:
    operation_id: str
    status: str | None
    complaint: str | None

    @property
    def is_done(self) -> bool:
        return self.status == OPERATION_DONE_STATUS

    @property
    def has_complaint(self) -> bool:
        return self.complaint is not None


def build_create_project_rpc(title: str) -> FlowRpc:
    clean_title = " ".join(title.split())[:PROJECT_TITLE_LIMIT] or DEFAULT_PROJECT_TITLE
    inner = ["projects/*", [None, [clean_title]], [None, SURFACE_ID]]
    return FlowRpc(
        RPC_CREATE_PROJECT,
        build_envelope(RPC_CREATE_PROJECT, inner),
        CREATE_PROJECT_TIMEOUT_SEC,
    )


def build_upload_rpc(upload: ImageUpload) -> FlowRpc:
    inner = [
        _to_context(upload.project_id, None),
        upload.image_base64,
        upload.mime_type,
        UPLOAD_FLAG,
        None,
        None,
        None,
        None,
        upload.file_name,
        None,
        _new_client_uuid(),
        _new_client_uuid(),
    ]
    return FlowRpc(
        RPC_UPLOAD_IMAGE,
        build_envelope(RPC_UPLOAD_IMAGE, inner),
        UPLOAD_TIMEOUT_SEC,
        captcha_action=CAPTCHA_IMAGE,
    )


def build_image_rpc(generation: ImageGeneration) -> FlowRpc:
    context = _to_context(generation.project_id, generation.base_media_id)
    item = [
        None,
        None,
        _to_image_inputs(generation) or None,
        random.randint(1, MAX_SEED),
        generation.aspect,
        generation.model_id,
        None,
        context,
        [[[generation.prompt]]],
        None,
        None,
        None,
        None,
        _new_client_uuid(),
    ]
    inner = [None, [item], IMAGE_BATCH_FLAG, context, [_new_client_uuid()]]
    return FlowRpc(
        RPC_GENERATE_IMAGE,
        build_envelope(RPC_GENERATE_IMAGE, inner),
        GENERATE_IMAGE_TIMEOUT_SEC,
        captcha_action=CAPTCHA_IMAGE,
    )


def build_video_rpc(generation: VideoGeneration) -> FlowRpc:
    request = [
        [None, None, [[[generation.prompt]]]],
        generation.model_id,
        generation.aspect,
        None,
        [None, generation.start_media_id, None, None, None, FULL_FRAME_CROP],
        [None, None, None, None, _new_client_uuid(), _new_client_uuid()],
    ]
    inner = [
        [request],
        _to_context(generation.project_id, None),
        [_new_client_uuid(), VIDEO_CLIENT_DESCRIPTOR_TYPE],
    ]
    return FlowRpc(
        RPC_GENERATE_VIDEO,
        build_envelope(RPC_GENERATE_VIDEO, inner),
        GENERATE_VIDEO_TIMEOUT_SEC,
        captcha_action=CAPTCHA_VIDEO,
    )


def build_operation_rpc(operation_id: str) -> FlowRpc:
    inner = [None, None, [[operation_id]]]
    return FlowRpc(RPC_OPERATION, build_envelope(RPC_OPERATION, inner), OPERATION_TIMEOUT_SEC)


def build_project_media_rpc(project_id: str, operation_id: str) -> FlowRpc:
    inner = [f"projects/{project_id}", None, None, None, PROJECT_MEDIA_PAGE]
    return FlowRpc(
        RPC_PROJECT_MEDIA,
        build_envelope(RPC_PROJECT_MEDIA, inner),
        PROJECT_MEDIA_TIMEOUT_SEC,
        match=operation_id,
    )


def build_media_rpc(media_id: str) -> FlowRpc:
    return FlowRpc(RPC_MEDIA, build_envelope(RPC_MEDIA, [media_id]), MEDIA_TIMEOUT_SEC)


def build_envelope(rpc_id: str, inner: Any) -> str:
    inner_text = json.dumps(inner, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(
        [[[rpc_id, inner_text, None, "generic"]]], separators=(",", ":"), ensure_ascii=False
    )


def read_payload(answer_text: str, rpc_id: str) -> Any:
    envelopes = list(_iter_envelopes(answer_text))
    for envelope in envelopes:
        if envelope[ENVELOPE_RPC_SLOT] != rpc_id:
            continue
        payload = _slot(envelope, ENVELOPE_PAYLOAD_SLOT)
        if payload is None:
            raise FlowRpcError(rpc_id, _slot(envelope, ENVELOPE_ERROR_SLOT) or True)
        return json.loads(payload) if isinstance(payload, str) else payload
    raise FlowAnswerError(f"no {rpc_id} answer in the response ({len(envelopes)} others)")


def read_created_project_id(payload: Any) -> str:
    project_id = _slot(payload, 0)
    if not isinstance(project_id, str) or not 0 < len(project_id) <= FLOW_PROJECT_ID_MAX_LENGTH:
        raise FlowAnswerError("the new Flow project carried no id")
    return project_id


def read_uploaded_media_id(payload: Any) -> str:
    media_id = _slot(_slot(payload, 0), 0)
    if not isinstance(media_id, str) or not media_id:
        raise FlowAnswerError("the upload carried no media id")
    return media_id


def read_image_url(payload: Any) -> str:
    image_url = next((text for text in _iter_strings(payload) if IMAGE_URL_PART in text), None)
    if image_url is None:
        raise FlowAnswerError("no image in the answer")
    return image_url


def read_operation(payload: Any) -> FlowOperation:
    record = _slot(_slot(payload, OPERATION_RECORDS_SLOT), 0)
    if not isinstance(record, list) or not record or not isinstance(record[0], str):
        raise FlowAnswerError("the operation carried no record")
    return FlowOperation(
        operation_id=record[0],
        status=_slot(record, OPERATION_STATUS_SLOT),
        complaint=_read_complaint(record),
    )


def find_media_id_in_listing(listing_text: str, operation_id: str) -> str | None:
    start = listing_text.lower().find(operation_id.lower())
    if start == -1:
        return None
    match = LISTING_MEDIA_SLOT_PATTERN.search(listing_text, start, start + LISTING_WINDOW_CHARS)
    return match.group(1) if match else None


def read_video_url(payload: Any) -> str | None:
    return next(
        (
            text
            for text in _iter_strings(payload)
            if text.startswith("https://") and VIDEO_URL_PART in text
        ),
        None,
    )


def _iter_envelopes(answer_text: str) -> Iterator[list[Any]]:
    body = (
        answer_text.split("\n", 1)[-1] if answer_text.startswith(ANSWER_SENTINEL) else answer_text
    )
    decoder = json.JSONDecoder()
    index = 0
    while (start := body.find("[", index)) != -1:
        try:
            chunk, consumed = decoder.raw_decode(body[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        index = start + consumed
        yield from _to_envelopes(chunk)


def _to_envelopes(chunk: Any) -> Iterator[list[Any]]:
    entries = chunk if isinstance(chunk, list) else []
    for entry in entries:
        if isinstance(entry, list) and len(entry) > ENVELOPE_RPC_SLOT and entry[0] == ENVELOPE_TAG:
            yield entry


def _read_complaint(record: list[Any]) -> str | None:
    outcome = _slot(_slot(record, OPERATION_DETAIL_SLOT), OPERATION_OUTCOME_SLOT)
    if not isinstance(outcome, list) or not outcome or outcome[0] != COMPLAINT_OUTCOME:
        return None
    return next(_iter_strings(outcome), COMPLAINT_FALLBACK)


def _iter_strings(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _iter_strings(item)


def _slot(node: Any, index: int) -> Any:
    if isinstance(node, list) and len(node) > index:
        return node[index]
    return None


def _to_context(project_id: str, asset_id: str | None) -> list[Any]:
    return [
        None,
        SURFACE_ID,
        None,
        None,
        asset_id,
        project_id,
        None,
        None,
        None,
        None,
        [CAPTCHA_SLOT, CAPTCHA_CONTEXT_FLAG],
    ]


def _to_image_inputs(generation: ImageGeneration) -> list[list[Any]]:
    base_inputs = (
        []
        if generation.base_media_id is None
        else [_to_image_input(generation.base_media_id, BASE_IMAGE_INPUT_TYPE)]
    )
    return base_inputs + [
        _to_image_input(media_id, REFERENCE_INPUT_TYPE)
        for media_id in generation.reference_media_ids
        if media_id != generation.base_media_id
    ]


def _to_image_input(media_id: str, input_type: int) -> list[Any]:
    return [media_id, None, None, None, input_type]


def _new_client_uuid() -> str:
    return str(uuid.uuid4()).upper()
