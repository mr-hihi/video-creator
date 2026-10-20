from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.ai_models.ai_calls import AiStepGroup
from app.modules.ai_models.step_models import AiStepModels
from app.modules.app_settings.service import AppSettingService
from app.modules.jobs.errors import JobPresetNotFoundError
from app.modules.jobs.film_analysis.job_options import to_max_frames_options
from app.modules.jobs.job_ai import (
    INPUT_MODE_OPTION_KEY,
    AiGroupCheck,
    to_film_analysis_ai_check,
    to_notes_ai_check,
)
from app.modules.jobs.job_prompts import FILM_ANALYSIS_PROMPT_KEYS, build_prompt_options
from app.modules.jobs.models import Job, JobOutput
from app.modules.jobs.repository import JobRepository
from app.modules.prompt_presets.errors import PromptPresetNotFoundError
from app.modules.prompt_presets.prompt_texts import PromptKey
from app.modules.prompt_presets.service import PromptPresetService


@dataclass(frozen=True)
class JobIntakeTools:
    repository: JobRepository
    preset_service: PromptPresetService
    settings_service: AppSettingService
    step_models: AiStepModels
    notify_worker: Callable[[], None]


class JobIntake:
    def __init__(self, tools: JobIntakeTools):
        self._tools = tools

    def resolve_prompt_options(
        self, preset_id: str | None, prompt_keys: Iterable[PromptKey]
    ) -> dict[str, Any]:
        try:
            snapshot = self._tools.preset_service.get_job_snapshot(preset_id)
        except PromptPresetNotFoundError as error:
            raise JobPresetNotFoundError(error.preset_id) from error
        return build_prompt_options(snapshot, prompt_keys)

    def resolve_ai_options(self, groups: Iterable[AiStepGroup]) -> dict[str, Any]:
        self._tools.step_models.ensure_set_up(groups)
        return {INPUT_MODE_OPTION_KEY: self._tools.settings_service.get_input_mode().value}

    def resolve_film_analysis_options(
        self, preset_id: str | None, requested_max_frames: int | None
    ) -> dict[str, Any]:
        input_mode = self._tools.settings_service.get_film_analysis_input_mode()
        max_frames_options = to_max_frames_options(requested_max_frames, input_mode)
        prompt_options = self.resolve_prompt_options(preset_id, FILM_ANALYSIS_PROMPT_KEYS)
        self.ensure_ai_set_up(to_film_analysis_ai_check(input_mode))
        return {
            **max_frames_options,
            **prompt_options,
            INPUT_MODE_OPTION_KEY: input_mode.value,
        }

    def resolve_film_clone_ai_options(self, groups: Iterable[AiStepGroup]) -> dict[str, Any]:
        input_mode = self._tools.settings_service.get_film_clone_input_mode()
        self.ensure_ai_set_up(to_notes_ai_check(groups, input_mode))
        return {INPUT_MODE_OPTION_KEY: input_mode.value}

    def ensure_ai_set_up(self, check: AiGroupCheck) -> None:
        self._tools.step_models.ensure_set_up(check.groups, check.google_groups)

    def enqueue(self, job: Job, outputs: Sequence[JobOutput] = ()) -> Job:
        added_job = self._tools.repository.add(job, outputs)
        self._tools.notify_worker()
        return added_job
