import base64
import mimetypes
from pathlib import Path

import httpx

from app.modules.media_generation.media_task import MediaResult, ProviderError, ProviderErrorKind
from app.modules.providers.connection_tester import describe_error_response
from app.modules.providers.secret_box import redact_secret

FALLBACK_MIME_TYPE = "application/octet-stream"
SERVER_ERROR_STATUS_MIN = 500
TOO_MANY_REQUESTS_STATUS = 429
EXTENSIONS_BY_MIME_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
}


def to_mime_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or FALLBACK_MIME_TYPE


def to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def to_data_uri(path: Path) -> str:
    return f"data:{to_mime_type(path)};base64,{to_base64(path)}"


def to_file_extension(mime_type: str, fallback: str) -> str:
    return EXTENSIONS_BY_MIME_TYPE.get(mime_type.split(";")[0].strip().lower(), fallback)


def ensure_success(response: httpx.Response, provider_name: str, api_key: str | None) -> None:
    if response.is_success:
        return
    message = redact_secret(f"{provider_name}: {describe_error_response(response)}", api_key)
    raise ProviderError(message, to_error_kind(response.status_code))


def to_error_kind(status_code: int) -> ProviderErrorKind:
    if status_code >= SERVER_ERROR_STATUS_MIN or status_code == TOO_MANY_REQUESTS_STATUS:
        return ProviderErrorKind.RETRYABLE
    return ProviderErrorKind.FATAL


def download_result(
    http_client: httpx.Client, url: str, fallback_extension: str, headers: dict[str, str] | None
) -> MediaResult:
    try:
        response = http_client.get(url, headers=headers, follow_redirects=True)
    except httpx.HTTPError as error:
        raise ProviderError(
            f"Could not download the result: {error}", ProviderErrorKind.NO_ANSWER
        ) from error
    if not response.is_success:
        raise ProviderError(
            f"Could not download the result: HTTP {response.status_code}",
            to_error_kind(response.status_code),
        )
    return MediaResult(
        content=response.content,
        file_extension=to_file_extension(
            response.headers.get("content-type", ""), fallback_extension
        ),
    )


def send(http_client: httpx.Client, request: httpx.Request, provider_name: str) -> httpx.Response:
    try:
        return http_client.send(request)
    except httpx.TimeoutException as error:
        raise ProviderError(
            f"{provider_name} timed out: {error}", ProviderErrorKind.NO_ANSWER
        ) from error
    except httpx.HTTPError as error:
        raise ProviderError(
            f"{provider_name} could not be reached: {error}", ProviderErrorKind.NO_ANSWER
        ) from error
