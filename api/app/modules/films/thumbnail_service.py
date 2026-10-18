from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.modules.films.errors import FilmConflictError, InvalidFilmRequestError
from app.modules.films.film_access import EpisodeContext, FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_outputs import FilmOutput, build_output_file_name
from app.modules.films.media_queue import CANDIDATE_PARAM, FilmMediaQueue
from app.modules.films.models import Episode
from app.modules.films.repository import FilmRepository
from app.modules.films.views import EpisodeSummary
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus

THUMBNAIL_CANDIDATES = (1, 2, 3, 4)
ANY_FILE_EXTENSION = "*"
NO_THUMBNAIL_PROMPT_MESSAGE = "Episode {number} has no thumbnail prompt"
THUMBNAILS_RUNNING_MESSAGE = "Thumbnails are already being generated"
CANDIDATE_RANGE_MESSAGE = "Candidate must be 1-4"
CANDIDATE_NOT_READY_MESSAGE = "Thumbnail candidate {candidate} is not ready"


class ThumbnailCropper(Protocol):
    def crop_to_fill(self, source_path: Path, target_path: Path) -> None: ...


@dataclass(frozen=True)
class ThumbnailServiceTools:
    access: FilmAccess
    repository: FilmRepository
    files: FilmFiles
    media_queue: FilmMediaQueue
    cropper: ThumbnailCropper


class FilmThumbnailService:
    def __init__(self, tools: ThumbnailServiceTools):
        self._tools = tools

    def generate_candidates(self, episode_id: str) -> list[GenerationRequest]:
        context = self._tools.access.get_editable_episode(episode_id)
        self._ensure_can_generate(context.episode)
        scenes = self._tools.repository.find_scenes(episode_id)
        self._delete_candidate_files(context)
        return [
            self._tools.media_queue.queue_thumbnail(
                context.project, context.episode, scenes, candidate
            )
            for candidate in THUMBNAIL_CANDIDATES
        ]

    def choose_candidate(self, episode_id: str, candidate: int) -> EpisodeSummary:
        context = self._tools.access.get_writable_episode(episode_id)
        if candidate not in THUMBNAIL_CANDIDATES:
            raise InvalidFilmRequestError(CANDIDATE_RANGE_MESSAGE)
        candidate_path = self._find_ready_candidate_path(episode_id, candidate)
        thumbnail_path = self._crop_thumbnail(context, candidate_path)
        self._tools.repository.update_episode(episode_id, {"thumbnail_path": thumbnail_path})
        self._remove_replaced(context.episode.thumbnail_path, thumbnail_path)
        episode = self._tools.repository.find_episode(episode_id) or context.episode
        return EpisodeSummary(episode=episode)

    def _ensure_can_generate(self, episode: Episode) -> None:
        if not (episode.thumbnail_prompt or "").strip():
            raise FilmConflictError(NO_THUMBNAIL_PROMPT_MESSAGE.format(number=episode.number))
        open_requests = self._tools.repository.find_open_requests_for_episode(episode.id)
        if any(request.kind is GenerationKind.THUMBNAIL for request in open_requests):
            raise FilmConflictError(THUMBNAILS_RUNNING_MESSAGE)

    def _delete_candidate_files(self, context: EpisodeContext) -> None:
        for candidate in THUMBNAIL_CANDIDATES:
            pattern_path = self._tools.files.thumbnail_candidate_path(
                context.project.id, context.episode.id, candidate, ANY_FILE_EXTENSION
            )
            for candidate_file in pattern_path.parent.glob(pattern_path.name):
                candidate_file.unlink(missing_ok=True)

    def _crop_thumbnail(self, context: EpisodeContext, candidate_path: Path) -> str:
        output_dir = self._tools.files.output_dir(context.project.id, context.episode.id)
        thumbnail_path = output_dir / build_output_file_name(context, FilmOutput.THUMBNAIL)
        self._tools.cropper.crop_to_fill(candidate_path, thumbnail_path)
        return self._tools.files.to_relative(thumbnail_path)

    def _remove_replaced(self, previous_path: str | None, current_path: str) -> None:
        if previous_path != current_path:
            self._tools.files.delete(previous_path)

    def _find_ready_candidate_path(self, episode_id: str, candidate: int) -> Path:
        requests = self._tools.repository.find_latest_requests(episode_id, GenerationKind.THUMBNAIL)
        newest_request = next(
            (request for request in requests if request.params.get(CANDIDATE_PARAM) == candidate),
            None,
        )
        if newest_request is None or not _is_ready_candidate(newest_request):
            raise FilmConflictError(CANDIDATE_NOT_READY_MESSAGE.format(candidate=candidate))
        return Path(newest_request.output_path or "")


def _is_ready_candidate(request: GenerationRequest) -> bool:
    return (
        request.status is GenerationStatus.DONE
        and request.output_path is not None
        and Path(request.output_path).is_file()
    )
