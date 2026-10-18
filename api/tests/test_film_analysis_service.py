from io import BytesIO
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_calls import AiStepGroup, InputMode
from app.modules.ai_models.step_models import AiStepModels
from app.modules.app_settings.service import AppSettingService
from app.modules.jobs.errors import (
    InvalidFilmAnalysisJobError,
    InvalidUploadError,
    JobNotDeletableError,
    JobNotFoundError,
    JobPresetNotFoundError,
    JobStillRunningError,
    NotFilmAnalysisJobError,
    NoVideoNotesError,
)
from app.modules.jobs.film_analysis_service import FilmAnalysisJobService
from app.modules.jobs.job_intake import JobIntake, JobIntakeTools
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import VideoUpload
from app.modules.jobs.storage import JobStorage
from app.modules.prompt_presets.errors import PromptPresetNotFoundError
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.prompt_presets.service import PresetSnapshot, PromptPresetService

SOURCE_JOB_ID = "source-1"
PRESET_SNAPSHOT = PresetSnapshot(
    preset_id="preset-2", name="Three scenes", version=2, prompts=DEFAULT_PRESET_PROMPTS
)
SOURCE_OPTIONS = {
    "url": "https://www.youtube.com/watch?v=vfjegxHDOwI",
    "videoId": "vfjegxHDOwI",
    "language": "auto",
    "captionKind": "auto",
    "maxFrames": 40,
    "frameCounts": {"dialogue": 12, "scene": 28},
    "preset": {"id": "preset-1", "name": "Default", "version": 1},
    "prompts": {"scene": "Old scene prompt"},
    "aiModel": "claude",
    "inputMode": "subtitles",
}


def build_source_job(job_type: JobType, job_status: JobStatus) -> Job:
    return Job(
        id=SOURCE_JOB_ID,
        type=job_type,
        status=job_status,
        source_filename="Phim [vfjegxHDOwI].mp4",
        options=dict(SOURCE_OPTIONS),
    )


def build_upload(filename: str) -> VideoUpload:
    return VideoUpload(
        filename=filename, stream=BytesIO(b"film-bytes"), language="vi", preset_id=None
    )


def capture_error(error_class: type[Exception], action):
    with pytest.raises(error_class) as caught:
        action()
    return caught.value


@pytest.fixture
def repository():
    job_repository = MagicMock(spec=JobRepository)
    job_repository.add.side_effect = lambda job, outputs: job
    job_repository.find_by_id.return_value = build_source_job(
        JobType.YOUTUBE_FILM_ANALYSIS, JobStatus.FAILED
    )
    job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: "# Notes"}
    return job_repository


@pytest.fixture
def storage(tmp_path):
    job_storage = JobStorage(tmp_path, max_upload_bytes=1024)
    job_storage.images_dir(SOURCE_JOB_ID).mkdir(parents=True)
    (job_storage.images_dir(SOURCE_JOB_ID) / "moment-01-00m00s.jpg").write_bytes(b"jpg")
    return job_storage


@pytest.fixture
def preset_service():
    service = MagicMock(spec=PromptPresetService)
    service.get_job_snapshot.return_value = PRESET_SNAPSHOT
    return service


@pytest.fixture
def notify_worker():
    return MagicMock()


@pytest.fixture
def settings_service():
    service = MagicMock(spec=AppSettingService)
    service.get_input_mode.return_value = InputMode.WHOLE_VIDEO
    service.get_film_clone_input_mode.return_value = InputMode.SUBTITLES
    return service


@pytest.fixture
def step_models():
    return MagicMock(spec=AiStepModels)


@pytest.fixture
def service(repository, storage, preset_service, settings_service, step_models, notify_worker):
    intake_tools = JobIntakeTools(
        repository, preset_service, settings_service, step_models, notify_worker
    )
    return FilmAnalysisJobService(repository, storage, JobIntake(intake_tools))


@pytest.fixture
def created_upload_job(service):
    return service.create_film_analysis_job(build_upload("Phim.mkv"), 20)


