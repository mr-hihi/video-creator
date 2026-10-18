import shutil
from dataclasses import dataclass
from pathlib import Path

from app.modules.films.errors import FilmConflictError, FilmNotFoundError, InvalidFilmRequestError
from app.modules.films.film_files import FilmFiles
from app.modules.films.models import Episode
from app.modules.jobs.models import FILM_ANALYSIS_JOB_TYPES, Job, JobOutputKind, JobStatus
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import IMAGES_DIR_NAME, JobStorage
from app.modules.prompt_presets.prompt_texts import FilmScriptAnalysis

SOURCE_JOB_REQUIRED_MESSAGE = "sourceJobId is required for a film analysis source"
JOB_NOT_FOUND_MESSAGE = "Job {job_id} not found"
NOT_FILM_ANALYSIS_MESSAGE = "Job {job_id} is not a film analysis"
JOB_NOT_DONE_MESSAGE = "Job {job_id} is not done"
PROMPT_FILE_NAMES_BY_KIND = {
    JobOutputKind.CHARACTER_IMAGE_PROMPTS: "character_image_prompts.md",
    JobOutputKind.CHARACTER_VOICE_PROMPTS: "character_voice_prompts.md",
    JobOutputKind.SCENE_PROMPTS: "scene_prompts.md",
}
TEXT_ENCODING = "utf-8"


@dataclass(frozen=True)
class AnalysisSourceTools:
    files: FilmFiles
    job_repository: JobRepository
    job_storage: JobStorage


class AnalysisSource:
    def __init__(self, tools: AnalysisSourceTools):
        self._tools = tools

    def get_done_job(self, job_id: str | None) -> Job:
        if not job_id:
            raise InvalidFilmRequestError(SOURCE_JOB_REQUIRED_MESSAGE)
        job = self._tools.job_repository.find_by_id(job_id)
        if job is None:
            raise FilmNotFoundError(JOB_NOT_FOUND_MESSAGE.format(job_id=job_id))
        if job.type not in FILM_ANALYSIS_JOB_TYPES:
            raise FilmConflictError(NOT_FILM_ANALYSIS_MESSAGE.format(job_id=job_id))
        if job.status is not JobStatus.DONE:
            raise FilmConflictError(JOB_NOT_DONE_MESSAGE.format(job_id=job_id))
        return job

    def has_job(self, job_id: str | None) -> bool:
        if job_id is None:
            return False
        return self._tools.job_repository.find_by_id(job_id) is not None

    def copy_into(self, episode: Episode) -> None:
        job_id = episode.source_job_id or ""
        source_dir = self._source_dir(episode)
        source_dir.mkdir(parents=True, exist_ok=True)
        outputs = self._tools.job_repository.find_outputs(job_id)
        for kind, file_name in PROMPT_FILE_NAMES_BY_KIND.items():
            (source_dir / file_name).write_text(outputs.get(kind, ""), encoding=TEXT_ENCODING)
        frames_dir = self._tools.job_storage.images_dir(job_id)
        if frames_dir.is_dir():
            shutil.copytree(frames_dir, source_dir / IMAGES_DIR_NAME)

    def read(self, episode: Episode) -> FilmScriptAnalysis:
        texts_by_kind = {
            kind: self._read_text(self._source_dir(episode) / file_name)
            for kind, file_name in PROMPT_FILE_NAMES_BY_KIND.items()
        }
        return FilmScriptAnalysis(
            character_image_prompts=texts_by_kind[JobOutputKind.CHARACTER_IMAGE_PROMPTS],
            character_voice_prompts=texts_by_kind[JobOutputKind.CHARACTER_VOICE_PROMPTS],
            scene_prompts=texts_by_kind[JobOutputKind.SCENE_PROMPTS],
            frame_names=self._find_frame_names(episode),
        )

    def frame_path(self, episode: Episode, frame_name: str) -> Path:
        return self._source_dir(episode) / IMAGES_DIR_NAME / frame_name

    def _find_frame_names(self, episode: Episode) -> list[str]:
        frames_dir = self._source_dir(episode) / IMAGES_DIR_NAME
        if not frames_dir.is_dir():
            return []
        return sorted(path.name for path in frames_dir.iterdir() if path.is_file())

    def _source_dir(self, episode: Episode) -> Path:
        return self._tools.files.source_dir(episode.project_id, episode.id)

    def _read_text(self, file_path: Path) -> str:
        if not file_path.is_file():
            return ""
        return file_path.read_text(encoding=TEXT_ENCODING)
