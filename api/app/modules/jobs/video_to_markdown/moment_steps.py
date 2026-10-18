from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import (
    AiAsk,
    AiLimits,
    AiModelChoice,
    AiStepGroup,
    AttachedImage,
    InputMode,
)
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.jobs.job_ai import get_job_input_mode
from app.modules.jobs.job_prompts import get_job_prompt
from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import IMAGES_DIR_NAME, JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.frame_sampler import FrameSampler
from app.modules.jobs.video_to_markdown.markdown import CapturedMoment
from app.modules.jobs.video_to_markdown.moment_windows import (
    MomentWindow,
    SampleFrame,
    WindowPlan,
    split_into_windows,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment, VideoOutline, normalize_moments
from app.modules.jobs.video_to_markdown.outline_reply import OUTLINE_SCHEMA, reply_to_outline
from app.modules.jobs.video_to_markdown.transcript import (
    TranscriptSegment,
    format_timestamp,
    to_clock_time,
)
from app.modules.prompt_presets.prompt_texts import (
    PromptKey,
    WindowMomentRequestText,
    build_moment_request_message,
    build_window_moment_message,
)
from app.modules.providers.provider_catalog import ProviderId


@dataclass(frozen=True)
class OutlineRequest:
    job_id: str
    segments: list[TranscriptSegment]
    duration_ms: int
    max_moments: int
    instructions: str


@dataclass(frozen=True)
class MomentPickerConfig:
    limits: AiLimits
    max_images_by_provider: Mapping[ProviderId, int]


@dataclass(frozen=True)
class MomentSource:
    job: Job
    segments: list[TranscriptSegment]
    duration_ms: int
    get_video_path: Callable[[], Path]


@dataclass(frozen=True)
class PickedMoments:
    outline: VideoOutline
    video_path: Path


class KeyMomentPicker:
    def __init__(self, ai_caller: AiCaller, repository: JobRepository, config: MomentPickerConfig):
        self._ai_caller = ai_caller
        self._repository = repository
        self._config = config

    def pick_from_transcript(self, request: OutlineRequest) -> VideoOutline:
        choice = self._start_picking(request.job_id)
        outline = self._pick_outline(choice, to_transcript_ask(request))
        return to_normalized_outline(outline, request)

    def pick_from_samples(
        self, request: OutlineRequest, samples: Sequence[SampleFrame]
    ) -> VideoOutline:
        choice = self._start_picking(request.job_id)
        windows = split_into_windows(
            WindowPlan(
                segments=request.segments,
                samples=samples,
                duration_ms=request.duration_ms,
                max_moments=request.max_moments,
                max_images=self._config.max_images_by_provider[choice.provider],
            )
        )
        outlines = [
            self._pick_outline(choice, to_window_ask(request.instructions, window))
            for window in windows
        ]
        merged = VideoOutline(
            title=outlines[0].title,
            summary=outlines[0].summary,
            moments=[moment for outline in outlines for moment in outline.moments],
        )
        return to_normalized_outline(merged, request)

    def _start_picking(self, job_id: str) -> AiModelChoice:
        choice = self._ai_caller.find_model(AiStepGroup.MOMENTS)
        self._repository.save_ai_used(job_id, JobStep.PICKING_MOMENTS, choice)
        return choice

    def _pick_outline(self, choice: AiModelChoice, ask: AiAsk) -> VideoOutline:
        reply = self._ai_caller.ask_for_json(choice, ask, self._config.limits)
        return reply_to_outline(reply, to_ai_name(choice.provider))


class MomentPickingSteps:
    def __init__(self, key_moment_picker: KeyMomentPicker, sampler: FrameSampler):
        self._key_moment_picker = key_moment_picker
        self._sampler = sampler

    def pick(
        self, source: MomentSource, max_moments: int, report_step: Callable[[JobStep], None]
    ) -> PickedMoments:
        request = to_outline_request(source, max_moments)
        if get_job_input_mode(source.job.options) is InputMode.SUBTITLES:
            report_step(JobStep.PICKING_MOMENTS)
            outline = self._key_moment_picker.pick_from_transcript(request)
            return PickedMoments(outline=outline, video_path=source.get_video_path())
        video_path = source.get_video_path()
        try:
            report_step(JobStep.SAMPLING_FRAMES)
            samples = self._sampler.sample(source.job.id, video_path, source.duration_ms)
            report_step(JobStep.PICKING_MOMENTS)
            outline = self._key_moment_picker.pick_from_samples(request, samples)
        finally:
            self._sampler.delete_samples(source.job.id)
        return PickedMoments(outline=outline, video_path=video_path)


class MomentFrameCapturer:
    def __init__(self, storage: JobStorage, media: FfmpegMediaProcessor):
        self._storage = storage
        self._media = media

    def capture(
        self, job_id: str, video_path: Path, moments: list[KeyMoment]
    ) -> list[CapturedMoment]:
        images_dir = self._storage.images_dir(job_id)
        captured_moments = []
        for index, moment in enumerate(moments, start=1):
            image_name = to_frame_filename(index, moment.at_ms)
            self._media.capture_frame(video_path, moment.at_ms, images_dir / image_name)
            captured_moments.append(
                CapturedMoment(moment=moment, image_relative_path=f"{IMAGES_DIR_NAME}/{image_name}")
            )
        return captured_moments


def to_outline_request(source: MomentSource, max_moments: int) -> OutlineRequest:
    return OutlineRequest(
        job_id=source.job.id,
        segments=source.segments,
        duration_ms=source.duration_ms,
        max_moments=max_moments,
        instructions=get_job_prompt(source.job.options, PromptKey.VIDEO_TO_MARKDOWN),
    )


def to_transcript_ask(request: OutlineRequest) -> AiAsk:
    return AiAsk(
        instructions=request.instructions,
        message=build_moment_request_message(
            str(request.max_moments), to_transcript_lines(request.segments)
        ),
        reply_schema=OUTLINE_SCHEMA,
    )


def to_transcript_lines(segments: Sequence[TranscriptSegment]) -> str:
    return "\n".join(f"[{segment.start_ms}ms] {segment.text.strip()}" for segment in segments)


def to_window_ask(instructions: str, window: MomentWindow) -> AiAsk:
    return AiAsk(
        instructions=instructions,
        message=build_window_moment_message(
            WindowMomentRequestText(
                start=format_timestamp(window.start_ms),
                end=format_timestamp(window.end_ms),
                max_moments=str(window.max_moments),
                transcript_lines=to_transcript_lines(window.segments),
            )
        ),
        images=[
            AttachedImage(label=f"[{sample.at_ms}ms]", path=sample.path)
            for sample in window.samples
        ],
        reply_schema=OUTLINE_SCHEMA,
    )


def to_normalized_outline(outline: VideoOutline, request: OutlineRequest) -> VideoOutline:
    return VideoOutline(
        title=outline.title,
        summary=outline.summary,
        moments=normalize_moments(outline.moments, request.duration_ms, request.max_moments),
    )


def to_frame_filename(index: int, at_ms: int) -> str:
    clock = to_clock_time(at_ms)
    hours_part = f"{clock.hours}h" if clock.hours else ""
    return f"moment-{index:02d}-{hours_part}{clock.minutes:02d}m{clock.seconds:02d}s.jpg"