@pytest.fixture
def created_prompt_keys(created_upload_job):
    return sorted(created_upload_job.options["prompts"])


@pytest.fixture
def saved_film_bytes(storage, created_upload_job):
    return storage.source_path(created_upload_job.id, "Phim.mkv").read_bytes()


@pytest.fixture(params=[9, 1001])
def max_frames_error(request, service):
    return capture_error(
        InvalidFilmAnalysisJobError,
        lambda: service.create_film_analysis_job(build_upload("Phim.mkv"), request.param),
    )


@pytest.fixture
def unsupported_file_error(service):
    return capture_error(
        InvalidUploadError, lambda: service.create_film_analysis_job(build_upload("a.txt"), None)
    )


@pytest.fixture
def rerun_job(service):
    return service.create_rerun_job(SOURCE_JOB_ID, "preset-2")


@pytest.fixture
def rerun_output_rows(repository, rerun_job):
    return [
        (output.job_id, output.kind, output.content) for output in repository.add.call_args.args[1]
    ]


@pytest.fixture
def rerun_frame_bytes(storage, rerun_job):
    return (storage.images_dir(rerun_job.id) / "moment-01-00m00s.jpg").read_bytes()


@pytest.fixture
def missing_source_error(service, repository):
    repository.find_by_id.return_value = None
    return capture_error(JobNotFoundError, lambda: service.create_rerun_job("nope", None))


@pytest.fixture
def not_film_error(service, repository):
    repository.find_by_id.return_value = build_source_job(JobType.VIDEO_TO_MARKDOWN, JobStatus.DONE)
    return capture_error(
        NotFilmAnalysisJobError, lambda: service.create_rerun_job(SOURCE_JOB_ID, None)
    )


@pytest.fixture
def running_source_error(service, repository):
    repository.find_by_id.return_value = build_source_job(
        JobType.FILM_ANALYSIS, JobStatus.PROCESSING
    )
    return capture_error(NoVideoNotesError, lambda: service.create_rerun_job(SOURCE_JOB_ID, None))


@pytest.fixture
def source_without_notes_error(service, repository):
    repository.find_outputs.return_value = {}
    return capture_error(NoVideoNotesError, lambda: service.create_rerun_job(SOURCE_JOB_ID, None))


@pytest.fixture
def unknown_rerun_preset_error(service, preset_service):
    preset_service.get_job_snapshot.side_effect = PromptPresetNotFoundError("nope")
    return capture_error(
        JobPresetNotFoundError, lambda: service.create_rerun_job(SOURCE_JOB_ID, "nope")
    )


@pytest.fixture
def job_folder_names(tmp_path, unknown_rerun_preset_error):
    return [path.name for path in tmp_path.iterdir()]


@pytest.fixture
def deleted_job(service, storage):
    service.delete_film_analysis_job(SOURCE_JOB_ID)


@pytest.fixture
def delete_other_type_error(service, repository):
    repository.find_by_id.return_value = build_source_job(JobType.VIDEO_TO_MARKDOWN, JobStatus.DONE)
    return capture_error(
        JobNotDeletableError, lambda: service.delete_film_analysis_job(SOURCE_JOB_ID)
    )


@pytest.fixture(params=[JobStatus.PENDING, JobStatus.PROCESSING])
def delete_running_error(request, service, repository):
    repository.find_by_id.return_value = build_source_job(JobType.FILM_ANALYSIS, request.param)
    return capture_error(
        JobStillRunningError, lambda: service.delete_film_analysis_job(SOURCE_JOB_ID)
    )


@pytest.fixture
def delete_missing_error(service, repository):
    repository.find_by_id.return_value = None
    return capture_error(JobNotFoundError, lambda: service.delete_film_analysis_job("nope"))


def test_create_film_analysis_job_copies_every_prompt(created_upload_job, created_prompt_keys):
    assert created_upload_job.type == JobType.FILM_ANALYSIS
    assert created_upload_job.options["maxFrames"] == 20
    assert created_upload_job.options["inputMode"] == "whole_video"
    assert created_prompt_keys == [
        "characterImage",
        "characterVoice",
        "scene",
        "videoToMarkdown",
    ]


