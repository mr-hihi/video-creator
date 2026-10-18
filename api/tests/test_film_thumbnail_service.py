from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    InvalidFilmRequestError,
    ProjectArchivedError,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue
from app.modules.films.models import (
    Episode,
    EpisodeStatus,
    FilmProject,
    ProjectStatus,
    Scene,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.thumbnail_service import FilmThumbnailService, ThumbnailServiceTools
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus

UPLOAD_MAX_MB = 20
CREATED_AT = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
OUTPUT_DIR = "projects/p1/episodes/e1/output"
THUMBNAIL_PATH = f"{OUTPUT_DIR}/Test Series - E02 - Race Against Time-thumbnail.jpg"
THUMBNAIL_PROMPT = "Mai holding a glowing compass in the fog"
SCENES = [Scene(id="s1", episode_id="e1", position=0, character_ids=["c1"])]


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "status": ProjectStatus.ACTIVE,
        "clip_duration_s": 8,
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 2,
        "title": "Race Against Time",
        "status": EpisodeStatus.DONE,
        "thumbnail_prompt": THUMBNAIL_PROMPT,
        "thumbnail_path": None,
        "needs_assembly": False,
    }
    return Episode(**{**defaults, **values})


def build_request(candidate: int, **values) -> GenerationRequest:
    defaults = {
        "id": f"r{candidate}",
        "kind": GenerationKind.THUMBNAIL,
        "episode_id": "e1",
        "params": {"candidate": candidate, "aspect": "16:9"},
        "status": GenerationStatus.QUEUED,
        "output_path": None,
        "created_at": CREATED_AT,
    }
    return GenerationRequest(**{**defaults, **values})


def write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"image")
    return path


def build_service(tmp_path: Path, episode: Episode, **values) -> SimpleNamespace:
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.side_effect = values.get("found_episodes", [episode, episode])
    repository.find_project.return_value = values.get("project", build_project())
    repository.find_scenes.return_value = SCENES
    repository.find_open_requests_for_episode.return_value = values.get("open_requests", [])
    repository.find_latest_requests.return_value = values.get("latest_requests", [])
    media_queue = MagicMock(spec=FilmMediaQueue)
    media_queue.queue_thumbnail.side_effect = [build_request(k) for k in (1, 2, 3, 4)]
    cropper = MagicMock()
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    service = FilmThumbnailService(
        ThumbnailServiceTools(
            access=FilmAccess(repository),
            repository=repository,
            files=files,
            media_queue=media_queue,
            cropper=cropper,
        )
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        media_queue=media_queue,
        cropper=cropper,
        files=files,
    )


def generate_error(tmp_path: Path, episode: Episode, **values) -> str:
    built = build_service(tmp_path, episode, **values)
    with pytest.raises((FilmConflictError, InvalidFilmRequestError)) as error_info:
        built.service.generate_candidates("e1")
    return str(error_info.value)


def choose_error(tmp_path: Path, candidate: int, **values) -> SimpleNamespace:
    built = build_service(tmp_path, build_episode(), **values)
    with pytest.raises((FilmConflictError, InvalidFilmRequestError)) as error_info:
        built.service.choose_candidate("e1", candidate)
    return SimpleNamespace(
        message=str(error_info.value),
        error_type=type(error_info.value),
        cropper=built.cropper,
    )


@pytest.fixture
def running_error(tmp_path):
    with pytest.raises(EpisodeRunningError) as error_info:
        build_service(
            tmp_path, build_episode(status=EpisodeStatus.RUNNING)
        ).service.generate_candidates("e1")
    return str(error_info.value)


@pytest.fixture
def archived_generate_error(tmp_path):
    with pytest.raises(ProjectArchivedError) as error_info:
        build_service(
            tmp_path, build_episode(), project=build_project(status=ProjectStatus.ARCHIVED)
        ).service.generate_candidates("e1")
    return str(error_info.value)


@pytest.fixture(params=[None, "", "   "])
def blank_prompt_error(tmp_path, request):
    return generate_error(tmp_path, build_episode(thumbnail_prompt=request.param))


