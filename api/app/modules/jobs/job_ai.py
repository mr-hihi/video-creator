from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.ai_models.ai_calls import AiStepGroup, InputMode

INPUT_MODE_OPTION_KEY = "inputMode"
MARKDOWN_AI_GROUPS = (AiStepGroup.MOMENTS,)
FILM_ANALYSIS_AI_GROUPS = (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS)
RERUN_AI_GROUPS = (AiStepGroup.FILM_ANALYSIS,)


@dataclass(frozen=True)
class AiGroupCheck:
    groups: tuple[AiStepGroup, ...]
    google_groups: tuple[AiStepGroup, ...] = ()


FULL_VIDEO_AI_CHECK = AiGroupCheck(
    groups=(AiStepGroup.FILM_ANALYSIS,), google_groups=(AiStepGroup.FILM_ANALYSIS,)
)


def get_job_input_mode(options: Mapping[str, Any]) -> InputMode:
    return InputMode(options.get(INPUT_MODE_OPTION_KEY, InputMode.SUBTITLES))


def to_notes_ai_check(groups: Iterable[AiStepGroup], input_mode: InputMode) -> AiGroupCheck:
    if input_mode is InputMode.WHOLE_VIDEO:
        return AiGroupCheck(groups=(*groups, AiStepGroup.AUDIO), google_groups=(AiStepGroup.AUDIO,))
    return AiGroupCheck(groups=tuple(groups))


def to_film_analysis_ai_check(input_mode: InputMode) -> AiGroupCheck:
    if input_mode is InputMode.FULL_VIDEO:
        return FULL_VIDEO_AI_CHECK
    return to_notes_ai_check(FILM_ANALYSIS_AI_GROUPS, input_mode)


def to_rerun_ai_check(source_input_mode: InputMode) -> AiGroupCheck:
    if source_input_mode is InputMode.FULL_VIDEO:
        return FULL_VIDEO_AI_CHECK
    return AiGroupCheck(groups=RERUN_AI_GROUPS)
