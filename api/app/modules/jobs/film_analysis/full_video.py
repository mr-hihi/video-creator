from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import (
    AiAsk,
    AiLimits,
    AiModelChoice,
    AiStepGroup,
    AttachedMedia,
)
from app.modules.film_clones.clone_catalog import LANGUAGE_NAMES_BY_CODE
from app.modules.jobs.errors import NoCompressedVideoError
from app.modules.jobs.film_analysis.media_parts import (
    VIDEO_MEDIA_WORD,
    VIDEO_MIME_TYPE,
    MediaPart,
    find_part_paths,
    to_media_parts,
    to_part_label,
)
from app.modules.jobs.film_analysis.prompt_passes import (
    CHARACTER_IMAGE_PASS,
    CHARACTER_VOICE_PASS,
    SCENE_PASS,
    PromptPass,
)
from app.modules.jobs.job_prompts import get_job_prompt
from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor, VideoCompression
from app.modules.jobs.video_to_markdown.handler import DEFAULT_LANGUAGE
from app.modules.jobs.video_to_markdown.transcript import format_timestamp
from app.modules.jobs.youtube_to_markdown.job_options import LANGUAGE_KEY
from app.modules.prompt_presets.prompt_texts import (
    FullVideoRequestText,
    build_film_part_line,
    build_full_video_message,
)

VIDEO_COMPRESSION_FAILED_MESSAGE = "Video compression failed: {error}"
NO_VIDEO_PART_ERROR = "ffmpeg wrote no video part"
ANSWER_SEPARATOR = "\n\n"


class VideoCompressionError(Exception):
    pass


@dataclass(frozen=True)
class VideoCompressorConfig:
    part_sec: int
    max_side_px: int
    max_fps: int


@dataclass(frozen=True)
class FullVideoPassTools:
    repository: JobRepository
    ai_caller: AiCaller
    limits: AiLimits


@dataclass(frozen=True)
class FullVideoPass:
    job: Job
    prompt_pass: PromptPass
    parts: Sequence[MediaPart]
    character_prompts: str | None = None


@dataclass(frozen=True)
class FullVideoPartRequest:
    instructions: str
    part: MediaPart
    message: str


class VideoCompressor:
    def __init__(
        self, storage: JobStorage, media: FfmpegMediaProcessor, config: VideoCompressorConfig
    ):
        self._storage = storage
        self._media = media
        self._config = config

    def compress(
        self, job_id: str, video_path: Path, report_step: Callable[[JobStep], None]
    ) -> list[MediaPart]:
        report_step(JobStep.COMPRESSING_VIDEO)
        compressed_dir = self._storage.compressed_dir(job_id)
        self._storage.delete_compressed(job_id)
        compressed_dir.mkdir(parents=True)
        try:
            self._media.compress_video(
                VideoCompression(
                    video_path=video_path,
                    output_dir=compressed_dir,
                    part_sec=self._config.part_sec,
                    max_side_px=self._config.max_side_px,
                    max_fps=self._config.max_fps,
                )
            )
            parts = self.find_parts(job_id)
            if not parts:
                raise CommandError(NO_VIDEO_PART_ERROR)
        except CommandError as error:
            self._storage.delete_compressed(job_id)
            raise VideoCompressionError(
                VIDEO_COMPRESSION_FAILED_MESSAGE.format(error=error)
            ) from error
        return parts

    def find_parts(self, job_id: str) -> list[MediaPart]:
        part_paths = find_part_paths(self._storage.compressed_dir(job_id))
        durations_ms = [self._media.probe_duration_ms(path) for path in part_paths]
        return to_media_parts(part_paths, durations_ms)


class FullVideoPromptPasses:
    def __init__(self, tools: FullVideoPassTools):
        self._tools = tools

    def run(
        self, job: Job, parts: Sequence[MediaPart], report_step: Callable[[JobStep], None]
    ) -> None:
        report_step(CHARACTER_IMAGE_PASS.step)
        character_prompts = self._write(FullVideoPass(job, CHARACTER_IMAGE_PASS, parts))
        for prompt_pass in (CHARACTER_VOICE_PASS, SCENE_PASS):
            report_step(prompt_pass.step)
            self._write(FullVideoPass(job, prompt_pass, parts, character_prompts))

    def _write(self, full_video_pass: FullVideoPass) -> str:
        choice = self._tools.ai_caller.find_google_model(AiStepGroup.FILM_ANALYSIS)
        prompt_pass = full_video_pass.prompt_pass
        self._tools.repository.save_ai_used(full_video_pass.job.id, prompt_pass.step, choice)
        answers = self._ask_every_part(choice, full_video_pass)
        stored_answer = ANSWER_SEPARATOR.join(answers) if prompt_pass is SCENE_PASS else answers[-1]
        self._tools.repository.save_output(
            full_video_pass.job.id, prompt_pass.output_kind, stored_answer
        )
        return stored_answer

    def _ask_every_part(self, choice: AiModelChoice, full_video_pass: FullVideoPass) -> list[str]:
        job = full_video_pass.job
        prompt_pass = full_video_pass.prompt_pass
        instructions = get_job_prompt(job.options, prompt_pass.prompt_key)
        parts = full_video_pass.parts
        answers: list[str] = []
        for part, part_line in zip(parts, to_part_lines(parts), strict=True):
            earlier_answer = answers[-1] if answers and prompt_pass is not SCENE_PASS else None
            message = build_full_video_message(
                FullVideoRequestText(
                    language_name=to_language_name(job.options),
                    part_line=part_line,
                    character_prompts=full_video_pass.character_prompts,
                    earlier_answer=earlier_answer,
                )
            )
            answer = self._tools.ai_caller.ask_for_text(
                choice,
                to_full_video_ask(FullVideoPartRequest(instructions, part, message)),
                self._tools.limits,
            )
            answers.append(answer.strip())
        return answers


def to_full_video_ask(request: FullVideoPartRequest) -> AiAsk:
    return AiAsk(
        instructions=request.instructions,
        message=request.message,
        media=[
            AttachedMedia(
                label=to_part_label(VIDEO_MEDIA_WORD, request.part),
                path=request.part.path,
                mime_type=VIDEO_MIME_TYPE,
            )
        ],
    )


def to_language_name(options: Mapping[str, Any]) -> str | None:
    language = options.get(LANGUAGE_KEY, DEFAULT_LANGUAGE)
    if language == DEFAULT_LANGUAGE:
        return None
    return LANGUAGE_NAMES_BY_CODE.get(language, language)


def to_part_lines(parts: Sequence[MediaPart]) -> list[str | None]:
    if len(parts) == 1:
        return [None]
    return [
        build_film_part_line(
            format_timestamp(part.start_ms),
            format_timestamp(part.end_ms),
            str(part_number),
            str(len(parts)),
        )
        for part_number, part in enumerate(parts, start=1)
    ]


class FullVideoSteps:
    def __init__(self, compressor: VideoCompressor, prompt_passes: FullVideoPromptPasses):
        self._compressor = compressor
        self._prompt_passes = prompt_passes

    def run_from_video(
        self, job: Job, video_path: Path, report_step: Callable[[JobStep], None]
    ) -> None:
        parts = self._compressor.compress(job.id, video_path, report_step)
        self._prompt_passes.run(job, parts, report_step)

    def run_from_compressed(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        parts = self._compressor.find_parts(job.id)
        if not parts:
            raise NoCompressedVideoError(job.id)
        self._prompt_passes.run(job, parts, report_step)
