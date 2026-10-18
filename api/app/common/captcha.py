import logging
from typing import Annotated, Protocol

import httpx
from fastapi import Depends, Header, HTTPException, Request, status

from app.config import CaptchaProvider, Settings

CAPTCHA_VERIFY_URLS: dict[CaptchaProvider, str] = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
    "hcaptcha": "https://api.hcaptcha.com/siteverify",
}
CAPTCHA_TIMEOUT_SEC = 10.0

logger = logging.getLogger(__name__)


class CaptchaVerifier(Protocol):
    def verify(self, token: str) -> bool: ...


class DisabledCaptchaService:
    def verify(self, token: str) -> bool:
        return True


class CaptchaService:
    def __init__(self, provider: CaptchaProvider, secret: str, http_client: httpx.Client):
        self._verify_url = CAPTCHA_VERIFY_URLS[provider]
        self._secret = secret
        self._http_client = http_client

    def verify(self, token: str) -> bool:
        if not token:
            return False
        try:
            response = self._http_client.post(
                self._verify_url, data={"secret": self._secret, "response": token}
            )
            return response.json().get("success") is True
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Captcha verification request failed: %s", error)
            return False


def create_captcha_http_client() -> httpx.Client:
    return httpx.Client(timeout=CAPTCHA_TIMEOUT_SEC)


def create_captcha_service(settings: Settings, http_client: httpx.Client) -> CaptchaVerifier:
    if not settings.captcha_enabled:
        logger.warning("Captcha is disabled (CAPTCHA_ENABLED=false); every token is accepted")
        return DisabledCaptchaService()
    return CaptchaService(settings.captcha_provider, settings.captcha_secret, http_client)


def get_captcha_service(request: Request) -> CaptchaVerifier:
    return request.app.state.container.captcha_service


def require_captcha(
    captcha_service: Annotated[CaptchaVerifier, Depends(get_captcha_service)],
    x_captcha_token: Annotated[str, Header()] = "",
) -> None:
    if not captcha_service.verify(x_captcha_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Captcha verification failed")
