from collections.abc import Callable
from dataclasses import dataclass

from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.storage import JobStorage, to_safe_stem
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.markdown import MarkdownSource, build_markdown
from app.modules.jobs.video_to_markdown.moment_steps import (
    MomentFrameCapturer,
    MomentPickingSteps,
    MomentSource,
)
from app.modules.jobs.video_to_markdown.whisper_transcriber import WhisperCppTranscriber

AUDIO_FILENAME = "audio.wav"
DEFAULT_LANGUAGE = "auto"


class NoSpeechError(Exception):
    def __init__(self):
        super().__init__("No speech was detected in the video")


@dataclass(frozen=True)
class VideoToMarkdownTools:
    media: FfmpegMediaProcessor
    transcriber: WhisperCppTranscriber
    moment_steps: MomentPickingSteps


class VideoToMarkdownHandler:
    def __init__(self, storage: JobStorage, tools: VideoToMarkdownTools, max_moments: int):
        self._storage = storage
        self._tools = tools
        self._max_moments = max_moments
        self._frame_capturer = MomentFrameCapturer(storage, tools.media)

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._storage.create_processing_dirs(job.id)
        source_path = self._storage.source_path(job.id, job.source_filename)

        report_step(JobStep.EXTRACTING_AUDIO)
        duration_ms = self._tools.media.probe_duration_ms(source_path)
        audio_path = self._tools.media.extract_audio(
            source_path, self._storage.work_dir(job.id) / AUDIO_FILENAME
        )

        report_step(JobStep.TRANSCRIBING)
        transcript = self._tools.transcriber.transcribe(
            audio_path, job.options.get("language", DEFAULT_LANGUAGE)
        )
        if not transcript.segments:
            raise NoSpeechError()

        outline = self._tools.moment_steps.pick(
            MomentSource(job, transcript.segments, duration_ms, lambda: source_path),
            self._max_moments,
            report_step,
        ).outline

        report_step(JobStep.CAPTURING_FRAMES)
        captured_moments = self._frame_capturer.capture(job.id, source_path, outline.moments)

        report_step(JobStep.WRITING_MARKDOWN)
        markdown = build_markdown(
            MarkdownSource(
                title=outline.title or to_safe_stem(job.source_filename),
                summary=outline.summary,
                source_label=job.source_filename,
                duration_ms=duration_ms,
                transcript=transcript,
                captured_moments=captured_moments,
            )
        )
        self._storage.save_result(job.id, job.source_filename, markdown)
