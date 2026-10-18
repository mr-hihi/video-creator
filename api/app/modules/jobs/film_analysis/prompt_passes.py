from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.common.sequences import spread_evenly
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiAsk, AiLimits, AiStepGroup, AttachedImage
from app.modules.jobs.film_analysis.notes_passes import WrittenNotes
from app.modules.jobs.job_prompts import get_job_prompt
from app.modules.jobs.models import Job, JobOutputKind, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import IMAGES_DIR_NAME, JobStorage
from app.modules.prompt_presets.prompt_texts import (
    PromptKey,
    build_video_notes_message,
    build_video_notes_message_with_characters,
)
from app.modules.providers.provider_catalog import ProviderId


@dataclass(frozen=True)
class PromptPass:
    step: JobStep
    prompt_key: PromptKey
    output_kind: JobOutputKind


CHARACTER_IMAGE_PASS = PromptPass(
    JobStep.WRITING_CHARACTER_IMAGE_PROMPTS,
    PromptKey.CHARACTER_IMAGE,
    JobOutputKind.CHARACTER_IMAGE_PROMPTS,
)
CHARACTER_VOICE_PASS = PromptPass(
    JobStep.WRITING_CHARACTER_VOICE_PROMPTS,
    PromptKey.CHARACTER_VOICE,
    JobOutputKind.CHARACTER_VOICE_PROMPTS,
)
SCENE_PASS = PromptPass(JobStep.WRITING_SCENE_PROMPTS, PromptKey.SCENE, JobOutputKind.SCENE_PROMPTS)
FRAME_FILE_PATTERN = "*.jpg"


@dataclass(frozen=True)
class PromptPassTools:
    storage: JobStorage
    repository: JobRepository
    ai_caller: AiCaller
    limits: AiLimits
    max_images_by_provider: Mapping[ProviderId, int]


class FilmPromptPasses:
    def __init__(self, tools: PromptPassTools):
        self._tools = tools

    def run(self, job: Job, notes: WrittenNotes, report_step: Callable[[JobStep], None]) -> None:
        video_notes = notes.video_notes
        report_step(CHARACTER_IMAGE_PASS.step)
        character_prompts = self._write(
            job, CHARACTER_IMAGE_PASS, build_video_notes_message(video_notes)
        )
        message_with_characters = build_video_notes_message_with_characters(
            video_notes, character_prompts
        )
        for prompt_pass in (CHARACTER_VOICE_PASS, SCENE_PASS):
            report_step(prompt_pass.step)
            self._write(job, prompt_pass, message_with_characters)

    def _write(self, job: Job, prompt_pass: PromptPass, message: str) -> str:
        choice = self._tools.ai_caller.find_model(AiStepGroup.FILM_ANALYSIS)
        self._tools.repository.save_ai_used(job.id, prompt_pass.step, choice)
        answer = self._tools.ai_caller.ask_for_text(
            choice,
            AiAsk(
                instructions=get_job_prompt(job.options, prompt_pass.prompt_key),
                message=message,
                images=spread_evenly(
                    to_frame_images(self._tools.storage.images_dir(job.id)),
                    self._tools.max_images_by_provider[choice.provider],
                ),
            ),
            self._tools.limits,
        )
        self._tools.repository.save_output(job.id, prompt_pass.output_kind, answer)
        return answer


def to_frame_images(images_dir: Path) -> list[AttachedImage]:
    return [
        AttachedImage(label=f"{IMAGES_DIR_NAME}/{frame_path.name}", path=frame_path)
        for frame_path in sorted(images_dir.glob(FRAME_FILE_PATTERN))
    ]
