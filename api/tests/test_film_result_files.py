from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.modules.films.errors import (
    EpisodeNotFoundError,
    FilmConflictError,
    FilmFileNotFoundError,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_outputs import FilmOutput
from app.modules.films.models import Episode, FilmProject, ProjectStatus
from app.modules.films.repository import FilmRepository
from app.modules.films.result_files import EpisodeDownload, FilmResultFiles

UPLOAD_MAX_MB = 20
OUTPUT_DIR = "projects/p1/episodes/e1/output"
STEM = "Test Series - E02 - Race Against Time"


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 2,
        "title": "Race Against Time",
        "video_path": f"{OUTPUT_DIR}/{STEM}.mp4",
        "subtitles_path": None,
        "thumbnail_path": f"{OUTPUT_DIR}/{STEM}-thumbnail.jpg",
    }
    return Episode(**{**defaults, **values})


def build_result_files(tmp_path: Path, episode: Episode | None) -> FilmResultFiles:
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = episode
    repository.find_project.return_value = FilmProject(
        id="p1", name="Test Series", status=ProjectStatus.ACTIVE
    )
    return FilmResultFiles(FilmAccess(repository), FilmFiles(tmp_path, UPLOAD_MAX_MB))


def write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"data")
    return path


@pytest.fixture
def films_root(tmp_path):
    return tmp_path / "films"


@pytest.fixture
def video_download(tmp_path, films_root):
    video_file = write_file(films_root / OUTPUT_DIR / f"{STEM}.mp4")
    download = build_result_files(tmp_path, build_episode()).get_download("e1", FilmOutput.VIDEO)
    return Outcome(download, EpisodeDownload(path=video_file.resolve(), file_name=f"{STEM}.mp4"))


@pytest.fixture
def renamed_subtitles_download(tmp_path, films_root):
    subtitles_file = write_file(films_root / OUTPUT_DIR / "Old Title.srt")
    episode = build_episode(subtitles_path=f"{OUTPUT_DIR}/Old Title.srt")
    download = build_result_files(tmp_path, episode).get_download("e1", FilmOutput.SUBTITLES)
    return Outcome(
        download, EpisodeDownload(path=subtitles_file.resolve(), file_name=f"{STEM}.srt")
    )


@pytest.fixture(
    params=[
        (FilmOutput.SUBTITLES, "Episode 2 has no subtitles yet"),
        (FilmOutput.THUMBNAIL, "Episode 2 has no thumbnail yet"),
    ]
)
def missing_output_error(tmp_path, request):
    output, expected = request.param
    with pytest.raises(FilmConflictError) as error_info:
        build_result_files(tmp_path, build_episode()).get_download("e1", output)
    return Outcome(str(error_info.value), expected)


@pytest.fixture
def unknown_episode_error(tmp_path):
    with pytest.raises(EpisodeNotFoundError) as error_info:
        build_result_files(tmp_path, None).get_download("e9", FilmOutput.VIDEO)
    return str(error_info.value)


@pytest.fixture
def preview_path(tmp_path, films_root):
    candidate = write_file(films_root / OUTPUT_DIR / "thumbnail-candidate-1.png")
    resolved = build_result_files(tmp_path, None).resolve_preview(
        f"{OUTPUT_DIR}/thumbnail-candidate-1.png"
    )
    return Outcome(resolved, candidate.resolve())


@pytest.fixture(params=["../api/.env", f"{OUTPUT_DIR}/missing.png", OUTPUT_DIR])
def preview_error(tmp_path, request):
    write_file(tmp_path / "api" / ".env")
    with pytest.raises(FilmFileNotFoundError) as error_info:
        build_result_files(tmp_path, None).resolve_preview(request.param)
    return Outcome(str(error_info.value), f"File {request.param} not found")


def test_get_download_names_the_video_after_the_episode(video_download):
    assert video_download.actual == video_download.expected


def test_get_download_names_the_file_after_the_current_title(renamed_subtitles_download):
    assert renamed_subtitles_download.actual == renamed_subtitles_download.expected


def test_get_download_rejects_an_output_not_made_yet(missing_output_error):
    assert missing_output_error.actual == missing_output_error.expected


def test_get_download_rejects_an_unknown_episode(unknown_episode_error):
    assert unknown_episode_error == "Episode e9 not found"


def test_resolve_preview_serves_a_file_under_films(preview_path):
    assert preview_path.actual == preview_path.expected


def test_resolve_preview_rejects_missing_files_and_paths_outside_films(preview_error):
    assert preview_error.actual == preview_error.expected
