from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.films.errors import FilmConflictError, FilmRequestNotFoundError
from app.modules.films.models import Episode, EpisodeStatus
from app.modules.films.repository import FilmRepository
from app.modules.films.request_service import FilmRequestService, FilmRequestTools
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.service import GenerationService


def build_request(**values) -> GenerationRequest:
    defaults = {
        "id": "r1",
        "kind": GenerationKind.SCENE_IMAGE,
        "status": GenerationStatus.QUEUED,
        "project_id": "p1",
        "episode_id": "e1",
        "character_id": None,
    }
    return GenerationRequest(**{**defaults, **values})


def build_requests(request: GenerationRequest | None, episodes: list[Episode] = ()):
    episodes_by_id = {episode.id: episode for episode in episodes}
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.side_effect = episodes_by_id.get
    repository.find_running_episodes_of_project.side_effect = lambda project_id: [
        episode
        for episode in episodes
        if episode.project_id == project_id and episode.status is EpisodeStatus.RUNNING
    ]
    request_repository = MagicMock(spec=GenerationRequestRepository)
    request_repository.find_by_id.side_effect = lambda request_id: (
        request if request is not None and request.id == request_id else None
    )
    generation_service = MagicMock(spec=GenerationService)
    generation_service.cancel_queued.side_effect = lambda requests: [
        setattr(item, "status", GenerationStatus.CANCELLED) for item in requests
    ]
    service = FilmRequestService(
        FilmRequestTools(
            repository=repository,
            request_repository=request_repository,
            generation_service=generation_service,
        )
    )
    return SimpleNamespace(service=service, generation_service=generation_service)


def build_episode(status: EpisodeStatus, number: int = 2) -> Episode:
    return Episode(id="e1", project_id="p1", number=number, status=status)


def capture(error_class, call) -> str:
    with pytest.raises(error_class) as caught:
        call()
    return str(caught.value)


@pytest.fixture
def cancelled_scene_request():
    parts = build_requests(build_request(), [build_episode(EpisodeStatus.PAUSED)])
    cancelled = parts.service.cancel("r1")
    return SimpleNamespace(cancelled=cancelled, generation_service=parts.generation_service)


@pytest.fixture
def cancelled_character_request():
    parts = build_requests(
        build_request(kind=GenerationKind.CHARACTER_IMAGE, episode_id=None, character_id="c1"),
        [build_episode(EpisodeStatus.DONE)],
    )
    return parts.service.cancel("r1")


@pytest.fixture
def cancelled_library_request():
    parts = build_requests(
        build_request(
            kind=GenerationKind.CHARACTER_IMAGE, project_id=None, episode_id=None, character_id="c1"
        )
    )
    return parts.service.cancel("r1")


@pytest.fixture(
    params=[None, build_request(id="r2"), build_request(kind=GenerationKind.CLONE_SCENE_IMAGE)],
    ids=["unknown", "other-id", "clone-kind"],
)
def missing_request_error(request):
    parts = build_requests(request.param)
    return capture(FilmRequestNotFoundError, lambda: parts.service.cancel("r1"))


@pytest.fixture(params=[GenerationStatus.PROCESSING, GenerationStatus.DONE])
def not_queued_error(request):
    parts = build_requests(build_request(status=request.param))
    return capture(FilmConflictError, lambda: parts.service.cancel("r1"))


@pytest.fixture
def running_episode_error():
    parts = build_requests(build_request(), [build_episode(EpisodeStatus.RUNNING)])
    return SimpleNamespace(
        message=capture(FilmConflictError, lambda: parts.service.cancel("r1")),
        generation_service=parts.generation_service,
    )


@pytest.fixture
def running_project_error():
    parts = build_requests(
        build_request(kind=GenerationKind.CHARACTER_IMAGE, episode_id=None, character_id="c1"),
        [build_episode(EpisodeStatus.RUNNING, number=3)],
    )
    return capture(FilmConflictError, lambda: parts.service.cancel("r1"))


def test_cancel_returns_the_cancelled_request(cancelled_scene_request):
    assert cancelled_scene_request.cancelled.status is GenerationStatus.CANCELLED


def test_cancel_goes_through_the_generation_service(cancelled_scene_request):
    assert cancelled_scene_request.generation_service.cancel_queued.call_args.args[0][0].id == "r1"


def test_a_character_request_is_cancelled_when_no_episode_runs(cancelled_character_request):
    assert cancelled_character_request.status is GenerationStatus.CANCELLED


def test_a_library_request_is_cancelled(cancelled_library_request):
    assert cancelled_library_request.status is GenerationStatus.CANCELLED


def test_cancel_of_an_unknown_or_clone_request_is_not_found(missing_request_error):
    assert missing_request_error == "Generation request r1 not found"


def test_only_a_queued_request_can_be_cancelled(not_queued_error):
    assert not_queued_error == "Only a queued request can be cancelled"


def test_cancel_is_refused_while_its_episode_runs(running_episode_error):
    assert running_episode_error.message == "Episode 2 is running — stop it first"


def test_a_refused_cancel_leaves_the_request(running_episode_error):
    running_episode_error.generation_service.cancel_queued.assert_not_called()


def test_a_character_request_is_refused_while_a_project_episode_runs(running_project_error):
    assert running_project_error == "Episode 3 is running — stop it first"
