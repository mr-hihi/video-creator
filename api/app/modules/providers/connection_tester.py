from dataclasses import dataclass
from typing import Any

import httpx

from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.provider_catalog import ProviderId, ProviderKind, ProviderSpec
from app.modules.providers.secret_box import redact_secret

EXTENSION_NOT_CONNECTED_MESSAGE = "The Google Flow extension is not connected"
HTTP_STATUS_OK_FIRST = 200
HTTP_STATUS_OK_LAST = 299
ERROR_TEXT_LIMIT = 500


@dataclass(frozen=True)
class ApiAuthHeader:
    name: str
    value_prefix: str


@dataclass(frozen=True)
class ApiReadCall:
    url: str
    auth_header: ApiAuthHeader


API_READ_CALLS: dict[ProviderId, ApiReadCall] = {
    ProviderId.GOOGLE: ApiReadCall(
        "https://generativelanguage.googleapis.com/v1beta/models",
        ApiAuthHeader("x-goog-api-key", ""),
    ),
    ProviderId.OPENAI: ApiReadCall(
        "https://api.openai.com/v1/models", ApiAuthHeader("Authorization", "Bearer ")
    ),
    ProviderId.REPLICATE: ApiReadCall(
        "https://api.replicate.com/v1/account", ApiAuthHeader("Authorization", "Bearer ")
    ),
    ProviderId.ELEVENLABS: ApiReadCall(
        "https://api.elevenlabs.io/v1/user", ApiAuthHeader("xi-api-key", "")
    ),
    ProviderId.FAL: ApiReadCall(
        "https://api.fal.ai/v1/account/billing?expand=credits",
        ApiAuthHeader("Authorization", "Key "),
    ),
}
LOCAL_HEALTH_PATHS: dict[ProviderId, str] = {
    ProviderId.SD_WEBUI: "/sdapi/v1/sd-models",
    ProviderId.OMNIVOICE: "/health",
    ProviderId.ACE_STEP: "/health",
    ProviderId.YUE: "/health",
}


@dataclass(frozen=True)
class ConnectionCheck:
    spec: ProviderSpec
    api_key: str | None
    base_url: str | None


@dataclass(frozen=True)
class ConnectionOutcome:
    is_ok: bool
    error: str | None


class ProviderConnectionTester:
    def __init__(
        self, http_client: httpx.Client, extension: FlowExtensionBridge, timeout_sec: float
    ):
        self._http_client = http_client
        self._extension = extension
        self._timeout_sec = timeout_sec

    def test(self, check: ConnectionCheck) -> ConnectionOutcome:
        if check.spec.kind is ProviderKind.EXTENSION:
            return self._test_extension()
        if check.spec.kind is ProviderKind.LOCAL:
            return self._test_local_server(check.spec.id, check.base_url or "")
        return self._test_api_key(check.spec.id, check.api_key or "")

    def _test_extension(self) -> ConnectionOutcome:
        if self._extension.is_connected():
            return ConnectionOutcome(is_ok=True, error=None)
        return ConnectionOutcome(is_ok=False, error=EXTENSION_NOT_CONNECTED_MESSAGE)

    def _test_local_server(self, provider_id: ProviderId, base_url: str) -> ConnectionOutcome:
        url = f"{base_url.rstrip('/')}{LOCAL_HEALTH_PATHS[provider_id]}"
        try:
            response = self._http_client.get(url, timeout=self._timeout_sec)
        except httpx.HTTPError as error:
            return ConnectionOutcome(is_ok=False, error=f"Could not reach {url}: {error}")
        return _to_outcome(response, secret=None)

    def _test_api_key(self, provider_id: ProviderId, api_key: str) -> ConnectionOutcome:
        read_call = API_READ_CALLS[provider_id]
        headers = {read_call.auth_header.name: f"{read_call.auth_header.value_prefix}{api_key}"}
        try:
            response = self._http_client.get(
                read_call.url, headers=headers, timeout=self._timeout_sec
            )
        except httpx.HTTPError as error:
            return ConnectionOutcome(is_ok=False, error=redact_secret(str(error), api_key))
        return _to_outcome(response, secret=api_key)


def _to_outcome(response: httpx.Response, secret: str | None) -> ConnectionOutcome:
    if HTTP_STATUS_OK_FIRST <= response.status_code <= HTTP_STATUS_OK_LAST:
        return ConnectionOutcome(is_ok=True, error=None)
    return ConnectionOutcome(
        is_ok=False, error=redact_secret(describe_error_response(response), secret)
    )


def describe_error_response(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        return response.text.strip()[:ERROR_TEXT_LIMIT] or f"HTTP {response.status_code}"
    return _find_error_message(body) or f"HTTP {response.status_code}"


def _find_error_message(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    for key in ("error", "detail", "message"):
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested_message = _find_error_message(value)
            if nested_message:
                return nested_message
    return None
