from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.films.errors import (
    EpisodeNotFoundError,
    EpisodeRunningError,
    FilmConflictError,
    FilmFileNotFoundError,
    FilmRequestNotFoundError,
    InvalidFilmRequestError,
)
from app.modules.films.film_outputs import FilmOutput
from app.modules.films.http_errors import register_film_error_handlers
from app.modules.films.models import (
    Episode,
    EpisodeSource,
    EpisodeStatus,
    MediaStatus,
    SubtitleStyle,
)
from app.modules.films.request_service import FilmRequestService
from app.modules.films.result_files import EpisodeDownload, FilmResultFiles
from app.modules.films.result_router import router
from app.modules.films.thumbnail_service import FilmThumbnailService
from app.modules.films.views import EpisodeSummary
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.providers.provider_catalog import MediaKind

CREATED_AT = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
THUMBNAIL_PATH = (
    "projects/p1/episodes/e1/output/Test Series - E02 - Race Against Time-thumbnail.jpg"
)


def build_episode() -> Episode:
    return Episode(
        id="e1",
        project_id="p1",
        number=2,
        title="Race Against Time",
        logline=None,
        source=EpisodeSource.IDEA,
        idea="A bell under the sea.",
        source_job_id=None,
        source_clone_id=None,
        target_duration_s=21,
        stop_points={"afterScript": False, "afterReferences": False, "afterSceneImages": True},
        burn_subtitles=False,
        subtitle_style=SubtitleStyle.CLEAN_WHITE,
        music_prompt=None,
        thumbnail_prompt="Mai holding a glowing compass in the fog",
        music_status=MediaStatus.NONE,
        music_path=None,
        music_error=None,
        preset={"id": "p-1", "name": "Default", "version": 1},
        ai_used={},
        status=EpisodeStatus.DONE,
        step=None,
        error_message=None,
        needs_assembly=False,
        video_path="projects/p1/episodes/e1/output/Test Series - E02 - Race Against Time.mp4",
        subtitles_path=None,
        thumbnail_path=THUMBNAIL_PATH,
        duration_ms=17_700,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        started_at=CREATED_AT,
        finished_at=CREATED_AT,
    )


def build_request(candidate: int) -> GenerationRequest:
    return GenerationRequest(
        id=f"r{candidate}",
        kind=GenerationKind.THUMBNAIL,
        media_kind=MediaKind.IMAGE,
        project_id="p1",
        clone_id=None,
        episode_id="e1",
        scene_id=None,
        character_id=None,
        clone_asset_id=None,
        clone_scene_id=None,
        provider="google_flow",
        status=GenerationStatus.QUEUED,
        params={"aspect": "16:9", "candidate": candidate},
        attempts=0,
        next_attempt_at=None,
        error_message=None,
        created_at=CREATED_AT,
        started_at=None,
        finished_at=None,
    )


def build_client() -> SimpleNamespace:
    thumbnails = MagicMock(spec=FilmThumbnailService)
    result_files = MagicMock(spec=FilmResultFiles)
    requests = MagicMock(spec=FilmRequestService)
    app = FastAPI()
    app.include_router(router)
    register_film_error_handlers(app)
    app.state.container = SimpleNamespace(
        film_thumbnail_service=thumbnails,
        film_result_files=result_files,
        film_request_service=requests,
    )
    return SimpleNamespace(
        client=TestClient(app), thumbnails=thumbnails, result_files=result_files, requests=requests
    )


@pytest.fixture
def api():
    return build_client()


@pytest.fixture
def generate_response(api):
    api.thumbnails.generate_candidates.return_value = [build_request(k) for k in (1, 2, 3, 4)]
    return api.client.post("/films/episodes/e1/thumbnails")


@pytest.fixture
def busy_generate_response(api):
    api.thumbnails.generate_candidates.side_effect = FilmConflictError(
        "Thumbnails are already being generated"
    )
    return api.client.post("/films/episodes/e1/thumbnails")


@pytest.fixture
def choose_response(api):
    api.thumbnails.choose_candidate.return_value = EpisodeSummary(episode=build_episode())
    return api.client.post("/films/episodes/e1/thumbnail", json={"candidate": 2})


@pytest.fixture
def out_of_range_choose_response(api):
    api.thumbnails.choose_candidate.side_effect = InvalidFilmRequestError("Candidate must be 1-4")
    return api.client.post("/films/episodes/e1/thumbnail", json={"candidate": 5})


@pytest.fixture
def cancel_response(api):
    cancelled = build_request(1)
    cancelled.status = GenerationStatus.CANCELLED
    api.requests.cancel.return_value = cancelled
    return api.client.post("/films/requests/r1/cancel")


@pytest.fixture
def cancel_failure_response(api, request):
    api.requests.cancel.side_effect = request.param
    return api.client.post("/films/requests/r1/cancel")


@pytest.fixture
def video_download_response(api, tmp_path):
    video_file = tmp_path / "film.mp4"
    video_file.write_bytes(b"mp4-bytes")
    api.result_files.get_download.return_value = EpisodeDownload(
        path=video_file, file_name="Test Series - E02 - Race Against Time.mp4"
    )
    return api.client.get("/films/episodes/e1/download", params={"file": "video"})


