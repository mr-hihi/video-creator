from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.common.captcha import CaptchaService
from app.main import create_app
from app.modules.jobs.errors import (
    InvalidUploadError,
    InvalidYoutubeJobError,
    JobNotFoundError,
    JobPresetNotFoundError,
    JobStillRunningError,
    NoCompressedVideoError,
    ResultNotReadyError,
    YoutubeUnreachableError,
)
from app.modules.jobs.film_analysis_service import FilmAnalysisJobService
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.service import (
    JobDetail,
    JobService,
    ResultArchive,
    VideoUpload,
    YoutubeJobRequest,
    YoutubeJobService,
)
from app.modules.jobs.storage import UploadTooLargeError

JOB_ID = "job-1"
CREATED_AT = datetime(2026, 9, 27, 9, 30, tzinfo=UTC)
UPLOAD_FILES = {"file": ("clip.mp4", b"video-bytes", "video/mp4")}
CAPTCHA_HEADERS = {"X-Captcha-Token": "token-1"}
YOUTUBE_LINK = "https://youtu.be/vfjegxHDOwI"


def build_job(job_status: JobStatus) -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.VIDEO_TO_MARKDOWN,
        status=job_status,
        step=None,
        source_filename="clip.mp4",
        options={"language": "vi"},
        error_message=None,
        created_at=CREATED_AT,
        started_at=None,
        finished_at=None,
    )


@pytest.fixture
def job_service():
    service = MagicMock(spec=JobService)
    service.create_video_to_markdown_job.return_value = build_job(JobStatus.PENDING)
    service.list_recent_jobs.return_value = [build_job(JobStatus.DONE)]
    return service


@pytest.fixture
def captcha_service():
    service = MagicMock(spec=CaptchaService)
    service.verify.return_value = True
    return service


@pytest.fixture
def youtube_job_service():
    service = MagicMock(spec=YoutubeJobService)
    service.create_youtube_to_markdown_job.return_value = build_job(JobStatus.PENDING)
    service.create_youtube_film_analysis_job.return_value = build_job(JobStatus.PENDING)
    return service


@pytest.fixture
def film_analysis_job_service():
    service = MagicMock(spec=FilmAnalysisJobService)
    service.create_film_analysis_job.return_value = build_job(JobStatus.PENDING)
    service.create_rerun_job.return_value = build_job(JobStatus.PENDING)
    return service


@pytest.fixture
def client(job_service, youtube_job_service, film_analysis_job_service, captcha_service):
    app = create_app()
    app.state.container = SimpleNamespace(
        job_service=job_service,
        youtube_job_service=youtube_job_service,
        film_analysis_job_service=film_analysis_job_service,
        captcha_service=captcha_service,
    )
    return TestClient(app)


def post_youtube_job(client: TestClient, body: dict):
    return client.post("/jobs/youtube-to-markdown", json=body, headers=CAPTCHA_HEADERS)


@pytest.fixture
def youtube_create_response(client):
    return post_youtube_job(client, {"url": YOUTUBE_LINK, "language": "ja"})


@pytest.fixture
def youtube_default_language_response(client):
    return post_youtube_job(client, {"url": YOUTUBE_LINK})


@pytest.fixture
def youtube_missing_url_response(client):
    return post_youtube_job(client, {"language": "auto"})


@pytest.fixture
def youtube_rejected_captcha_response(client, captcha_service):
    captcha_service.verify.return_value = False
    return client.post(
        "/jobs/youtube-to-markdown", json={"language": "auto"}, headers=CAPTCHA_HEADERS
    )


@pytest.fixture
def youtube_invalid_response(client, youtube_job_service):
    youtube_job_service.create_youtube_to_markdown_job.side_effect = InvalidYoutubeJobError(
        "Not a YouTube video link"
    )
    return post_youtube_job(client, {"url": "hello"})


@pytest.fixture
def youtube_unreachable_response(client, youtube_job_service):
    youtube_job_service.create_youtube_to_markdown_job.side_effect = YoutubeUnreachableError(
        "Could not reach YouTube: yt-dlp timed out after 30s"
    )
    return post_youtube_job(client, {"url": YOUTUBE_LINK})


