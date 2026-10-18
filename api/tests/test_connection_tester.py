from types import SimpleNamespace

import httpx
import pytest

from app.modules.providers.connection_tester import (
    ConnectionCheck,
    ProviderConnectionTester,
    describe_error_response,
)
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.provider_catalog import PROVIDER_SPECS_BY_ID, ProviderId

API_KEY = "sk-live-SECRET-9999"


def build_tester(handler, extension: FlowExtensionBridge | None = None):
    calls = []

    def recording_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(recording_handler))
    tester = ProviderConnectionTester(client, extension or FlowExtensionBridge(), 15)
    return tester, calls


def run_check(handler, provider_id: ProviderId, api_key=None, base_url=None):
    tester, calls = build_tester(handler)
    outcome = tester.test(
        ConnectionCheck(spec=PROVIDER_SPECS_BY_ID[provider_id], api_key=api_key, base_url=base_url)
    )
    return SimpleNamespace(outcome=outcome, calls=calls)


def answer_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


def answer_rejected_key(request: httpx.Request) -> httpx.Response:
    return httpx.Response(401, json={"error": {"message": f"API key not valid: {API_KEY}"}})


def raise_connect_error(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("Connection refused")


@pytest.fixture
def google_check():
    return run_check(answer_ok, ProviderId.GOOGLE, api_key=API_KEY)


@pytest.fixture
def fal_check():
    return run_check(answer_ok, ProviderId.FAL, api_key=API_KEY)


@pytest.fixture
def rejected_key_check():
    return run_check(answer_rejected_key, ProviderId.ELEVENLABS, api_key=API_KEY)


@pytest.fixture
def unreachable_api_check():
    return run_check(raise_connect_error, ProviderId.REPLICATE, api_key=API_KEY)


@pytest.fixture
def sd_check():
    return run_check(answer_ok, ProviderId.SD_WEBUI, base_url="http://127.0.0.1:7860/")


@pytest.fixture
def adapter_down_check():
    return run_check(
        lambda request: httpx.Response(503, text="starting"),
        ProviderId.ACE_STEP,
        base_url="http://127.0.0.1:8001",
    )


@pytest.fixture
def unreachable_local_check():
    return run_check(raise_connect_error, ProviderId.YUE, base_url="http://127.0.0.1:8002")


@pytest.fixture
def connected_flow_outcome():
    extension = FlowExtensionBridge()
    extension.register_connection(lambda command: None)
    tester, _calls = build_tester(answer_ok, extension)
    return tester.test(
        ConnectionCheck(
            spec=PROVIDER_SPECS_BY_ID[ProviderId.GOOGLE_FLOW], api_key=None, base_url=None
        )
    )


@pytest.fixture
def disconnected_flow_outcome():
    tester, _calls = build_tester(answer_ok)
    return tester.test(
        ConnectionCheck(
            spec=PROVIDER_SPECS_BY_ID[ProviderId.GOOGLE_FLOW], api_key=None, base_url=None
        )
    )


@pytest.fixture(
    params=[
        (httpx.Response(400, json={"detail": "Bad input"}), "Bad input"),
        (httpx.Response(400, json={"error": "quota"}), "quota"),
        (httpx.Response(400, json={"detail": {"message": "nested"}}), "nested"),
        (httpx.Response(400, json=["list"]), "HTTP 400"),
        (httpx.Response(400, json={"other": 1}), "HTTP 400"),
    ]
)
def described_error(request):
    response, expected = request.param
    return SimpleNamespace(actual=describe_error_response(response), expected=expected)


@pytest.fixture(
    params=[
        (
            httpx.Response(400, text=" Blocked by the content filter \n"),
            "Blocked by the content filter",
        ),
        (httpx.Response(500, text="  "), "HTTP 500"),
        (httpx.Response(502, text="x" * 600), "x" * 500),
    ]
)
def described_text_error(request):
    response, expected = request.param
    return SimpleNamespace(actual=describe_error_response(response), expected=expected)


def test_google_check_lists_models_with_the_key_header(google_check):
    assert google_check.outcome.is_ok is True
    assert (
        str(google_check.calls[0].url) == "https://generativelanguage.googleapis.com/v1beta/models"
    )
    assert google_check.calls[0].headers["x-goog-api-key"] == API_KEY


def test_fal_check_reads_billing_with_a_key_header(fal_check):
    assert str(fal_check.calls[0].url) == "https://api.fal.ai/v1/account/billing?expand=credits"
    assert fal_check.calls[0].headers["authorization"] == f"Key {API_KEY}"


def test_rejected_key_reports_the_message_without_the_key(rejected_key_check):
    assert rejected_key_check.outcome.is_ok is False
    assert rejected_key_check.outcome.error == "API key not valid: ***"
    assert str(rejected_key_check.calls[0].url) == "https://api.elevenlabs.io/v1/user"


def test_unreachable_api_reports_the_error(unreachable_api_check):
    assert unreachable_api_check.outcome.is_ok is False
    assert unreachable_api_check.outcome.error == "Connection refused"


def test_sd_check_reads_the_model_list(sd_check):
    assert sd_check.outcome.is_ok is True
    assert str(sd_check.calls[0].url) == "http://127.0.0.1:7860/sdapi/v1/sd-models"


def test_adapter_check_fails_on_a_non_2xx_health(adapter_down_check):
    assert adapter_down_check.outcome.is_ok is False
    assert str(adapter_down_check.calls[0].url) == "http://127.0.0.1:8001/health"


def test_unreachable_local_server_names_the_url(unreachable_local_check):
    assert unreachable_local_check.outcome.error == (
        "Could not reach http://127.0.0.1:8002/health: Connection refused"
    )


def test_flow_check_reads_the_extension_state(connected_flow_outcome, disconnected_flow_outcome):
    assert connected_flow_outcome.is_ok is True
    assert disconnected_flow_outcome.is_ok is False
    assert disconnected_flow_outcome.error == "The Google Flow extension is not connected"


def test_describe_error_response_finds_the_message(described_error):
    assert described_error.actual == described_error.expected


def test_describe_error_response_falls_back_to_the_text_body(described_text_error):
    assert described_text_error.actual == described_text_error.expected
