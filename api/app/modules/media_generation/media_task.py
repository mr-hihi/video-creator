from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind


class ProviderErrorKind(StrEnum):
    RETRYABLE = "retryable"
    NO_ANSWER = "no_answer"
    INPUT_EXPIRED = "input_expired"
    NOT_CONNECTED = "not_connected"
    CAPTCHA = "captcha"
    UNUSUAL_ACTIVITY = "unusual_activity"
    FATAL = "fatal"


class ProviderError(Exception):
    def __init__(self, message: str, kind: ProviderErrorKind = ProviderErrorKind.RETRYABLE):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class MediaInputs:
    references: tuple[Path, ...] = ()
    source_image: Path | None = None
    start_frame: Path | None = None
    voice_sample: Path | None = None
    consent_clip: Path | None = None


@dataclass(frozen=True)
class MediaTask:
    request_id: str
    media_kind: MediaKind
    model: CatalogModel
    api_key: str | None
    base_url: str | None
    prompt: str
    inputs: MediaInputs
    aspect: str | None = None
    clip_length_s: int | None = None
    language: str | None = None
    min_length_s: int | None = None
    sample_text: str | None = None
    flow_project_id: str | None = None
    reference_kinds: tuple[str, ...] = ()
    voice_name: str | None = None
    provider_voice_id: str | None = None


@dataclass(frozen=True)
class MediaResult:
    content: bytes
    file_extension: str
    provider_voice_id: str | None = None


@dataclass(frozen=True)
class SubmitOutcome:
    external_id: str | None = None
    result: MediaResult | None = None


@dataclass(frozen=True)
class PollOutcome:
    is_done: bool
    result: MediaResult | None = field(default=None)
