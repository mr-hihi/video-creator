import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

LAST_VISIBLE_KEY_CHARS = 4


class SecretBox:
    def __init__(self, secret_key: str):
        self._fernet = _build_fernet(secret_key) if secret_key else None

    @property
    def is_ready(self) -> bool:
        return self._fernet is not None

    def encrypt(self, plain_text: str) -> bytes:
        if self._fernet is None:
            raise RuntimeError("SecretBox has no secret key")
        return self._fernet.encrypt(plain_text.encode("utf-8"))

    def decrypt(self, token: bytes) -> str | None:
        if self._fernet is None:
            return None
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken:
            return None


def to_last_visible_chars(api_key: str) -> str:
    return api_key[-LAST_VISIBLE_KEY_CHARS:]


def redact_secret(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "***")


def _build_fernet(secret_key: str) -> Fernet:
    digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
