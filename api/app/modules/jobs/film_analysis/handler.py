from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.modules.ai_models.ai_calls import InputMode
from app.modules.jobs.errors import NoVideoNotesError
from app.modules.jobs.film_analysis.audio_notes import AudioNotes, to_speaker_voices
from app.modules.jobs.film_analysis.frame_steps import (
    FilmFrameSteps,
    FrameCaptureRequest,
    PickedFilmMoments,
)
from app.modules.jobs.film_analysis.full_video import FullVideoSteps
from app.modules.jobs.film_analysis.notes_passes import (
    CapturedFilmFrame,
    NotesPasses,
    WrittenNotes,
)
from app.modules.jobs.film_analysis.prompt_passes import FilmPromptPasses
from app.modules.jobs.job_ai import get_job_input_mode
from app.modules.jobs.models import PROMPT_OUTPUT_KINDS, Job, JobOutputKind, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage, to_safe_stem
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.handler import (
    AUDIO_FILENAME,
    DEFAULT_LANGUAGE,
    NoSpeechError,
)
from app.modules.jobs.video_to_markdown.markdown import (
    CapturedMoment,
    MarkdownSource,
    SpeakerVoices,
    build_markdown,
    build_markdown_with_moment_links,
)
from app.modules.jobs.video_to_markdown.moment_steps import MomentSource
from app.modules.jobs.video_to_markdown.whisper_transcriber import WhisperCppTranscriber
from app.modules.jobs.youtube_to_markdown.job_options import LANGUAGE_KEY, URL_KEY, VIDEO_ID_KEY
from app.modules.jobs.youtube_to_markdown.links import to_timestamp_url
from app.modules.jobs.youtube_to_markdown.transcript_fetcher import YoutubeTranscriptFetcher
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader

ALL_OUTPUT_KINDS = tuple(JobOutputKind)
INPUT_MODES_WITH_AUDIO = (InputMode.WHOLE_VIDEO, InputMode.FULL_VIDEO)


@dataclass(frozen=True)
class FilmAnalysisTools:
    media: FfmpegMediaProcessor
    transcriber: WhisperCppTranscriber
    frame_steps: FilmFrameSteps
    prompt_passes: NotesPasses
    full_video: FullVideoSteps


@dataclass(frozen=True)
class YoutubeFilmAnalysisTools:
    transcript_fetcher: YoutubeTranscriptFetcher
    downloader: YtDlpDownloader
    frame_steps: FilmFrameSteps
    prompt_passes: NotesPasses
    full_video: FullVideoSteps


class FilmAnalysisHandler:
    def __init__(self, storage: JobStorage, repository: JobRepository, tools: FilmAnalysisTools):
        self._storage = storage
        self._repository = repository
        self._tools = tools

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._repository.delete_outputs(job.id, ALL_OUTPUT_KINDS)
        source_path = self._storage.source_path(job.id, job.source_filename)
        if get_job_input_mode(job.options) is InputMode.FULL_VIDEO:
            self._tools.full_video.run_from_video(job, source_path, report_step)
            return
        self._storage.create_processing_dirs(job.id)

        report_step(JobStep.EXTRACTING_AUDIO)
        duration_ms = self._tools.media.probe_duration_ms(source_path)
        audio_path = self._tools.media.extract_audio(
            source_path, self._storage.work_dir(job.id) / AUDIO_FILENAME
        )

        report_step(JobStep.TRANSCRIBING)
        transcript = self._tools.transcriber.transcribe(
            audio_path, job.options.get(LANGUAGE_KEY, DEFAULT_LANGUAGE)
        )
        if not transcript.segments:
            raise NoSpeechError()

        frame_steps = self._tools.frame_steps
        picked = frame_steps.pick_dialogue_moments(
            MomentSource(job, transcript.segments, duration_ms, lambda: source_path), report_step
        )
        captured_frames = frame_steps.capture_frames(
            to_frame_capture_request(job, picked, duration_ms), report_step
        )

        report_step(JobStep.WRITING_MARKDOWN)
        video_notes = build_markdown(
            MarkdownSource(
                title=picked.outline.title or to_safe_stem(job.source_filename),
                summary=picked.outline.summary,
                source_label=job.source_filename,
                duration_ms=duration_ms,
                transcript=transcript,
                captured_moments=to_captured_moments(captured_frames),
                voices=to_markdown_voices(picked.audio_notes),
            )
        )
        frame_steps.save_video_notes(job, video_notes)
        self._tools.prompt_passes.run(job, WrittenNotes(video_notes, captured_frames), report_step)