def test_create_film_analysis_job_checks_the_moments_and_analysis_models(
    step_models, created_upload_job
):
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS)
    )


def test_create_film_analysis_job_saves_the_film_and_wakes_the_worker(
    saved_film_bytes, notify_worker
):
    assert saved_film_bytes == b"film-bytes"
    notify_worker.assert_called_once_with()


def test_create_film_analysis_job_rejects_max_frames_before_saving(
    max_frames_error, repository, preset_service
):
    assert str(max_frames_error) == "Max frames must be between 10 and 1000"
    preset_service.get_job_snapshot.assert_not_called()
    repository.add.assert_not_called()


def test_create_film_analysis_job_rejects_an_unsupported_file(unsupported_file_error):
    assert "Unsupported file type '.txt'" in str(unsupported_file_error)


def test_rerun_keeps_display_options_and_copies_three_prompts(rerun_job):
    assert rerun_job.type == JobType.FILM_ANALYSIS_RERUN
    assert rerun_job.source_filename == "Phim [vfjegxHDOwI].mp4"
    assert rerun_job.options == {
        "url": SOURCE_OPTIONS["url"],
        "videoId": "vfjegxHDOwI",
        "language": "auto",
        "captionKind": "auto",
        "frameCounts": {"dialogue": 12, "scene": 28},
        "rerunOfJobId": SOURCE_JOB_ID,
        "preset": {"id": "preset-2", "name": "Three scenes", "version": 2},
        "prompts": {
            "characterImage": DEFAULT_PRESET_PROMPTS.character_image,
            "characterVoice": DEFAULT_PRESET_PROMPTS.character_voice,
            "scene": DEFAULT_PRESET_PROMPTS.scene,
        },
    }


def test_rerun_checks_only_the_analysis_model(step_models, rerun_job):
    step_models.ensure_set_up.assert_called_once_with((AiStepGroup.FILM_ANALYSIS,))


def test_rerun_copies_the_video_notes_and_frames(rerun_job, rerun_output_rows, rerun_frame_bytes):
    assert rerun_output_rows == [(rerun_job.id, JobOutputKind.VIDEO_NOTES, "# Notes")]
    assert rerun_frame_bytes == b"jpg"


def test_rerun_raises_for_an_unknown_source(missing_source_error):
    assert str(missing_source_error) == "Job nope not found"


def test_rerun_refuses_a_job_of_another_type(not_film_error):
    assert str(not_film_error) == f"Job {SOURCE_JOB_ID} is not a film analysis"


def test_rerun_refuses_a_running_source(running_source_error, repository):
    assert str(running_source_error) == f"Job {SOURCE_JOB_ID} has no video notes to reuse"
    repository.add.assert_not_called()


def test_rerun_refuses_a_source_without_video_notes(source_without_notes_error):
    assert str(source_without_notes_error) == f"Job {SOURCE_JOB_ID} has no video notes to reuse"


def test_rerun_refuses_an_unknown_preset_before_copying(
    unknown_rerun_preset_error, job_folder_names
):
    assert str(unknown_rerun_preset_error) == "Prompt preset nope not found"
    assert job_folder_names == [SOURCE_JOB_ID]


def test_delete_removes_the_job_and_its_files(deleted_job, repository, storage):
    repository.delete.assert_called_once_with(SOURCE_JOB_ID)
    assert not storage.job_dir(SOURCE_JOB_ID).exists()


def test_delete_refuses_a_video_to_markdown_job(delete_other_type_error, repository):
    assert str(delete_other_type_error) == "Only film analysis jobs can be deleted"
    repository.delete.assert_not_called()


def test_delete_refuses_a_running_job(delete_running_error, repository):
    assert str(delete_running_error) == f"Job {SOURCE_JOB_ID} is still running"
    repository.delete.assert_not_called()


def test_delete_raises_for_an_unknown_job(delete_missing_error):
    assert str(delete_missing_error) == "Job nope not found"
