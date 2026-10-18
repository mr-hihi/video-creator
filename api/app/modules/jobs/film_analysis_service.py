from uuid import uuid4

from app.modules.jobs.errors import (
    JobNotDeletableError,
    JobNotFoundError,
    JobStillRunningError,
    NotFilmAnalysisJobError,
    NoVideoNotesError,
)
from app.modules.jobs.film_analysis.job_options import (
    MAX_FRAMES_KEY,
    RERUN_OF_JOB_ID_KEY,
    copy_reused_source_options,
    to_valid_max_frames,
)
from app.modules.jobs.job_ai import FILM_ANALYSIS_AI_GROUPS, RERUN_AI_GROUPS
from app.modules.jobs.job_intake import JobIntake
from app.modules.jobs.job_prompts import FILM_ANALYSIS_PROMPT_KEYS, FILM_PROMPT_PASS_KEYS
from app.modules.jobs.models import (
    FILM_ANALYSIS_JOB_TYPES,
    FINISHED_JOB_STATUSES,
    Job,
    JobOutput,
    JobOutputKind,
    JobStatus,
    JobType,
)
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import MAX_SOURCE_FILENAME_LENGTH, VideoUpload, validate_video_upload
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.youtube_to_markdown.job_options import LANGUAGE_KEY


class FilmAnalysisJobService:
    def __init__(self, repository: JobRepository, storage: JobStorage, intake: JobIntake):
        self._repository = repository
        self._storage = storage
        self._intake = intake

    def create_film_analysis_job(self, upload: VideoUpload, max_frames: int | None) -> Job:
        validate_video_upload(upload)
        valid_max_frames = to_valid_max_frames(max_frames)
        prompt_options = self._intake.resolve_prompt_options(
            upload.preset_id, FILM_ANALYSIS_PROMPT_KEYS
        )
        ai_options = self._intake.resolve_ai_options(FILM_ANALYSIS_AI_GROUPS)
        job_id = str(uuid4())
        self._storage.save_source(job_id, upload.filename, upload.stream)
        return self._intake.enqueue(
            Job(
                id=job_id,
                type=JobType.FILM_ANALYSIS,
                status=JobStatus.PENDING,
                source_filename=upload.filename[:MAX_SOURCE_FILENAME_LENGTH],
                options={
                    LANGUAGE_KEY: upload.language,
                    MAX_FRAMES_KEY: valid_max_frames,
                    **prompt_options,
                    **ai_options,
                },
            )
        )

    def create_rerun_job(self, source_job_id: str, preset_id: str | None) -> Job:
        source_job = self._get_film_analysis_job(source_job_id)
        video_notes = self._get_reusable_video_notes(source_job)
        prompt_options = self._intake.resolve_prompt_options(preset_id, FILM_PROMPT_PASS_KEYS)
        self._intake.ensure_ai_set_up(RERUN_AI_GROUPS)
        job_id = str(uuid4())
        self._storage.copy_images(source_job.id, job_id)
        return self._intake.enqueue(
            Job(
                id=job_id,
                type=JobType.FILM_ANALYSIS_RERUN,
                status=JobStatus.PENDING,
                source_filename=source_job.source_filename,
                options={
                    **copy_reused_source_options(source_job.options),
                    RERUN_OF_JOB_ID_KEY: source_job.id,
                    **prompt_options,
                },
            ),
            [JobOutput(job_id=job_id, kind=JobOutputKind.VIDEO_NOTES, content=video_notes)],
        )

    def delete_film_analysis_job(self, job_id: str) -> None:
        job = self._get_job(job_id)
        if job.type not in FILM_ANALYSIS_JOB_TYPES:
            raise JobNotDeletableError()
        if job.status not in FINISHED_JOB_STATUSES:
            raise JobStillRunningError(job_id)
        self._repository.delete(job_id)
        self._storage.delete_job_files(job_id)

    def _get_job(self, job_id: str) -> Job:
        job = self._repository.find_by_id(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def _get_film_analysis_job(self, job_id: str) -> Job:
        job = self._get_job(job_id)
        if job.type not in FILM_ANALYSIS_JOB_TYPES:
            raise NotFilmAnalysisJobError(job_id)
        return job

    def _get_reusable_video_notes(self, source_job: Job) -> str:
        video_notes = self._repository.find_outputs(source_job.id).get(JobOutputKind.VIDEO_NOTES)
        if source_job.status not in FINISHED_JOB_STATUSES or video_notes is None:
            raise NoVideoNotesError(source_job.id)
        return video_notes
