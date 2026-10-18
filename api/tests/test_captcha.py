from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.common.captcha import (
    CAPTCHA_VERIFY_URLS,
    CaptchaService,
    DisabledCaptchaService,
    create_captcha_service,
    require_captcha,
)
from app.config import Settings

SECRET = "secret-key"


def build_http_client(verify_response: dict) -> MagicMock:
    http_client = MagicMock(spec=httpx.Client)
    http_client.post.return_value.json.return_value = verify_response
    return http_client


@pytest.fixture
def accepting_http_client():
    return build_http_client({"success": True})


@pytest.fixture
def accepted_verification(accepting_http_client):
    return CaptchaService("turnstile", SECRET, accepting_http_client).verify("token-1")


@pytest.fixture
def empty_token_verification(accepting_http_client):
    return CaptchaService("turnstile", SECRET, accepting_http_client).verify("")


@pytest.fixture
def rejected_verification():
    return CaptchaService("hcaptcha", SECRET, build_http_client({"success": False})).verify("t")


@pytest.fixture
def network_failure_verification():
    http_client = MagicMock(spec=httpx.Client)
    http_client.post.side_effect = httpx.ConnectError("offline")
    return CaptchaService("recaptcha", SECRET, http_client).verify("t")


@pytest.fixture
def non_json_verification():
    http_client = MagicMock(spec=httpx.Client)
    http_client.post.return_value.json.side_effect = ValueError("not json")
    return CaptchaService("turnstile", SECRET, http_client).verify("t")


@pytest.fixture
def rejected_request_error():
    captcha_service = MagicMock(spec=CaptchaService)
    captcha_service.verify.return_value = False
    with pytest.raises(HTTPException) as caught:
        require_captcha(captcha_service, "bad-token")
    return caught.value


@pytest.fixture
def accepted_request_result():
    captcha_service = MagicMock(spec=CaptchaService)
    captcha_service.verify.return_value = True
    return require_captcha(captcha_service, "good-token")


@pytest.fixture
def disabled_verification():
    return DisabledCaptchaService().verify("")


@pytest.fixture
def enabled_captcha_service(accepting_http_client):
    return create_captcha_service(
        Settings(database_url="sqlite://", captcha_enabled=True), accepting_http_client
    )


@pytest.fixture
def disabled_captcha_service(accepting_http_client):
    return create_captcha_service(
        Settings(database_url="sqlite://", captcha_enabled=False), accepting_http_client
    )


def test_verify_accepts_token_the_provider_confirms(accepted_verification):
    assert accepted_verification is True


def test_verify_posts_secret_and_token_to_provider_url(
    accepting_http_client, accepted_verification
):
    accepting_http_client.post.assert_called_once_with(
        CAPTCHA_VERIFY_URLS["turnstile"], data={"secret": SECRET, "response": "token-1"}
    )


def test_verify_rejects_empty_token_without_calling_provider(
    accepting_http_client, empty_token_verification
):
    assert empty_token_verification is False
    accepting_http_client.post.assert_not_called()


def test_verify_rejects_token_the_provider_refuses(rejected_verification):
    assert rejected_verification is False


def test_verify_rejects_when_provider_is_unreachable(network_failure_verification):
    assert network_failure_verification is False


def test_verify_rejects_when_provider_answers_non_json(non_json_verification):
    assert non_json_verification is False


def test_require_captcha_answers_403_on_rejected_token(rejected_request_error):
    assert rejected_request_error.status_code == 403


def test_require_captcha_passes_accepted_token(accepted_request_result):
    assert accepted_request_result is None


def test_disabled_captcha_accepts_a_missing_token(disabled_verification):
    assert disabled_verification is True


def test_create_captcha_service_verifies_with_the_provider_when_enabled(enabled_captcha_service):
    assert isinstance(enabled_captcha_service, CaptchaService)


def test_create_captcha_service_skips_verification_when_disabled(disabled_captcha_service):
    assert isinstance(disabled_captcha_service, DisabledCaptchaService)
