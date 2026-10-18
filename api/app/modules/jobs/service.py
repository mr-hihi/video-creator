import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from app.modules.jobs.errors import (
    InvalidUploadError,
    InvalidYoutubeJobError,
    JobNotFoundError,
    NoZipDownloadError,
    ResultFileNotFoundError,
    ResultNotReadyError,
)
from app.modules.jobs.film_analysis.job_options import MAX_FRAMES_KEY, to_valid_max_frames
from app.modules.jobs.job_ai import FILM_ANALYSIS_AI_GROUPS, MARKDOWN_AI_GROUPS
from app.modules.jobs.job_intake import JobIntake
from app.modules.jobs.job_prompts import FILM_ANALYSIS_PROMPT_KEYS, VIDEO_TO_MARKDOWN_PROMPT_KEYS
from app.modules.jobs.models import (
    VIDEO_NOTES_JOB_TYPES,
    Job,
    JobOutputKind,
    JobStatus,
    JobType,
)
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage, to_safe_stem
from app.modules.jobs.youtube_to_markdown.job_options import (
    LANGUAGE_KEY,
    build_youtube_job_options,
)
from app.modules.jobs.youtube_to_markdown.video_checker import YoutubeVideoChecker
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo

SUPPORTED_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"})
LANGUAGE_PATTERN = re.compile(r"^(auto|[a-z]{2,3})$")
MAX_SOURCE_FILENAME_LENGTH = 255
YOUTUBE_SOURCE_EXTENSION = ".mp4"


@dataclass(frozen=True)
class VideoUpload:
    filename: str
    stream: BinaryIO
    language: str
    preset_id: str | None


@dataclass(frozen=True)
class YoutubeJobRequest:
    link: str
    language: str
    preset_id: str | None


@dataclass(frozen=True)
class JobDetail:
    job: Job
    markdown: str | None
    outputs: dict[JobOutputKind, str] | None


@dataclass(frozen=True)
class ResultArchive:
    path: Path
    download_name: str


