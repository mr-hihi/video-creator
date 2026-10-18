from collections.abc import Mapping
from typing import Any

from app.modules.ai_models.ai_calls import AiStepGroup, InputMode

INPUT_MODE_OPTION_KEY = "inputMode"
MARKDOWN_AI_GROUPS = (AiStepGroup.MOMENTS,)
FILM_ANALYSIS_AI_GROUPS = (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS)
RERUN_AI_GROUPS = (AiStepGroup.FILM_ANALYSIS,)


def get_job_input_mode(options: Mapping[str, Any]) -> InputMode:
    return InputMode(options.get(INPUT_MODE_OPTION_KEY, InputMode.SUBTITLES))