@pytest.fixture
def already_generating_error(tmp_path):
    open_requests = [build_request(1, status=GenerationStatus.PROCESSING)]
    return generate_error(tmp_path, build_episode(), open_requests=open_requests)


@pytest.fixture
def generated(tmp_path):
    episode = build_episode()
    clip_request = build_request(1, kind=GenerationKind.SCENE_CLIP, scene_id="s1")
    built = build_service(tmp_path, episode, open_requests=[clip_request])
    output_dir = built.files.output_dir("p1", "e1")
    old_candidates = [
        write_file(output_dir / "thumbnail-candidate-1.png"),
        write_file(output_dir / "thumbnail-candidate-4.jpg"),
    ]
    film = write_file(output_dir / "Test Series - E02 - Race Against Time.mp4")
    requests = built.service.generate_candidates("e1")
    return SimpleNamespace(
        requests=requests,
        queue_calls=built.media_queue.queue_thumbnail.call_args_list,
        project=built.repository.find_project.return_value,
        episode=episode,
        kept_old_candidates=[path for path in old_candidates if path.exists()],
        is_film_kept=film.exists(),
    )


@pytest.fixture(params=[0, 5])
def out_of_range_choice(tmp_path, request):
    return choose_error(tmp_path, request.param)


@pytest.fixture
def archived_choose_error(tmp_path):
    built = build_service(
        tmp_path, build_episode(), project=build_project(status=ProjectStatus.ARCHIVED)
    )
    with pytest.raises(ProjectArchivedError) as error_info:
        built.service.choose_candidate("e1", 1)
    return str(error_info.value)


@pytest.fixture
def never_generated_choice(tmp_path):
    return choose_error(tmp_path, 2, latest_requests=[build_request(1)])


@pytest.fixture
def queued_choice(tmp_path):
    older_file = write_file(tmp_path / "old-candidate-2.png")
    latest_requests = [
        build_request(2, id="r-new"),
        build_request(2, id="r-old", status=GenerationStatus.DONE, output_path=str(older_file)),
    ]
    return choose_error(tmp_path, 2, latest_requests=latest_requests)


@pytest.fixture
def pathless_choice(tmp_path):
    latest_requests = [build_request(2, status=GenerationStatus.DONE)]
    return choose_error(tmp_path, 2, latest_requests=latest_requests)


@pytest.fixture
def missing_file_choice(tmp_path):
    latest_requests = [
        build_request(2, status=GenerationStatus.DONE, output_path=str(tmp_path / "gone.png"))
    ]
    return choose_error(tmp_path, 2, latest_requests=latest_requests)


@pytest.fixture
def chosen(tmp_path):
    episode = build_episode(thumbnail_path=f"{OUTPUT_DIR}/Old Title-thumbnail.jpg")
    reloaded = build_episode(thumbnail_path=THUMBNAIL_PATH)
    candidate_file = tmp_path / OUTPUT_DIR / "thumbnail-candidate-1.png"
    latest_requests = [
        build_request(2, status=GenerationStatus.DONE, output_path=str(tmp_path / "c2.png")),
        build_request(1, status=GenerationStatus.DONE, output_path=str(candidate_file)),
    ]
    built = build_service(
        tmp_path,
        episode,
        found_episodes=[episode, reloaded],
        latest_requests=latest_requests,
    )
    write_file(candidate_file)
    old_thumbnail = write_file(built.files.to_absolute(f"{OUTPUT_DIR}/Old Title-thumbnail.jpg"))
    summary = built.service.choose_candidate("e1", 1)
    return SimpleNamespace(
        summary=summary,
        reloaded=reloaded,
        candidate_file=candidate_file,
        thumbnail_file=built.files.to_absolute(THUMBNAIL_PATH),
        cropper=built.cropper,
        repository=built.repository,
        is_old_thumbnail_kept=old_thumbnail.exists(),
    )