class JobService:
    def __init__(self, repository: JobRepository, storage: JobStorage, intake: JobIntake):
        self._repository = repository
        self._storage = storage
        self._intake = intake

    def create_video_to_markdown_job(self, upload: VideoUpload) -> Job:
        validate_video_upload(upload)
        prompt_options = self._intake.resolve_prompt_options(
            upload.preset_id, VIDEO_TO_MARKDOWN_PROMPT_KEYS
        )
        ai_options = self._intake.resolve_ai_options(MARKDOWN_AI_GROUPS)
        job_id = str(uuid4())
        self._storage.save_source(job_id, upload.filename, upload.stream)
        return self._intake.enqueue(
            Job(
                id=job_id,
                type=JobType.VIDEO_TO_MARKDOWN,
                status=JobStatus.PENDING,
                source_filename=upload.filename[:MAX_SOURCE_FILENAME_LENGTH],
                options={LANGUAGE_KEY: upload.language, **prompt_options, **ai_options},
            )
        )

    def list_recent_jobs(self, limit: int, types: Collection[JobType]) -> list[Job]:
        return self._repository.find_recent(limit, types)

    def get_job(self, job_id: str) -> Job:
        job = self._repository.find_by_id(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def get_job_detail(self, job_id: str) -> JobDetail:
        job = self.get_job(job_id)
        if job.type in VIDEO_NOTES_JOB_TYPES:
            return JobDetail(job=job, markdown=None, outputs=self._repository.find_outputs(job.id))
        if job.status != JobStatus.DONE:
            return JobDetail(job=job, markdown=None, outputs=None)
        markdown_path = self._storage.markdown_path(job.id, job.source_filename)
        return JobDetail(job=job, markdown=markdown_path.read_text(encoding="utf-8"), outputs=None)

    def resolve_result_file(self, job_id: str, relative_path: str) -> Path:
        job = self._get_job_with_result_files(job_id)
        output_dir = self._storage.output_dir(job.id).resolve()
        candidate = (output_dir / relative_path).resolve()
        if not candidate.is_relative_to(output_dir) or not candidate.is_file():
            raise ResultFileNotFoundError(relative_path)
        return candidate

    def get_result_archive(self, job_id: str) -> ResultArchive:
        job = self.get_job(job_id)
        if job.type in VIDEO_NOTES_JOB_TYPES:
            raise NoZipDownloadError(job_id)
        if job.status != JobStatus.DONE:
            raise ResultNotReadyError(job_id)
        return ResultArchive(
            path=self._storage.archive_path(job.id),
            download_name=f"{to_safe_stem(job.source_filename)}.zip",
        )

    def _get_job_with_result_files(self, job_id: str) -> Job:
        job = self.get_job(job_id)
        if not self._has_result_files(job):
            raise ResultNotReadyError(job_id)
        return job

    def _has_result_files(self, job: Job) -> bool:
        if job.type in VIDEO_NOTES_JOB_TYPES:
            return JobOutputKind.VIDEO_NOTES in self._repository.find_outputs(job.id)
        return job.status == JobStatus.DONE


class YoutubeJobService:
    def __init__(self, video_checker: YoutubeVideoChecker, intake: JobIntake):
        self._video_checker = video_checker
        self._intake = intake

    def create_youtube_to_markdown_job(self, request: YoutubeJobRequest) -> Job:
        validate_youtube_language(request.language)
        prompt_options = self._intake.resolve_prompt_options(
            request.preset_id, VIDEO_TO_MARKDOWN_PROMPT_KEYS
        )
        ai_options = self._intake.resolve_ai_options(MARKDOWN_AI_GROUPS)
        video = self._video_checker.fetch_convertible_video(request.link)
        return self._intake.enqueue(
            build_youtube_job(
                JobType.YOUTUBE_TO_MARKDOWN,
                video,
                {
                    **build_youtube_job_options(video.video_id, request.language),
                    **prompt_options,
                    **ai_options,
                },
            )
        )

    def create_youtube_film_analysis_job(
        self, request: YoutubeJobRequest, max_frames: int | None
    ) -> Job:
        validate_youtube_language(request.language)
        valid_max_frames = to_valid_max_frames(max_frames)
        prompt_options = self._intake.resolve_prompt_options(
            request.preset_id, FILM_ANALYSIS_PROMPT_KEYS
        )
        ai_options = self._intake.resolve_ai_options(FILM_ANALYSIS_AI_GROUPS)
        video = self._video_checker.fetch_convertible_video(request.link)
        return self._intake.enqueue(
            build_youtube_job(
                JobType.YOUTUBE_FILM_ANALYSIS,
                video,
                {
                    **build_youtube_job_options(video.video_id, request.language),
                    MAX_FRAMES_KEY: valid_max_frames,
                    **prompt_options,
                    **ai_options,
                },
            )
        )


def to_youtube_source_filename(video: VideoInfo) -> str:
    suffix = f" [{video.video_id}]{YOUTUBE_SOURCE_EXTENSION}"
    return f"{video.title[: MAX_SOURCE_FILENAME_LENGTH - len(suffix)]}{suffix}"


def validate_video_upload(upload: VideoUpload) -> None:
    extension = Path(upload.filename).suffix.lower()
    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_VIDEO_EXTENSIONS))
        raise InvalidUploadError(f"Unsupported file type '{extension}'. Use one of: {supported}")
    if not LANGUAGE_PATTERN.match(upload.language):
        raise InvalidUploadError(f"Invalid language '{upload.language}'")


def validate_youtube_language(language: str) -> None:
    if not LANGUAGE_PATTERN.match(language):
        raise InvalidYoutubeJobError(f"Invalid language '{language}'")


def build_youtube_job(job_type: JobType, video: VideoInfo, options: dict[str, Any]) -> Job:
    return Job(
        id=str(uuid4()),
        type=job_type,
        status=JobStatus.PENDING,
        source_filename=to_youtube_source_filename(video),
        options=options,
    )