@pytest.fixture
def create_response(client):
    return client.post(
        "/jobs/video-to-markdown",
        files=UPLOAD_FILES,
        data={"language": "vi", "presetId": "preset-1"},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def forwarded_upload(job_service, create_response):
    return job_service.create_video_to_markdown_job.call_args.args[0]


@pytest.fixture
def rejected_captcha_response(client, captcha_service):
    captcha_service.verify.return_value = False
    return client.post("/jobs/video-to-markdown", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def invalid_upload_response(client, job_service):
    job_service.create_video_to_markdown_job.side_effect = InvalidUploadError("Unsupported type")
    return client.post("/jobs/video-to-markdown", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def too_large_response(client, job_service):
    job_service.create_video_to_markdown_job.side_effect = UploadTooLargeError("Too large")
    return client.post("/jobs/video-to-markdown", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def list_response(client):
    return client.get("/jobs", params={"limit": 5})


@pytest.fixture
def out_of_range_list_response(client):
    return client.get("/jobs", params={"limit": 0})


@pytest.fixture
def filtered_list_response(client):
    return client.get("/jobs", params=[("type", "film_analysis"), ("type", "film_analysis_rerun")])


@pytest.fixture
def unknown_type_list_response(client):
    return client.get("/jobs", params={"type": "nope"})


@pytest.fixture
def film_detail_response(client, job_service):
    job_service.get_job_detail.return_value = JobDetail(
        job=build_job(JobStatus.PROCESSING),
        markdown=None,
        outputs={JobOutputKind.VIDEO_NOTES: "# Notes"},
    )
    return client.get(f"/jobs/{JOB_ID}")


@pytest.fixture
def film_upload_response(client):
    return client.post(
        "/jobs/film-analysis",
        files=UPLOAD_FILES,
        data={"language": "vi", "presetId": "preset-1", "maxFrames": "30"},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def forwarded_film_upload(film_analysis_job_service, film_upload_response):
    upload, max_frames = film_analysis_job_service.create_film_analysis_job.call_args.args
    return (upload.filename, upload.language, upload.preset_id, max_frames)


@pytest.fixture
def youtube_film_response(client):
    return client.post(
        "/jobs/youtube-film-analysis",
        json={"url": YOUTUBE_LINK, "language": "vi", "presetId": "preset-2", "maxFrames": 25},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def unknown_preset_response(client, youtube_job_service):
    youtube_job_service.create_youtube_film_analysis_job.side_effect = JobPresetNotFoundError(
        "nope"
    )
    return client.post(
        "/jobs/youtube-film-analysis",
        json={"url": YOUTUBE_LINK, "presetId": "nope"},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def rerun_response(client):
    return client.post(
        f"/jobs/{JOB_ID}/film-analysis-rerun",
        json={"presetId": "preset-2"},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def rerun_rejected_captcha_response(client, captcha_service):
    captcha_service.verify.return_value = False
    return client.post(f"/jobs/{JOB_ID}/film-analysis-rerun", json={}, headers=CAPTCHA_HEADERS)


@pytest.fixture
def rerun_without_compressed_video_response(client, film_analysis_job_service):
    film_analysis_job_service.create_rerun_job.side_effect = NoCompressedVideoError(JOB_ID)
    return client.post(f"/jobs/{JOB_ID}/film-analysis-rerun", json={}, headers=CAPTCHA_HEADERS)


@pytest.fixture
def delete_response(client):
    return client.delete(f"/jobs/{JOB_ID}")


@pytest.fixture
def delete_running_response(client, film_analysis_job_service):
    film_analysis_job_service.delete_film_analysis_job.side_effect = JobStillRunningError(JOB_ID)
    return client.delete(f"/jobs/{JOB_ID}")


@pytest.fixture
def missing_job_response(client, job_service):
    job_service.get_job_detail.side_effect = JobNotFoundError("missing")
    return client.get("/jobs/missing")


@pytest.fixture
def done_job_response(client, job_service):
    job_service.get_job_detail.return_value = JobDetail(
        job=build_job(JobStatus.DONE), markdown="# Clip\n", outputs=None
    )
    return client.get(f"/jobs/{JOB_ID}")


@pytest.fixture
def result_file_response(client, job_service, tmp_path):
    image = tmp_path / "moment-01-00m00s.jpg"
    image.write_bytes(b"jpg-bytes")
    job_service.resolve_result_file.return_value = image
    return client.get(f"/jobs/{JOB_ID}/files/images/moment-01-00m00s.jpg")


@pytest.fixture
def download_response(client, job_service, tmp_path):
    archive = tmp_path / "result.zip"
    archive.write_bytes(b"zip-bytes")
    job_service.get_result_archive.return_value = ResultArchive(
        path=archive, download_name="clip.zip"
    )
    return client.get(f"/jobs/{JOB_ID}/download")


@pytest.fixture
def not_ready_download_response(client, job_service):
    job_service.get_result_archive.side_effect = ResultNotReadyError(JOB_ID)
    return client.get(f"/jobs/{JOB_ID}/download")


def test_create_job_answers_201_with_camel_case_job(create_response):
    assert create_response.status_code == 201
    assert create_response.json() == {
        "id": JOB_ID,
        "type": "video_to_markdown",
        "status": "pending",
        "step": None,
        "sourceFilename": "clip.mp4",
        "options": {"language": "vi"},
        "errorMessage": None,
        "createdAt": "2026-09-27T09:30:00Z",
        "startedAt": None,
        "finishedAt": None,
        "aiUsed": {},
    }


def test_create_job_forwards_filename_language_and_preset(forwarded_upload):
    assert isinstance(forwarded_upload, VideoUpload)
    assert (forwarded_upload.filename, forwarded_upload.language, forwarded_upload.preset_id) == (
        "clip.mp4",
        "vi",
        "preset-1",
    )


def test_create_job_answers_403_when_captcha_is_rejected(rejected_captcha_response, job_service):
    assert rejected_captcha_response.status_code == 403
    job_service.create_video_to_markdown_job.assert_not_called()


def test_create_job_answers_400_on_invalid_upload(invalid_upload_response):
    assert invalid_upload_response.status_code == 400
    assert invalid_upload_response.json() == {"detail": "Unsupported type"}


def test_create_job_answers_413_on_oversized_upload(too_large_response):
    assert too_large_response.status_code == 413


def test_list_jobs_returns_recent_jobs(list_response, job_service):
    assert [job["status"] for job in list_response.json()] == ["done"]
    job_service.list_recent_jobs.assert_called_once_with(5, ())


def test_list_jobs_filters_by_every_given_type(filtered_list_response, job_service):
    job_service.list_recent_jobs.assert_called_once_with(
        50, [JobType.FILM_ANALYSIS, JobType.FILM_ANALYSIS_RERUN]
    )


def test_list_jobs_rejects_an_unknown_type(unknown_type_list_response):
    assert unknown_type_list_response.status_code == 422


def test_list_jobs_rejects_limit_out_of_range(out_of_range_list_response):
    assert out_of_range_list_response.status_code == 422


def test_get_job_answers_404_when_missing(missing_job_response):
    assert missing_job_response.status_code == 404
    assert missing_job_response.json() == {"detail": "Job missing not found"}


def test_get_job_includes_markdown(done_job_response):
    assert done_job_response.json()["markdown"] == "# Clip\n"
    assert done_job_response.json()["outputs"] is None


def test_get_job_includes_film_outputs_in_camel_case(film_detail_response):
    assert film_detail_response.json()["outputs"] == {
        "videoNotes": "# Notes",
        "characterImagePrompts": None,
        "characterVoicePrompts": None,
        "scenePrompts": None,
    }


def test_get_result_file_serves_file_bytes(result_file_response, job_service):
    assert result_file_response.content == b"jpg-bytes"
    job_service.resolve_result_file.assert_called_once_with(JOB_ID, "images/moment-01-00m00s.jpg")


def test_download_result_serves_zip_as_attachment(download_response):
    assert download_response.headers["content-type"] == "application/zip"
    assert 'filename="clip.zip"' in download_response.headers["content-disposition"]


def test_download_result_answers_409_before_the_job_is_done(not_ready_download_response):
    assert not_ready_download_response.status_code == 409


def test_create_youtube_job_answers_201_with_the_job(youtube_create_response):
    assert youtube_create_response.status_code == 201
    assert youtube_create_response.json()["id"] == JOB_ID


def test_create_youtube_job_forwards_link_and_language(
    youtube_job_service, youtube_create_response
):
    youtube_job_service.create_youtube_to_markdown_job.assert_called_once_with(
        YoutubeJobRequest(link=YOUTUBE_LINK, language="ja", preset_id=None)
    )


def test_create_youtube_job_defaults_the_language_to_auto(
    youtube_job_service, youtube_default_language_response
):
    youtube_job_service.create_youtube_to_markdown_job.assert_called_once_with(
        YoutubeJobRequest(link=YOUTUBE_LINK, language="auto", preset_id=None)
    )


def test_create_youtube_job_answers_422_without_a_url(youtube_missing_url_response):
    assert youtube_missing_url_response.status_code == 422
    assert youtube_missing_url_response.json()["detail"][0]["loc"] == ["body", "url"]


def test_create_youtube_job_answers_403_before_reading_the_body(
    youtube_rejected_captcha_response, youtube_job_service
):
    assert youtube_rejected_captcha_response.status_code == 403
    youtube_job_service.create_youtube_to_markdown_job.assert_not_called()


def test_create_youtube_job_answers_400_on_an_invalid_video(youtube_invalid_response):
    assert youtube_invalid_response.status_code == 400
    assert youtube_invalid_response.json() == {"detail": "Not a YouTube video link"}


def test_create_youtube_job_answers_502_when_youtube_is_unreachable(youtube_unreachable_response):
    assert youtube_unreachable_response.status_code == 502
    assert youtube_unreachable_response.json() == {
        "detail": "Could not reach YouTube: yt-dlp timed out after 30s"
    }


def test_create_film_analysis_job_forwards_upload_and_max_frames(forwarded_film_upload):
    assert forwarded_film_upload == ("clip.mp4", "vi", "preset-1", 30)


def test_create_youtube_film_analysis_job_forwards_request_and_max_frames(
    youtube_film_response, youtube_job_service
):
    assert youtube_film_response.status_code == 201
    youtube_job_service.create_youtube_film_analysis_job.assert_called_once_with(
        YoutubeJobRequest(link=YOUTUBE_LINK, language="vi", preset_id="preset-2"), 25
    )


def test_create_youtube_film_analysis_job_answers_400_on_unknown_preset(unknown_preset_response):
    assert unknown_preset_response.status_code == 400
    assert unknown_preset_response.json() == {"detail": "Prompt preset nope not found"}


def test_rerun_forwards_source_job_and_preset(rerun_response, film_analysis_job_service):
    assert rerun_response.status_code == 201
    film_analysis_job_service.create_rerun_job.assert_called_once_with(JOB_ID, "preset-2")


def test_rerun_answers_409_without_compressed_video(rerun_without_compressed_video_response):
    assert rerun_without_compressed_video_response.status_code == 409
    assert rerun_without_compressed_video_response.json() == {
        "detail": f"Job {JOB_ID} has no compressed video to reuse"
    }


def test_rerun_answers_403_when_captcha_is_rejected(
    rerun_rejected_captcha_response, film_analysis_job_service
):
    assert rerun_rejected_captcha_response.status_code == 403
    film_analysis_job_service.create_rerun_job.assert_not_called()


def test_delete_job_answers_204(delete_response, film_analysis_job_service):
    assert delete_response.status_code == 204
    film_analysis_job_service.delete_film_analysis_job.assert_called_once_with(JOB_ID)


def test_delete_job_answers_409_while_running(delete_running_response):
    assert delete_running_response.status_code == 409
    assert delete_running_response.json() == {"detail": f"Job {JOB_ID} is still running"}
