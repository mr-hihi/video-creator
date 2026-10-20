from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from app.modules.providers.provider_catalog import ProviderId


class InputMode(StrEnum):
    SUBTITLES = "subtitles"
    WHOLE_VIDEO = "whole_video"
    FULL_VIDEO = "full_video"


MOMENT_INPUT_MODES = (InputMode.SUBTITLES, InputMode.WHOLE_VIDEO)


class AiStepGroup(StrEnum):
    MOMENTS = "moments"
    AUDIO = "audio"
    FILM_ANALYSIS = "filmAnalysis"
    FILM_SCRIPT = "filmScript"
    FILM_CLONE = "filmClone"


@dataclass(frozen=True)
class AiModelChoice:
    provider: ProviderId
    model: str


@dataclass(frozen=True)
class AttachedImage:
    label: str
    path: Path


@dataclass(frozen=True)
class AttachedMedia:
    label: str
    path: Path
    mime_type: str


@dataclass(frozen=True)
class AiAsk:
    instructions: str
    message: str
    images: Sequence[AttachedImage] = ()
    reply_schema: Mapping[str, Any] | None = None
    media: Sequence[AttachedMedia] = ()


def do_nothing() -> None:
    return None


@dataclass(frozen=True)
class AiLimits:
    timeout_sec: float
    silence_limit_sec: float | None = None
    on_output: Callable[[], None] = do_nothing


class AiCallError(Exception):
    pass


class AiProviderNotSetUpError(AiCallError):
    def __init__(self, provider_name: str):
        super().__init__(f"{provider_name} is not set up — open Settings")


class GoogleModelRequiredError(AiCallError):
    def __init__(self, group_label: str):
        super().__init__(f"{group_label} needs a Google AI model — open Settings")
