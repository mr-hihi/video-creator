import zipfile
from dataclasses import dataclass
from io import BytesIO

import pytest

from app.modules.jobs.storage import JobStorage, UploadTooLargeError, to_safe_stem

JOB_ID = "job-1"


@dataclass(frozen=True)
class Outcome:
    actual: str
    expected: str


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=8)


@pytest.fixture
def oversized_upload_error(storage):
    with pytest.raises(UploadTooLargeError) as caught:
        storage.save_source(JOB_ID, "clip.mp4", BytesIO(b"123456789"))
    return caught.value


@pytest.fixture
def archived_names(storage):
    storage.create_processing_dirs(JOB_ID)
    storage.markdown_path(JOB_ID, "clip.mp4").write_text("# Clip", encoding="utf-8")
    (storage.images_dir(JOB_ID) / "moment-01-00m00s.jpg").write_bytes(b"jpg")
    with zipfile.ZipFile(storage.write_archive(JOB_ID)) as archive:
        return archive.namelist()


@pytest.fixture
def saved_result(storage):
    storage.create_processing_dirs(JOB_ID)
    storage.save_result(JOB_ID, "clip.mp4", "# Clip\n")
    with zipfile.ZipFile(storage.archive_path(JOB_ID)) as archive:
        return storage.markdown_path(JOB_ID, "clip.mp4").read_text(
            encoding="utf-8"
        ), archive.namelist()


@pytest.fixture(
    params=[
        ("Phỏng vấn khách.mov", "Phỏng vấn khách"),
        ("a/b?.mp4", "b"),
        ("???.mp4", "video"),
    ]
)
def safe_stem(request):
    source_filename, expected = request.param
    return Outcome(actual=to_safe_stem(source_filename), expected=expected)


def test_save_source_rejects_upload_over_the_limit(oversized_upload_error):
    assert "8 byte limit" in str(oversized_upload_error)


def test_save_source_removes_the_partial_job_dir(storage, oversized_upload_error):
    assert not storage.job_dir(JOB_ID).exists()


def test_write_archive_contains_markdown_and_images(archived_names):
    assert archived_names == ["clip.md", "images/moment-01-00m00s.jpg"]


def test_to_safe_stem_keeps_letters_and_drops_unsafe_characters(safe_stem):
    assert safe_stem.actual == safe_stem.expected


def test_save_result_writes_the_markdown_and_archives_it(saved_result):
    assert saved_result == ("# Clip\n", ["clip.md"])


@pytest.fixture
def storage_with_frames(tmp_path):
    job_storage = JobStorage(tmp_path, max_upload_bytes=1024)
    job_storage.images_dir("source-1").mkdir(parents=True)
    (job_storage.images_dir("source-1") / "moment-01-00m00s.jpg").write_bytes(b"jpg")
    return job_storage


@pytest.fixture
def copied_frame_bytes(storage_with_frames):
    storage_with_frames.copy_images("source-1", "copy-1")
    return (storage_with_frames.images_dir("copy-1") / "moment-01-00m00s.jpg").read_bytes()


@pytest.fixture
def is_deleted_job_present(storage_with_frames):
    storage_with_frames.delete_job_files("source-1")
    return storage_with_frames.job_dir("source-1").exists()


@pytest.fixture
def is_missing_job_deleted_quietly(storage_with_frames):
    storage_with_frames.delete_job_files("never-created")
    return True


def test_copy_images_copies_every_frame_to_the_new_job(copied_frame_bytes):
    assert copied_frame_bytes == b"jpg"


def test_delete_job_files_removes_the_job_folder(is_deleted_job_present):
    assert is_deleted_job_present is False


def test_delete_job_files_ignores_a_missing_folder(is_missing_job_deleted_quietly):
    assert is_missing_job_deleted_quietly