@pytest.fixture
def missing_subtitles_response(api):
    api.result_files.get_download.side_effect = FilmConflictError("Episode 2 has no subtitles yet")
    return api.client.get("/films/episodes/e1/download", params={"file": "subtitles"})


@pytest.fixture
def unknown_episode_download_response(api):
    api.result_files.get_download.side_effect = EpisodeNotFoundError(
        "00000000-0000-0000-0000-000000000000"
    )
    return api.client.get(
        "/films/episodes/00000000-0000-0000-0000-000000000000/download", params={"file": "video"}
    )


@pytest.fixture
def unknown_file_kind_response(api):
    return api.client.get("/films/episodes/e1/download", params={"file": "music"})


@pytest.fixture
def preview_response(api, tmp_path):
    candidate_file = tmp_path / "thumbnail-candidate-1.png"
    candidate_file.write_bytes(b"png-bytes")
    api.result_files.resolve_preview.return_value = candidate_file
    return api.client.get("/films/files/projects/p1/episodes/e1/output/thumbnail-candidate-1.png")


@pytest.fixture
def outside_preview_response(api):
    api.result_files.resolve_preview.side_effect = FilmFileNotFoundError("../../api/.env")
    return api.client.get("/films/files/%2e%2e/%2e%2e/api/.env")


def test_generate_thumbnails_answers_202_with_the_queued_requests(generate_response):
    assert (generate_response.status_code, generate_response.json()[1]["params"]) == (
        202,
        {"aspect": "16:9", "candidate": 2},
    )


def test_generate_thumbnails_returns_four_requests(generate_response):
    assert [request["id"] for request in generate_response.json()] == ["r1", "r2", "r3", "r4"]


def test_generate_thumbnails_passes_the_episode_id(api, generate_response):
    assert api.thumbnails.generate_candidates.call_args.args == ("e1",)


def test_generate_thumbnails_maps_a_conflict_to_409(busy_generate_response):
    assert (busy_generate_response.status_code, busy_generate_response.json()) == (
        409,
        {"detail": "Thumbnails are already being generated"},
    )


def test_choose_thumbnail_returns_the_episode(choose_response):
    assert (
        choose_response.status_code,
        choose_response.json()["thumbnailPath"],
        choose_response.json()["needsAssembly"],
        choose_response.json()["targetDurationS"],
    ) == (200, THUMBNAIL_PATH, False, 21)


def test_choose_thumbnail_passes_the_candidate(api, choose_response):
    assert api.thumbnails.choose_candidate.call_args.args == ("e1", 2)


def test_choose_thumbnail_maps_a_bad_candidate_to_400(out_of_range_choose_response):
    assert (out_of_range_choose_response.status_code, out_of_range_choose_response.json()) == (
        400,
        {"detail": "Candidate must be 1-4"},
    )


def test_cancel_request_returns_the_cancelled_request(cancel_response):
    assert (cancel_response.status_code, cancel_response.json()["status"]) == (200, "cancelled")


def test_cancel_request_passes_the_request_id(api, cancel_response):
    assert api.requests.cancel.call_args.args == ("r1",)


@pytest.mark.parametrize(
    ("cancel_failure_response", "expected"),
    [
        (FilmRequestNotFoundError("r1"), (404, "Generation request r1 not found")),
        (
            FilmConflictError("Only a queued request can be cancelled"),
            (409, "Only a queued request can be cancelled"),
        ),
        (EpisodeRunningError(2), (409, "Episode 2 is running — stop it first")),
    ],
    indirect=["cancel_failure_response"],
)
def test_cancel_request_maps_its_errors(cancel_failure_response, expected):
    assert (
        cancel_failure_response.status_code,
        cancel_failure_response.json()["detail"],
    ) == expected


def test_download_sends_the_file_as_an_attachment(video_download_response):
    assert (
        video_download_response.status_code,
        video_download_response.headers["content-disposition"],
        video_download_response.content,
    ) == (
        200,
        "attachment; filename*=utf-8''Test%20Series%20-%20E02%20-%20Race%20Against%20Time.mp4",
        b"mp4-bytes",
    )


def test_download_reads_the_file_kind_from_the_query(api, video_download_response):
    assert api.result_files.get_download.call_args.args == ("e1", FilmOutput.VIDEO)


def test_download_maps_a_missing_output_to_409(missing_subtitles_response):
    assert (missing_subtitles_response.status_code, missing_subtitles_response.json()) == (
        409,
        {"detail": "Episode 2 has no subtitles yet"},
    )


def test_download_maps_an_unknown_episode_to_404(unknown_episode_download_response):
    assert (
        unknown_episode_download_response.status_code,
        unknown_episode_download_response.json(),
    ) == (404, {"detail": "Episode 00000000-0000-0000-0000-000000000000 not found"})


def test_download_rejects_an_unknown_file_kind(unknown_file_kind_response):
    assert unknown_file_kind_response.status_code == 422


def test_files_route_serves_a_preview(preview_response):
    assert (preview_response.status_code, preview_response.content) == (200, b"png-bytes")


def test_files_route_passes_the_relative_path(api, preview_response):
    assert api.result_files.resolve_preview.call_args.args == (
        "projects/p1/episodes/e1/output/thumbnail-candidate-1.png",
    )


def test_files_route_maps_a_path_outside_films_to_404(outside_preview_response):
    assert outside_preview_response.status_code == 404
