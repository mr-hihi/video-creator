from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from app.modules.ai_models.ai_calls import InputMode
from app.modules.jobs.film_analysis.audio_listener import AudioListener, AudioSource
from app.modules.jobs.film_analysis.audio_notes import AudioNotes, to_sound_title
from app.modules.jobs.film_analysis.frames import (
    FrameCandidates,
    FrameKind,
    MergedFrames,
    merge_film_frames,
)
from app.modules.jobs.film_analysis.job_options import FRAME_COUNTS_KEY, get_max_frames
from app.modules.jobs.film_analysis.notes_passes import CapturedFilmFrame
from app.modules.jobs.film_analysis.scene_detector import FfmpegSceneDetector
from app.modules.jobs.job_ai import get_job_input_mode
from app.modules.jobs.models import Job, JobOutputKind, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.video_to_markdown.moment_steps import (
    MomentFrameCapturer,
    MomentPickingSteps,
    MomentSource,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment, VideoOutline


@dataclass(frozen=True)
class FilmFrameTools:
    moment_steps: MomentPickingSteps
    scene_detector: FfmpegSceneDetector
    frame_capturer: MomentFrameCapturer
    audio_listener: AudioListener


@dataclass(frozen=True)
class PickedFilmMoments:
    outline: VideoOutline
    video_path: Path
    audio_notes: AudioNotes | None = None


@dataclass(frozen=True)
class FrameCaptureRequest:
    job: Job
    video_path: Path
    dialogue_moments: list[KeyMoment]
    duration_ms: int
    audio_notes: AudioNotes | None = None


class FilmFrameSteps:
    def __init__(self, repository: JobRepository, tools: FilmFrameTools):
        self._repository = repository
        self._tools = tools

    def pick_dialogue_moments(
        self, source: MomentSource, report_step: Callable[[JobStep], None]
    ) -> PickedFilmMoments:
        max_moments = get_max_frames(source.job.options) // 2
        if get_job_input_mode(source.job.options) is not InputMode.WHOLE_VIDEO:
            picked = self._tools.moment_steps.pick(source, max_moments, report_step)
            return PickedFilmMoments(outline=picked.outline, video_path=picked.video_path)
        video_path = source.get_video_path()
        audio_notes = self._tools.audio_listener.listen(
            AudioSource(source.job, video_path, source.segments, source.duration_ms), report_step
        )
        picked = self._tools.moment_steps.pick(
            replace(source, get_video_path=lambda: video_path), max_moments, report_step
        )
        return PickedFilmMoments(
            outline=picked.outline, video_path=picked.video_path, audio_notes=audio_notes
        )

    def capture_frames(
        self, request: FrameCaptureRequest, report_step: Callable[[JobStep], None]
    ) -> list[CapturedFilmFrame]:
        report_step(JobStep.DETECTING_SCENES)
        cut_times_ms = self._tools.scene_detector.detect_cut_times_ms(request.video_path)

        report_step(JobStep.CAPTURING_FRAMES)
        merged = merge_film_frames(
            FrameCandidates(
                dialogue_moments=request.dialogue_moments,
                cut_times_ms=cut_times_ms,
                duration_ms=request.duration_ms,
                sound_moments=to_sound_moments(request.audio_notes),
            ),
            get_max_frames(request.job.options),
        )
        self._repository.merge_options(
            request.job.id, {FRAME_COUNTS_KEY: to_frame_counts(merged, request.audio_notes)}
        )
        captured_moments = self._tools.frame_capturer.capture(
            request.job.id, request.video_path, [frame.moment for frame in merged.frames]
        )
        return [
            CapturedFilmFrame(captured_moment=captured_moment, kind=frame.kind)
            for captured_moment, frame in zip(captured_moments, merged.frames, strict=True)
        ]

    def save_video_notes(self, job: Job, video_notes: str) -> None:
        self._repository.save_output(job.id, JobOutputKind.VIDEO_NOTES, video_notes)


def to_sound_moments(audio_notes: AudioNotes | None) -> list[KeyMoment]:
    if audio_notes is None:
        return []
    return [
        KeyMoment(at_ms=sound.at_ms, title=to_sound_title(sound)) for sound in audio_notes.sounds
    ]


def to_frame_counts(merged: MergedFrames, audio_notes: AudioNotes | None) -> dict[str, int]:
    frame_counts = {FrameKind.DIALOGUE.value: merged.dialogue_count}
    if audio_notes is not None:
        frame_counts[FrameKind.SOUND.value] = merged.sound_count
    frame_counts[FrameKind.SCENE.value] = merged.scene_count
    return frame_counts
