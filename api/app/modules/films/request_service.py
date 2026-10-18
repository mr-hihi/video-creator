from dataclasses import dataclass

from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    FilmRequestNotFoundError,
)
from app.modules.films.models import Episode, EpisodeStatus
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import (
    CLONE_GENERATION_KINDS,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.service import GenerationService

NOT_QUEUED_MESSAGE = "Only a queued request can be cancelled"


@dataclass(frozen=True)
class FilmRequestTools:
    repository: FilmRepository
    request_repository: GenerationRequestRepository
    generation_service: GenerationService


class FilmRequestService:
    def __init__(self, tools: FilmRequestTools):
        self._tools = tools

    def cancel(self, request_id: str) -> GenerationRequest:
        request = self._tools.request_repository.find_by_id(request_id)
        if request is None or request.kind in CLONE_GENERATION_KINDS:
            raise FilmRequestNotFoundError(request_id)
        if request.status is not GenerationStatus.QUEUED:
            raise FilmConflictError(NOT_QUEUED_MESSAGE)
        running_episodes = self._find_running_episodes(request)
        if running_episodes:
            raise EpisodeRunningError(running_episodes[0].number)
        self._tools.generation_service.cancel_queued([request])
        return self._tools.request_repository.find_by_id(request_id) or request

    def _find_running_episodes(self, request: GenerationRequest) -> list[Episode]:
        if request.episode_id is not None:
            episode = self._tools.repository.find_episode(request.episode_id)
            if episode is None or episode.status is not EpisodeStatus.RUNNING:
                return []
            return [episode]
        if request.project_id is None:
            return []
        return self._tools.repository.find_running_episodes_of_project(request.project_id)