@pytest.fixture
def rechosen(tmp_path):
    episode = build_episode(thumbnail_path=THUMBNAIL_PATH)
    candidate_file = write_file(tmp_path / OUTPUT_DIR / "thumbnail-candidate-3.png")
    built = build_service(
        tmp_path,
        episode,
        found_episodes=[episode, None],
        latest_requests=[
            build_request(3, status=GenerationStatus.DONE, output_path=str(candidate_file))
        ],
    )
    current_thumbnail = write_file(built.files.to_absolute(THUMBNAIL_PATH))
    summary = built.service.choose_candidate("e1", 3)
    return SimpleNamespace(
        summary=summary,
        episode=episode,
        is_current_thumbnail_kept=current_thumbnail.exists(),
    )


def test_generate_rejects_a_running_episode(running_error):
    assert running_error == "Episode 2 is running — stop it first"


def test_generate_rejects_an_archived_project(archived_generate_error):
    assert archived_generate_error == "Film project p1 is archived"


def test_generate_needs_a_thumbnail_prompt(blank_prompt_error):
    assert blank_prompt_error == "Episode 2 has no thumbnail prompt"


def test_generate_rejects_while_thumbnails_are_open(already_generating_error):
    assert already_generating_error == "Thumbnails are already being generated"


def test_generate_returns_the_four_queued_requests(generated):
    assert [request.id for request in generated.requests] == ["r1", "r2", "r3", "r4"]


def test_generate_queues_candidates_one_to_four(generated):
    assert generated.queue_calls == [
        call(generated.project, generated.episode, SCENES, 1),
        call(generated.project, generated.episode, SCENES, 2),
        call(generated.project, generated.episode, SCENES, 3),
        call(generated.project, generated.episode, SCENES, 4),
    ]


def test_generate_replaces_the_earlier_candidate_files(generated):
    assert (generated.kept_old_candidates, generated.is_film_kept) == ([], True)


def test_choose_rejects_a_candidate_outside_one_to_four(out_of_range_choice):
    assert (out_of_range_choice.message, out_of_range_choice.error_type) == (
        "Candidate must be 1-4",
        InvalidFilmRequestError,
    )


def test_choose_rejects_an_archived_project(archived_choose_error):
    assert archived_choose_error == "Film project p1 is archived"


def test_choose_rejects_a_candidate_never_generated(never_generated_choice):
    assert never_generated_choice.message == "Thumbnail candidate 2 is not ready"


def test_choose_uses_the_newest_request_of_the_candidate(queued_choice):
    assert (queued_choice.message, queued_choice.error_type) == (
        "Thumbnail candidate 2 is not ready",
        FilmConflictError,
    )


def test_choose_rejects_a_done_request_without_a_file_path(pathless_choice):
    assert pathless_choice.message == "Thumbnail candidate 2 is not ready"


def test_choose_rejects_a_done_request_whose_file_is_gone(missing_file_choice):
    assert missing_file_choice.message == "Thumbnail candidate 2 is not ready"


def test_choose_rejection_crops_nothing(missing_file_choice):
    assert missing_file_choice.cropper.crop_to_fill.call_count == 0


def test_choose_crops_the_candidate_into_the_episode_thumbnail(chosen):
    assert chosen.cropper.crop_to_fill.call_args_list == [
        call(chosen.candidate_file, chosen.thumbnail_file)
    ]


def test_choose_saves_only_the_thumbnail_path(chosen):
    assert chosen.repository.update_episode.call_args_list == [
        call("e1", {"thumbnail_path": THUMBNAIL_PATH})
    ]


def test_choose_returns_the_reloaded_episode(chosen):
    assert chosen.summary.episode is chosen.reloaded


def test_choose_removes_the_thumbnail_saved_under_a_previous_title(chosen):
    assert chosen.is_old_thumbnail_kept is False


def test_choose_again_keeps_the_rewritten_thumbnail(rechosen):
    assert rechosen.is_current_thumbnail_kept is True


def test_choose_falls_back_to_the_loaded_episode_when_it_cannot_reload(rechosen):
    assert rechosen.summary.episode is rechosen.episode
