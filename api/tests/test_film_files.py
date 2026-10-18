import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.films.errors import FilmFileNotFoundError, FilmFileTooLargeError
from app.modules.films.film_files import FilmFiles, build_episode_stem

UPLOAD_MAX_MB = 1
BYTES_PER_MB = 1024 * 1024


@pytest.fixture
def files(tmp_path):
    return FilmFiles(tmp_path, UPLOAD_MAX_MB)


@pytest.fixture
def saved_upload(files):
    destination = files.character_reference_path("c1", "png")
    old_file = files.character_reference_path("c1", "jpg")
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"old")
    saved = files.save_upload(io.BytesIO(b"new image"), destination, "Image exceeds 1 MB")
    return SimpleNamespace(saved=saved, old_file=old_file)


@pytest.fixture
def too_large_upload(files):
    destination = files.voice_sample_path("v1", "wav")
    with pytest.raises(FilmFileTooLargeError) as error:
        files.save_upload(io.BytesIO(b"x" * (BYTES_PER_MB + 1)), destination, "Audio exceeds 1 MB")
    return SimpleNamespace(error=error.value, destination=destination)


@pytest.fixture
def copied_file(files, tmp_path):
    source = tmp_path / "frame.jpg"
    source.write_bytes(b"frame")
    return files.copy_into(source, files.scene_image_path("p1", "e1", "s1", "jpg"))


@pytest.fixture
def resolved_file(files, copied_file):
    return files.resolve_existing(files.to_relative(copied_file))


@pytest.fixture(params=["../outside.txt", "projects/p1/missing.png"])
def unresolved_error(request, files, tmp_path):
    (tmp_path / "outside.txt").write_text("secret")
    with pytest.raises(FilmFileNotFoundError) as error:
        files.resolve_existing(request.param)
    return error.value


@pytest.fixture
def deleted_paths(files, copied_file):
    relative_path = files.to_relative(copied_file)
    files.delete(relative_path)
    files.delete(None)
    files.delete_dir(files.project_dir("p1"))
    return SimpleNamespace(file=copied_file, project_dir=files.project_dir("p1"))


@pytest.fixture
def named_paths(files):
    return [
        files.to_relative(files.source_dir("p1", "e1")),
        files.to_relative(files.voice_consent_path("v1", "m4a")),
        files.max_upload_mb,
    ]


@pytest.fixture(
    params=[
        (("Hong Nhat", 2, "Race Against Time"), "Hong Nhat - E02 - Race Against Time"),
        (("A/B", 12, "Who?"), "A_B - E12 - Who"),
    ]
)
def episode_stem(request):
    arguments, expected = request.param
    return SimpleNamespace(actual=build_episode_stem(*arguments), expected=expected)


@pytest.fixture
def path_from_relative_storage(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    files = FilmFiles(Path("storage-test"), UPLOAD_MAX_MB)
    return SimpleNamespace(
        actual=files.to_absolute("projects/p1/clip.mp4"), base=tmp_path.resolve()
    )


def test_upload_replaces_the_other_extension(saved_upload):
    assert saved_upload.saved.read_bytes() == b"new image"
    assert not saved_upload.old_file.exists()


def test_upload_over_the_cap_is_refused_and_removed(too_large_upload):
    assert str(too_large_upload.error) == "Audio exceeds 1 MB"
    assert not too_large_upload.destination.exists()
    assert list(too_large_upload.destination.parent.iterdir()) == []


def test_copy_lands_at_the_scene_path(copied_file, files):
    assert files.to_relative(copied_file) == "projects/p1/episodes/e1/scenes/s1/image.jpg"
    assert copied_file.read_bytes() == b"frame"


def test_existing_file_resolves(resolved_file, copied_file):
    assert resolved_file == copied_file.resolve()


def test_missing_or_outside_file_is_not_found(unresolved_error):
    assert str(unresolved_error).startswith("File ")


def test_delete_removes_files_and_folders(deleted_paths):
    assert not deleted_paths.file.exists()
    assert not deleted_paths.project_dir.exists()


def test_episode_stem_is_safe(episode_stem):
    assert episode_stem.actual == episode_stem.expected


def test_named_paths_follow_the_storage_layout(named_paths):
    assert named_paths == ["projects/p1/episodes/e1/source", "voices/v1/consent.m4a", UPLOAD_MAX_MB]


def test_a_relative_storage_dir_gives_absolute_paths(path_from_relative_storage):
    assert path_from_relative_storage.actual == (
        path_from_relative_storage.base / "storage-test/films/projects/p1/clip.mp4"
    )
