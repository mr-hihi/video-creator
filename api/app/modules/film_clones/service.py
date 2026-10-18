from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.ai_models.ai_calls import AiStepGroup
from app.modules.film_clones.clone_access import CloneAccess
from app.modules.film_clones.clone_activity import AiActivity, AiActivityTracker
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.errors import CloneConflictError, InvalidCloneRequestError
from app.modules.film_clones.localization_rules import (
    LocalizationChoices,
    to_choice_values,
    validate_localization_choices,
)
from app.modules.film_clones.models import (
    CloneAsset,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.jobs.film_analysis.job_options import DEFAULT_MAX_FRAMES, MAX_FRAMES_KEY
from app.modules.jobs.job_intake import JobIntake
from app.modules.jobs.job_prompts import PRESET_OPTION_KEY, PROMPTS_OPTION_KEY
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import (
    MAX_SOURCE_FILENAME_LENGTH,
    VideoUpload,
    YoutubeJobRequest,
    build_youtube_job,
    validate_video_upload,
    validate_youtube_language,
)
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.youtube_to_markdown.job_options import (
    LANGUAGE_KEY,
    build_youtube_job_options,
)
from app.modules.jobs.youtube_to_markdown.video_checker import YoutubeVideoChecker
from app.modules.media_generation.models import GenerationRequest
from app.modules.media_generation.service import GenerationService
from app.modules.prompt_presets.prompt_texts import PromptKey

CLONE_MAX_FRAMES_LIMITS = (10, 1000)
CLONE_ID_KEY = "cloneId"
JOB_PROMPT_KEYS = (PromptKey.VIDEO_TO_MARKDOWN, PromptKey.CLONE_ASSETS, PromptKey.CLONE_SHOTS)
CLONE_PROMPT_KEYS = (PromptKey.CLONE_LOCALIZATION, PromptKey.CLONE_SCRIPT)
FILM_CLONE_AI_GROUPS = (AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE)
STEP_BY_STEP_RUN_VALUES = {
    "should_run_automatically": False,
    "change_appearance": False,
    "change_costume": False,
    "change_setting": False,
}


@dataclass(frozen=True)
class CloneOptions:
    max_frames: int | None
    should_run_automatically: bool
    choices: LocalizationChoices


@dataclass(frozen=True)
class FilmCloneServiceTools:
    repository: FilmCloneRepository
    job_repository: JobRepository
    job_storage: JobStorage
    files: CloneFiles
    intake: JobIntake
    video_checker: YoutubeVideoChecker
    generation_service: GenerationService
    notify_worker: Callable[[], None]
    ai_activity: AiActivityTracker


@dataclass(frozen=True)
class CloneSummary:
    clone: FilmClone
    job: Job | None
    has_open_requests: bool


@dataclass(frozen=True)
class CloneDetail:
    summary: CloneSummary
    video_notes: str | None
    assets: list[CloneAsset]
    shots: list[CloneShot]
    scenes: list[CloneScene]
    open_requests: list[GenerationRequest]
    ai_activity: AiActivity | None


class FilmCloneService:
    def __init__(self, tools: FilmCloneServiceTools, access: CloneAccess):
        self._tools = tools
        self._access = access

    def create_from_upload(self, upload: VideoUpload, options: CloneOptions) -> CloneSummary:
        validate_video_upload(upload)
        valid_max_frames = to_valid_clone_max_frames(options.max_frames)
        validate_automatic_run(options)
        prompt_options = self._tools.intake.resolve_prompt_options(
            upload.preset_id, (*JOB_PROMPT_KEYS, *CLONE_PROMPT_KEYS)
        )
        ai_options = self._tools.intake.resolve_film_clone_ai_options(FILM_CLONE_AI_GROUPS)
        job_id = str(uuid4())
        self._tools.job_storage.save_source(job_id, upload.filename, upload.stream)
        job = Job(
            id=job_id,
            type=JobType.FILM_CLONE,
            status=JobStatus.PENDING,
            source_filename=upload.filename[:MAX_SOURCE_FILENAME_LENGTH],
            options={
                LANGUAGE_KEY: upload.language,
                MAX_FRAMES_KEY: valid_max_frames,
                **ai_options,
            },
        )
        return self._add_with_job(job, prompt_options, to_automatic_run_values(options))

    def create_from_youtube(
        self, request: YoutubeJobRequest, options: CloneOptions
    ) -> CloneSummary:
        validate_youtube_language(request.language)
        valid_max_frames = to_valid_clone_max_frames(options.max_frames)
        validate_automatic_run(options)
        prompt_options = self._tools.intake.resolve_prompt_options(
            request.preset_id, (*JOB_PROMPT_KEYS, *CLONE_PROMPT_KEYS)
        )
        ai_options = self._tools.intake.resolve_film_clone_ai_options(FILM_CLONE_AI_GROUPS)
        video = self._tools.video_checker.fetch_convertible_video(request.link)
        job = build_youtube_job(
            JobType.YOUTUBE_FILM_CLONE,
            video,
            {
                **build_youtube_job_options(video.video_id, request.language),
                MAX_FRAMES_KEY: valid_max_frames,
                **ai_options,
            },
        )
        return self._add_with_job(job, prompt_options, to_automatic_run_values(options))

    def list_recent(self, limit: int) -> list[CloneSummary]:
        clones = self._tools.repository.find_recent(limit)
        jobs_by_id = self._tools.repository.find_jobs([clone.job_id for clone in clones])
        busy_clone_ids = self._tools.generation_service.find_clone_ids_with_open_requests(
            [clone.id for clone in clones]
        )
        return [
            CloneSummary(clone, jobs_by_id.get(clone.job_id), clone.id in busy_clone_ids)
            for clone in clones
        ]

    def get_detail(self, clone_id: str) -> CloneDetail:
        clone = self._access.get_clone(clone_id)
        open_requests = self._access.find_open_requests(clone_id)
        return CloneDetail(
            summary=CloneSummary(
                clone, self._tools.job_repository.find_by_id(clone.job_id), bool(open_requests)
            ),
            video_notes=self._tools.job_repository.find_outputs(clone.job_id).get(
                JobOutputKind.VIDEO_NOTES
            ),
            assets=self._tools.repository.find_assets(clone_id),
            shots=self._tools.repository.find_shots(clone_id),
            scenes=self._tools.repository.find_scenes(clone_id),
            open_requests=open_requests,
            ai_activity=self._tools.ai_activity.get(clone_id),
        )

    def get_summary(self, clone_id: str) -> CloneSummary:
        clone = self._access.get_clone(clone_id)
        return CloneSummary(
            clone,
            self._tools.job_repository.find_by_id(clone.job_id),
            bool(self._access.find_open_requests(clone_id)),
        )

    def delete(self, clone_id: str) -> None:
        clone = self._access.get_clone(clone_id)
        if clone.status is CloneStatus.RUNNING or self._access.find_open_requests(clone_id):
            raise CloneConflictError(f"Film clone {clone_id} is still running")
        self._tools.generation_service.delete_for_clone(clone_id)
        self._tools.repository.delete_with_job(clone)
        self._tools.job_storage.delete_job_files(clone.job_id)
        self._tools.files.delete_clone_files(clone_id)

    def resolve_file(self, relative_path: str) -> Path:
        return self._tools.files.resolve_existing(relative_path)

    def _add_with_job(
        self, job: Job, prompt_options: dict, run_values: dict[str, Any]
    ) -> CloneSummary:
        clone_id = str(uuid4())
        prompts_by_key = prompt_options[PROMPTS_OPTION_KEY]
        job.options = {
            **job.options,
            PRESET_OPTION_KEY: prompt_options[PRESET_OPTION_KEY],
            PROMPTS_OPTION_KEY: {key.value: prompts_by_key[key.value] for key in JOB_PROMPT_KEYS},
            CLONE_ID_KEY: clone_id,
        }
        clone = self._tools.repository.add_with_job(
            job,
            FilmClone(
                id=clone_id,
                job_id=job.id,
                status=CloneStatus.RUNNING,
                step=CloneStep.ANALYZING,
                **run_values,
                preset=prompt_options[PRESET_OPTION_KEY],
                prompts={key.value: prompts_by_key[key.value] for key in CLONE_PROMPT_KEYS},
            ),
        )
        self._tools.notify_worker()
        return CloneSummary(clone, job, False)


def validate_automatic_run(options: CloneOptions) -> None:
    if options.should_run_automatically:
        validate_localization_choices(options.choices)


def to_automatic_run_values(options: CloneOptions) -> dict[str, Any]:
    if not options.should_run_automatically:
        return STEP_BY_STEP_RUN_VALUES
    return {"should_run_automatically": True, **to_choice_values(options.choices)}


def to_valid_clone_max_frames(requested_max_frames: int | None) -> int:
    if requested_max_frames is None:
        return DEFAULT_MAX_FRAMES
    lowest, highest = CLONE_MAX_FRAMES_LIMITS
    if not lowest <= requested_max_frames <= highest:
        raise InvalidCloneRequestError(f"Max frames must be between {lowest} and {highest}")
    return requested_max_frames