class YoutubeFilmAnalysisHandler:
    def __init__(
        self, storage: JobStorage, repository: JobRepository, tools: YoutubeFilmAnalysisTools
    ):
        self._storage = storage
        self._repository = repository
        self._tools = tools

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._repository.delete_outputs(job.id, ALL_OUTPUT_KINDS)
        if get_job_input_mode(job.options) is InputMode.FULL_VIDEO:
            video_path = self._download_video(job, report_step)
            self._tools.full_video.run_from_video(job, video_path, report_step)
            return
        self._storage.create_processing_dirs(job.id)
        video_id = job.options[VIDEO_ID_KEY]

        report_step(JobStep.FETCHING_TRANSCRIPT)
        fetched = self._tools.transcript_fetcher.fetch(job)

        frame_steps = self._tools.frame_steps
        picked = frame_steps.pick_dialogue_moments(
            MomentSource(
                job,
                fetched.transcript.segments,
                fetched.duration_ms,
                lambda: self._download_video(job, report_step),
            ),
            report_step,
        )
        captured_frames = frame_steps.capture_frames(
            to_frame_capture_request(job, picked, fetched.duration_ms), report_step
        )

        report_step(JobStep.WRITING_MARKDOWN)
        video_notes = build_markdown_with_moment_links(
            MarkdownSource(
                title=picked.outline.title or to_safe_stem(job.source_filename),
                summary=picked.outline.summary,
                source_label=job.options[URL_KEY],
                duration_ms=fetched.duration_ms,
                transcript=fetched.transcript,
                captured_moments=to_captured_moments(captured_frames),
                voices=to_markdown_voices(picked.audio_notes),
            ),
            lambda at_ms: to_timestamp_url(video_id, at_ms),
        )
        frame_steps.save_video_notes(job, video_notes)
        self._tools.prompt_passes.run(job, WrittenNotes(video_notes, captured_frames), report_step)

    def _download_video(self, job: Job, report_step: Callable[[JobStep], None]) -> Path:
        report_step(JobStep.DOWNLOADING_VIDEO)
        downloader = self._tools.downloader
        download = (
            downloader.download_video_with_audio
            if get_job_input_mode(job.options) in INPUT_MODES_WITH_AUDIO
            else downloader.download_video
        )
        return download(
            job.options[URL_KEY], self._storage.source_path(job.id, job.source_filename)
        )


class FilmAnalysisRerunHandler:
    def __init__(
        self,
        repository: JobRepository,
        prompt_passes: FilmPromptPasses,
        full_video: FullVideoSteps,
    ):
        self._repository = repository
        self._prompt_passes = prompt_passes
        self._full_video = full_video

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._repository.delete_outputs(job.id, PROMPT_OUTPUT_KINDS)
        if get_job_input_mode(job.options) is InputMode.FULL_VIDEO:
            self._full_video.run_from_compressed(job, report_step)
            return
        video_notes = self._repository.find_outputs(job.id).get(JobOutputKind.VIDEO_NOTES)
        if video_notes is None:
            raise NoVideoNotesError(job.id)
        self._prompt_passes.run(job, WrittenNotes(video_notes, ()), report_step)


def to_frame_capture_request(
    job: Job, picked: PickedFilmMoments, duration_ms: int
) -> FrameCaptureRequest:
    return FrameCaptureRequest(
        job=job,
        video_path=picked.video_path,
        dialogue_moments=picked.outline.moments,
        duration_ms=duration_ms,
        audio_notes=picked.audio_notes,
    )


def to_captured_moments(captured_frames: list[CapturedFilmFrame]) -> list[CapturedMoment]:
    return [captured_frame.captured_moment for captured_frame in captured_frames]


def to_markdown_voices(audio_notes: AudioNotes | None) -> SpeakerVoices:
    if audio_notes is None:
        return SpeakerVoices()
    return to_speaker_voices(audio_notes)
