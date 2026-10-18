from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.storage import JobStorage, to_safe_stem
from app.modules.jobs.video_to_markdown.markdown import (
    MarkdownSource,
    build_markdown_with_moment_links,
)
from app.modules.jobs.video_to_markdown.moment_steps import (
    MomentFrameCapturer,
    MomentPickingSteps,
    MomentSource,
)
from app.modules.jobs.youtube_to_markdown.job_options import URL_KEY, VIDEO_ID_KEY
from app.modules.jobs.youtube_to_markdown.links import to_timestamp_url
from app.modules.jobs.youtube_to_markdown.transcript_fetcher import YoutubeTranscriptFetcher
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader


@dataclass(frozen=True)
class YoutubeToMarkdownTools:
    transcript_fetcher: YoutubeTranscriptFetcher
    downloader: YtDlpDownloader
    moment_steps: MomentPickingSteps
    frame_capturer: MomentFrameCapturer


class YoutubeToMarkdownHandler:
    def __init__(self, storage: JobStorage, tools: YoutubeToMarkdownTools, max_moments: int):
        self._storage = storage
        self._tools = tools
        self._max_moments = max_moments

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._storage.create_processing_dirs(job.id)
        video_id = job.options[VIDEO_ID_KEY]

        report_step(JobStep.FETCHING_TRANSCRIPT)
        fetched = self._tools.transcript_fetcher.fetch(job)

        picked = self._tools.moment_steps.pick(
            MomentSource(
                job,
                fetched.transcript.segments,
                fetched.duration_ms,
                lambda: self._download_video(job, report_step),
            ),
            self._max_moments,
            report_step,
        )
        outline = picked.outline

        report_step(JobStep.CAPTURING_FRAMES)
        captured_moments = self._tools.frame_capturer.capture(
            job.id, picked.video_path, outline.moments
        )

        report_step(JobStep.WRITING_MARKDOWN)
        markdown = build_markdown_with_moment_links(
            MarkdownSource(
                title=outline.title or to_safe_stem(job.source_filename),
                summary=outline.summary,
                source_label=job.options[URL_KEY],
                duration_ms=fetched.duration_ms,
                transcript=fetched.transcript,
                captured_moments=captured_moments,
            ),
            lambda at_ms: to_timestamp_url(video_id, at_ms),
        )
        self._storage.save_result(job.id, job.source_filename, markdown)

    def _download_video(self, job: Job, report_step: Callable[[JobStep], None]) -> Path:
        report_step(JobStep.DOWNLOADING_VIDEO)
        return self._tools.downloader.download_video(
            job.options[URL_KEY], self._storage.source_path(job.id, job.source_filename)
        )
