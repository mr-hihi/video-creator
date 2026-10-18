from dataclasses import dataclass

from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.handler import NoSpeechError
from app.modules.jobs.video_to_markdown.transcript import Transcript
from app.modules.jobs.youtube_to_markdown.captions import (
    AUTO_LANGUAGE,
    json3_to_transcript,
    select_caption_track,
)
from app.modules.jobs.youtube_to_markdown.job_options import (
    CAPTION_KIND_KEY,
    LANGUAGE_KEY,
    URL_KEY,
)
from app.modules.jobs.youtube_to_markdown.video_info import info_json_to_video_info
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader


@dataclass(frozen=True)
class FetchedTranscript:
    transcript: Transcript
    duration_ms: int


class YoutubeTranscriptFetcher:
    def __init__(self, downloader: YtDlpDownloader, repository: JobRepository, storage: JobStorage):
        self._downloader = downloader
        self._repository = repository
        self._storage = storage

    def fetch(self, job: Job) -> FetchedTranscript:
        video_url = job.options[URL_KEY]
        video = info_json_to_video_info(self._downloader.read_video_info(video_url))
        track = select_caption_track(video, job.options.get(LANGUAGE_KEY, AUTO_LANGUAGE))
        self._repository.merge_options(job.id, {CAPTION_KIND_KEY: track.kind.value})
        captions_json = self._downloader.download_captions(
            video_url, track, self._storage.work_dir(job.id)
        )
        transcript = json3_to_transcript(captions_json, track.language)
        if not transcript.segments:
            raise NoSpeechError()
        return FetchedTranscript(transcript=transcript, duration_ms=video.duration_ms)
