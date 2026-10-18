from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.modules.jobs.film_analysis.frames import FrameCandidates, merge_dialogue_and_scene_frames
from app.modules.jobs.film_analysis.job_options import FRAME_COUNTS_KEY, get_max_frames
from app.modules.jobs.film_analysis.scene_detector import FfmpegSceneDetector
from app.modules.jobs.models import Job, JobOutputKind, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.video_to_markdown.markdown import CapturedMoment
from app.modules.jobs.video_to_markdown.moment_steps import (
    MomentFrameCapturer,
    MomentPickingSteps,
    MomentSource,
    PickedMoments,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment


@dataclass(frozen=True)
class FilmFrameTools:
    moment_steps: MomentPickingSteps
    scene_detector: FfmpegSceneDetector
    frame_capturer: MomentFrameCapturer


@dataclass(frozen=True)
class FrameCaptureRequest:
    job: Job
    video_path: Path
    dialogue_moments: list[KeyMoment]
    duration_ms: int


class FilmFrameSteps:
    def __init__(self, repository: JobRepository, tools: FilmFrameTools):
        self._repository = repository
        self._tools = tools

    def pick_dialogue_moments(
        self, source: MomentSource, report_step: Callable[[JobStep], None]
    ) -> PickedMoments:
        return self._tools.moment_steps.pick(
            source, get_max_frames(source.job.options) // 2, report_step
        )

    def capture_frames(
        self, request: FrameCaptureRequest, report_step: Callable[[JobStep], None]
    ) -> list[CapturedMoment]:
        report_step(JobStep.DETECTING_SCENES)
        cut_times_ms = self._tools.scene_detector.detect_cut_times_ms(request.video_path)

        report_step(JobStep.CAPTURING_FRAMES)
        merged = merge_dialogue_and_scene_frames(
            FrameCandidates(
                dialogue_moments=request.dialogue_moments,
                cut_times_ms=cut_times_ms,
                duration_ms=request.duration_ms,
            ),
            get_max_frames(request.job.options),
        )
        self._repository.merge_options(
            request.job.id,
            {FRAME_COUNTS_KEY: {"dialogue": merged.dialogue_count, "scene": merged.scene_count}},
        )
        return self._tools.frame_capturer.capture(
            request.job.id, request.video_path, merged.moments
        )

    def save_video_notes(self, job: Job, video_notes: str) -> None:
        self._repository.save_output(job.id, JobOutputKind.VIDEO_NOTES, video_notes)
