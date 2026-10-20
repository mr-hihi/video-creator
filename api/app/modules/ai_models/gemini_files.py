import logging
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.modules.ai_models.ai_calls import AiCallError, AiLimits, AttachedMedia
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.ai_models.streamed_answers import (
    CONNECT_TIMEOUT_SEC,
    JSON_CONTENT_TYPE,
    to_timeout_message,
)
from app.modules.providers.connection_tester import describe_error_response
from app.modules.providers.provider_catalog import ProviderId
from app.modules.providers.secret_box import redact_secret

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
API_KEY_HEADER = "x-goog-api-key"
UPLOAD_URL_HEADER = "x-goog-upload-url"
ACTIVE_STATE = "ACTIVE"
FAILED_STATE = "FAILED"
FILE_POLL_INTERVAL_SEC = 1.0
UPLOAD_CHUNK_BYTES = 1024 * 1024
GEMINI_AI_NAME = to_ai_name(ProviderId.GOOGLE)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadedFile:
    name: str
    uri: str
    media: AttachedMedia


@dataclass(frozen=True)
class FileCall:
    api_key: str
    limits: AiLimits
    started_at: float


class GeminiFiles:
    def __init__(
        self, http_client: httpx.Client, poll_interval_sec: float = FILE_POLL_INTERVAL_SEC
    ):
        self._http_client = http_client
        self._poll_interval_sec = poll_interval_sec

    def upload(self, media: AttachedMedia, call: FileCall) -> UploadedFile:
        with http_errors_as_call_errors(media, call):
            upload_url = self._start_upload(media, call)
            stored_file = self._send_bytes(media, upload_url, call)
        try:
            with http_errors_as_call_errors(media, call):
                return self._wait_until_active(media, stored_file, call)
        except AiCallError:
            self.delete(stored_file["name"], call.api_key)
            raise

    def delete(self, name: str, api_key: str) -> None:
        try:
            response = self._http_client.delete(
                to_file_url(name), headers={API_KEY_HEADER: api_key}, timeout=CONNECT_TIMEOUT_SEC
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            logger.warning(
                "Could not delete Gemini file %s: %s", name, redact_secret(str(error), api_key)
            )

    def _start_upload(self, media: AttachedMedia, call: FileCall) -> str:
        response = self._http_client.post(
            GEMINI_UPLOAD_URL,
            headers={
                API_KEY_HEADER: call.api_key,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(media.path.stat().st_size),
                "X-Goog-Upload-Header-Content-Type": media.mime_type,
                "Content-Type": JSON_CONTENT_TYPE,
            },
            json={"file": {"display_name": media.path.name}},
            timeout=to_remaining_timeout(call),
        )
        ensure_accepted(response, media, call)
        upload_url = response.headers.get(UPLOAD_URL_HEADER)
        if not upload_url:
            raise AiCallError(to_refusal_message(media, "no upload URL"))
        return upload_url

    def _send_bytes(self, media: AttachedMedia, upload_url: str, call: FileCall) -> dict[str, Any]:
        response = self._http_client.post(
            upload_url,
            headers={
                API_KEY_HEADER: call.api_key,
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
                "Content-Length": str(media.path.stat().st_size),
            },
            content=read_file_chunks(media.path),
            timeout=to_remaining_timeout(call),
        )
        ensure_accepted(response, media, call)
        return response_to_stored_file(response, media)

    def _wait_until_active(
        self, media: AttachedMedia, stored_file: Mapping[str, Any], call: FileCall
    ) -> UploadedFile:
        while True:
            state = stored_file.get("state")
            if state == ACTIVE_STATE:
                return to_uploaded_file(stored_file, media)
            if state == FAILED_STATE:
                raise AiCallError(to_refusal_message(media, FAILED_STATE))
            if to_remaining_sec(call) <= self._poll_interval_sec:
                raise AiCallError(to_timeout_message(GEMINI_AI_NAME, call.limits))
            time.sleep(self._poll_interval_sec)
            stored_file = self._read_file(media, stored_file["name"], call)

    def _read_file(self, media: AttachedMedia, name: str, call: FileCall) -> dict[str, Any]:
        response = self._http_client.get(
            to_file_url(name),
            headers={API_KEY_HEADER: call.api_key},
            timeout=to_remaining_timeout(call),
        )
        ensure_accepted(response, media, call)
        return response_to_stored_file(response, media)


@contextmanager
def http_errors_as_call_errors(media: AttachedMedia, call: FileCall) -> Iterator[None]:
    try:
        yield
    except httpx.TimeoutException as error:
        raise AiCallError(to_timeout_message(GEMINI_AI_NAME, call.limits)) from error
    except httpx.HTTPError as error:
        message = redact_secret(to_refusal_message(media, str(error)), call.api_key)
        raise AiCallError(message) from error


def to_file_url(name: str) -> str:
    return f"{GEMINI_BASE_URL}/{quote(name, safe='/')}"


def to_uploaded_file(stored_file: Mapping[str, Any], media: AttachedMedia) -> UploadedFile:
    uri = stored_file.get("uri")
    if not isinstance(uri, str) or not uri:
        raise AiCallError(to_refusal_message(media, "no file URI in the answer"))
    return UploadedFile(name=stored_file["name"], uri=uri, media=media)


def to_media_word(media: AttachedMedia) -> str:
    return media.mime_type.split("/", 1)[0]


def to_refusal_message(media: AttachedMedia, reason: str) -> str:
    return f"{GEMINI_AI_NAME} could not take the {to_media_word(media)}: {reason}"


def ensure_accepted(response: httpx.Response, media: AttachedMedia, call: FileCall) -> None:
    if response.is_success:
        return
    message = to_refusal_message(media, describe_error_response(response))
    raise AiCallError(redact_secret(message, call.api_key))


def response_to_stored_file(response: httpx.Response, media: AttachedMedia) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as error:
        raise AiCallError(to_refusal_message(media, "the answer is not JSON")) from error
    stored_file = body.get("file", body) if isinstance(body, dict) else None
    if not isinstance(stored_file, dict) or not isinstance(stored_file.get("name"), str):
        raise AiCallError(to_refusal_message(media, "no file in the answer"))
    return stored_file


def to_remaining_sec(call: FileCall) -> float:
    return call.limits.timeout_sec - (time.monotonic() - call.started_at)


def to_remaining_timeout(call: FileCall) -> httpx.Timeout:
    remaining_sec = to_remaining_sec(call)
    if remaining_sec <= 0:
        raise AiCallError(to_timeout_message(GEMINI_AI_NAME, call.limits))
    return httpx.Timeout(remaining_sec, connect=min(CONNECT_TIMEOUT_SEC, remaining_sec))


def read_file_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as source:
        while chunk := source.read(UPLOAD_CHUNK_BYTES):
            yield chunk
