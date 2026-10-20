from io import BytesIO
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_calls import AiProviderNotSetUpError, AiStepGroup, InputMode
from app.modules.ai_models.step_models import AiStepModels
from app.modules.app_settings.service import AppSettingService
from app.modules.jobs.errors import (
    InvalidFilmAnalysisJobError,
    InvalidUploadError,
    InvalidYoutubeJobError,
    JobNotFoundError,
    JobPresetNotFoundError,
    NoZipDownloadError,
    ResultFileNotFoundError,
    ResultNotReadyError,
)
from app.modules.jobs.job_intake import JobIntake, JobIntakeTools
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import (
    JobService,
    VideoUpload,
    YoutubeJobRequest,
    YoutubeJobService,
)
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.youtube_to_markdown.video_checker import YoutubeVideoChecker
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo
from app.modules.prompt_presets.errors import PromptPresetNotFoundError
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.prompt_presets.service import PresetSnapshot, PromptPresetService

JOB_ID = "job-1"
SOURCE_FILENAME = "My clip.mp4"
YOUTUBE_VIDEO_ID = "vfjegxHDOwI"
YOUTUBE_LINK = f"https://youtu.be/{YOUTUBE_VIDEO_ID}"
PRESET_ID = "preset-1"
PRESET_SNAPSHOT = PresetSnapshot(
    preset_id=PRESET_ID, name="Anime", version=3, prompts=DEFAULT_PRESET_PROMPTS
)
PRESET_OPTION = {"id": PRESET_ID, "name": "Anime", "version": 3}
AI_OPTIONS = {"inputMode": "whole_video"}
ALL_PROMPTS_OPTION = {
    "videoToMarkdown": DEFAULT_PRESET_PROMPTS.video_to_markdown,
    "speakersAndSounds": DEFAULT_PRESET_PROMPTS.speakers_and_sounds,
    "characterImage": DEFAULT_PRESET_PROMPTS.character_image,
    "characterVoice": DEFAULT_PRESET_PROMPTS.character_voice,
    "scene": DEFAULT_PRESET_PROMPTS.scene,
}


def build_job(job_status: JobStatus, job_type: JobType = JobType.VIDEO_TO_MARKDOWN) -> Job:
    return Job(
        id=JOB_ID,
        type=job_type,
        status=job_status,
        source_filename=SOURCE_FILENAME,
        options={"language": "auto"},
    )


def build_upload(filename: str, language: str, preset_id: str | None = None) -> VideoUpload:
    return VideoUpload(
        filename=filename, stream=BytesIO(b"video-bytes"), language=language, preset_id=preset_id
    )


def capture_error(error_class: type[Exception], action):
    with pytest.raises(error_class) as caught:
        action()
    return caught.value


@pytest.fixture
def repository():
    job_repository = MagicMock(spec=JobRepository)
    job_repository.add.side_effect = lambda job, outputs: job
    job_repository.find_by_id.return_value = None
    job_repository.find_outputs.return_value = {}
    return job_repository


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=1024)


@pytest.fixture
def notify_worker():
    return MagicMock()


@pytest.fixture
def preset_service():
    service = MagicMock(spec=PromptPresetService)
    service.get_job_snapshot.return_value = PRESET_SNAPSHOT
    return service


@pytest.fixture
def settings_service():
    service = MagicMock(spec=AppSettingService)
    service.get_input_mode.return_value = InputMode.WHOLE_VIDEO
    service.get_film_analysis_input_mode.return_value = InputMode.SUBTITLES
    service.get_film_clone_input_mode.return_value = InputMode.SUBTITLES
    return service


@pytest.fixture
def step_models():
    return MagicMock(spec=AiStepModels)


@pytest.fixture
def intake(repository, preset_service, settings_service, step_models, notify_worker):
    return JobIntake(
        JobIntakeTools(repository, preset_service, settings_service, step_models, notify_worker)
    )


def build_video_info(title: str) -> VideoInfo:
    return VideoInfo(
        video_id=YOUTUBE_VIDEO_ID,
        title=title,
        duration_ms=670_000,
        live_status="not_live",
        metadata_language="vi",
        manual_caption_codes=[],
        auto_caption_codes=["vi-orig"],
    )


@pytest.fixture
def service(repository, storage, intake):
    return JobService(repository, storage, intake)


@pytest.fixture
def done_job(repository, storage):
    repository.find_by_id.return_value = build_job(JobStatus.DONE)
    storage.images_dir(JOB_ID).mkdir(parents=True)
    storage.markdown_path(JOB_ID, SOURCE_FILENAME).write_text("# Result\n", encoding="utf-8")
    (storage.images_dir(JOB_ID) / "moment-01-00m00s.jpg").write_bytes(b"jpg")
    storage.source_path(JOB_ID, SOURCE_FILENAME).write_bytes(b"video")
    return repository.find_by_id.return_value


@pytest.fixture
def pending_job(repository):
    repository.find_by_id.return_value = build_job(JobStatus.PENDING)
    return repository.find_by_id.return_value


@pytest.fixture
def created_job(service):
    return service.create_video_to_markdown_job(build_upload("clip.MP4", "auto", PRESET_ID))


@pytest.fixture
def unknown_preset_error(service, preset_service):
    preset_service.get_job_snapshot.side_effect = PromptPresetNotFoundError("nope")
    return capture_error(
        JobPresetNotFoundError,
        lambda: service.create_video_to_markdown_job(build_upload("clip.mp4", "auto", "nope")),
    )


@pytest.fixture
def gemini_without_key_error(service, step_models):
    step_models.ensure_set_up.side_effect = AiProviderNotSetUpError("Google AI (Gemini, Veo)")
    return capture_error(
        AiProviderNotSetUpError,
        lambda: service.create_video_to_markdown_job(build_upload("clip.mp4", "auto")),
    )


@pytest.fixture
def youtube_gemini_without_key_error(youtube_service, step_models):
    step_models.ensure_set_up.side_effect = AiProviderNotSetUpError("Google AI (Gemini, Veo)")
    return capture_error(
        AiProviderNotSetUpError,
        lambda: youtube_service.create_youtube_film_analysis_job(build_youtube_request("vi"), 40),
    )


@pytest.fixture
def saved_source_bytes(storage, created_job):
    return storage.source_path(created_job.id, "clip.MP4").read_bytes()


@pytest.fixture
def unsupported_extension_error(service):
    upload = build_upload("notes.txt", "auto")
    return capture_error(InvalidUploadError, lambda: service.create_video_to_markdown_job(upload))


@pytest.fixture
def invalid_language_error(service):
    upload = build_upload("clip.mp4", "Vietnamese")
    return capture_error(InvalidUploadError, lambda: service.create_video_to_markdown_job(upload))


@pytest.fixture
def missing_job_error(service):
    return capture_error(JobNotFoundError, lambda: service.get_job("missing"))


@pytest.fixture
def recent_jobs(service, repository):
    repository.find_recent.return_value = [build_job(JobStatus.DONE)]
    return service.list_recent_jobs(10, [JobType.VIDEO_TO_MARKDOWN])


@pytest.fixture
def pending_detail(service, pending_job):
    return service.get_job_detail(JOB_ID)


@pytest.fixture
def done_detail(service, done_job):
    return service.get_job_detail(JOB_ID)


@pytest.fixture
def film_job_with_notes(repository, storage):
    repository.find_by_id.return_value = build_job(JobStatus.FAILED, JobType.FILM_ANALYSIS)
    repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: "# Notes"}
    storage.images_dir(JOB_ID).mkdir(parents=True)
    (storage.images_dir(JOB_ID) / "moment-01-00m00s.jpg").write_bytes(b"jpg")
    return repository.find_by_id.return_value


@pytest.fixture
def film_detail(service, film_job_with_notes):
    return service.get_job_detail(JOB_ID)


@pytest.fixture
def film_image_path(service, storage, film_job_with_notes):
    return service.resolve_result_file(JOB_ID, "images/moment-01-00m00s.jpg")


@pytest.fixture
def film_without_notes_error(service, repository):
    repository.find_by_id.return_value = build_job(JobStatus.PROCESSING, JobType.FILM_ANALYSIS)
    return capture_error(
        ResultNotReadyError,
        lambda: service.resolve_result_file(JOB_ID, "images/moment-01-00m00s.jpg"),
    )


@pytest.fixture
def film_zip_error(service, film_job_with_notes):
    return capture_error(NoZipDownloadError, lambda: service.get_result_archive(JOB_ID))


@pytest.fixture
def resolved_image_path(service, storage, done_job):
    return service.resolve_result_file(JOB_ID, "images/moment-01-00m00s.jpg")


@pytest.fixture
def traversal_error(service, done_job):
    return capture_error(
        ResultFileNotFoundError, lambda: service.resolve_result_file(JOB_ID, "../source.mp4")
    )


@pytest.fixture
def missing_file_error(service, done_job):
    return capture_error(
        ResultFileNotFoundError, lambda: service.resolve_result_file(JOB_ID, "images/nope.jpg")
    )


@pytest.fixture
def not_ready_error(service, pending_job):
    return capture_error(ResultNotReadyError, lambda: service.get_result_archive(JOB_ID))


@pytest.fixture
def result_archive(service, done_job):
    return service.get_result_archive(JOB_ID)


@pytest.fixture
def video_checker():
    checker = MagicMock(spec=YoutubeVideoChecker)
    checker.fetch_convertible_video.return_value = build_video_info("30 Năm Kinh Nghiệm Đầu Tư")
    return checker


@pytest.fixture
def youtube_service(video_checker, intake):
    return YoutubeJobService(video_checker, intake)


def build_youtube_request(language: str) -> YoutubeJobRequest:
    return YoutubeJobRequest(link=YOUTUBE_LINK, language=language, preset_id=None)


@pytest.fixture
def created_youtube_job(youtube_service):
    return youtube_service.create_youtube_to_markdown_job(build_youtube_request("vi"))


@pytest.fixture
def long_title_job(youtube_service, video_checker):
    video_checker.fetch_convertible_video.return_value = build_video_info("x" * 300)
    return youtube_service.create_youtube_to_markdown_job(build_youtube_request("auto"))


@pytest.fixture
def youtube_invalid_language_error(youtube_service):
    return capture_error(
        InvalidYoutubeJobError,
        lambda: youtube_service.create_youtube_to_markdown_job(build_youtube_request("vietnamese")),
    )


@pytest.fixture
def youtube_film_job(youtube_service):
    return youtube_service.create_youtube_film_analysis_job(build_youtube_request("vi"), 60)


@pytest.fixture
def youtube_film_job_with_default_frames(youtube_service):
    return youtube_service.create_youtube_film_analysis_job(build_youtube_request("vi"), None)


@pytest.fixture
def youtube_whole_video_film_job(youtube_service, settings_service):
    settings_service.get_film_analysis_input_mode.return_value = InputMode.WHOLE_VIDEO
    return youtube_service.create_youtube_film_analysis_job(build_youtube_request("vi"), 60)


@pytest.fixture
def youtube_full_video_film_job(youtube_service, settings_service):
    settings_service.get_film_analysis_input_mode.return_value = InputMode.FULL_VIDEO
    return youtube_service.create_youtube_film_analysis_job(build_youtube_request("vi"), 5)


@pytest.fixture(params=[9, 1001])
def youtube_film_max_frames_error(request, youtube_service):
    return capture_error(
        InvalidFilmAnalysisJobError,
        lambda: youtube_service.create_youtube_film_analysis_job(
            build_youtube_request("vi"), request.param
        ),
    )


def test_create_video_to_markdown_job_queues_a_pending_job(created_job):
    assert created_job.status == JobStatus.PENDING
    assert created_job.type == JobType.VIDEO_TO_MARKDOWN
    assert created_job.options == {
        "language": "auto",
        "preset": PRESET_OPTION,
        "prompts": {"videoToMarkdown": DEFAULT_PRESET_PROMPTS.video_to_markdown},
        **AI_OPTIONS,
    }


def test_create_video_to_markdown_job_checks_the_moments_model(step_models, created_job):
    step_models.ensure_set_up.assert_called_once_with((AiStepGroup.MOMENTS,))


def test_create_video_to_markdown_job_refuses_gemini_without_a_key_before_saving(
    gemini_without_key_error, repository, storage
):
    assert str(gemini_without_key_error) == "Google AI (Gemini, Veo) is not set up — open Settings"
    repository.add.assert_not_called()
    assert list(storage.job_dir(JOB_ID).parent.iterdir()) == []


def test_create_youtube_film_analysis_job_refuses_gemini_without_a_key_before_youtube(
    youtube_gemini_without_key_error, video_checker, repository
):
    assert (
        str(youtube_gemini_without_key_error)
        == "Google AI (Gemini, Veo) is not set up — open Settings"
    )
    video_checker.fetch_convertible_video.assert_not_called()
    repository.add.assert_not_called()


def test_create_video_to_markdown_job_snapshots_the_chosen_preset(preset_service, created_job):
    preset_service.get_job_snapshot.assert_called_once_with(PRESET_ID)


def test_create_video_to_markdown_job_rejects_an_unknown_preset(
    unknown_preset_error, repository, storage
):
    assert str(unknown_preset_error) == "Prompt preset nope not found"
    repository.add.assert_not_called()
    assert not storage.job_dir(JOB_ID).exists()


def test_create_video_to_markdown_job_saves_the_uploaded_video(saved_source_bytes):
    assert saved_source_bytes == b"video-bytes"


def test_create_video_to_markdown_job_wakes_the_worker(notify_worker, created_job):
    notify_worker.assert_called_once_with()


def test_create_video_to_markdown_job_rejects_unsupported_extension(
    unsupported_extension_error, repository
):
    assert "Unsupported file type '.txt'" in str(unsupported_extension_error)
    repository.add.assert_not_called()


def test_create_video_to_markdown_job_rejects_invalid_language(invalid_language_error):
    assert "Invalid language 'Vietnamese'" in str(invalid_language_error)


def test_list_recent_jobs_reads_the_requested_count(recent_jobs, repository):
    assert [job.id for job in recent_jobs] == [JOB_ID]
    repository.find_recent.assert_called_once_with(10, [JobType.VIDEO_TO_MARKDOWN])


def test_get_job_raises_when_missing(missing_job_error):
    assert missing_job_error.job_id == "missing"


def test_get_job_detail_has_no_markdown_before_done(pending_detail):
    assert pending_detail.markdown is None


def test_get_job_detail_includes_markdown_when_done(done_detail):
    assert done_detail.markdown == "# Result\n"


def test_get_job_detail_returns_outputs_of_a_film_analysis(film_detail):
    assert film_detail.outputs == {JobOutputKind.VIDEO_NOTES: "# Notes"}
    assert film_detail.markdown is None


def test_resolve_result_file_serves_film_frames_once_video_notes_exist(film_image_path, storage):
    assert film_image_path == (storage.images_dir(JOB_ID) / "moment-01-00m00s.jpg").resolve()


def test_resolve_result_file_refuses_film_frames_before_video_notes(film_without_notes_error):
    assert film_without_notes_error.job_id == JOB_ID


def test_get_result_archive_refuses_a_film_analysis(film_zip_error):
    assert str(film_zip_error) == f"Job {JOB_ID} has no zip download"


def test_resolve_result_file_returns_file_inside_output(resolved_image_path, storage):
    assert resolved_image_path == (storage.images_dir(JOB_ID) / "moment-01-00m00s.jpg").resolve()


def test_resolve_result_file_rejects_paths_outside_output(traversal_error):
    assert traversal_error.relative_path == "../source.mp4"


def test_resolve_result_file_rejects_missing_file(missing_file_error):
    assert missing_file_error.relative_path == "images/nope.jpg"


def test_get_result_archive_requires_a_finished_job(not_ready_error):
    assert not_ready_error.job_id == JOB_ID


def test_get_result_archive_names_download_after_the_video(result_archive, storage):
    assert result_archive.download_name == "My clip.zip"
    assert result_archive.path == storage.archive_path(JOB_ID)


def test_create_youtube_to_markdown_job_queues_a_pending_youtube_job(created_youtube_job):
    assert created_youtube_job.status == JobStatus.PENDING
    assert created_youtube_job.type == JobType.YOUTUBE_TO_MARKDOWN


def test_create_youtube_to_markdown_job_stores_the_canonical_link(created_youtube_job):
    assert created_youtube_job.options == {
        "url": f"https://www.youtube.com/watch?v={YOUTUBE_VIDEO_ID}",
        "videoId": YOUTUBE_VIDEO_ID,
        "language": "vi",
        "preset": PRESET_OPTION,
        "prompts": {"videoToMarkdown": DEFAULT_PRESET_PROMPTS.video_to_markdown},
        **AI_OPTIONS,
    }


def test_create_youtube_to_markdown_job_names_the_job_after_the_video(created_youtube_job):
    assert created_youtube_job.source_filename == (
        f"30 Năm Kinh Nghiệm Đầu Tư [{YOUTUBE_VIDEO_ID}].mp4"
    )


def test_create_youtube_to_markdown_job_checks_the_link(video_checker, created_youtube_job):
    video_checker.fetch_convertible_video.assert_called_once_with(YOUTUBE_LINK)


def test_create_youtube_to_markdown_job_wakes_the_worker(notify_worker, created_youtube_job):
    notify_worker.assert_called_once_with()


def test_create_youtube_to_markdown_job_shortens_a_long_title(long_title_job):
    assert len(long_title_job.source_filename) == 255
    assert long_title_job.source_filename.endswith(f"x [{YOUTUBE_VIDEO_ID}].mp4")


def test_create_youtube_to_markdown_job_rejects_invalid_language_before_calling_youtube(
    youtube_invalid_language_error, video_checker, repository
):
    assert str(youtube_invalid_language_error) == "Invalid language 'vietnamese'"
    video_checker.fetch_convertible_video.assert_not_called()
    repository.add.assert_not_called()


def test_create_youtube_film_analysis_job_copies_every_prompt(youtube_film_job):
    assert youtube_film_job.type == JobType.YOUTUBE_FILM_ANALYSIS
    assert youtube_film_job.options == {
        "url": f"https://www.youtube.com/watch?v={YOUTUBE_VIDEO_ID}",
        "videoId": YOUTUBE_VIDEO_ID,
        "language": "vi",
        "maxFrames": 60,
        "preset": PRESET_OPTION,
        "prompts": ALL_PROMPTS_OPTION,
        "inputMode": "subtitles",
    }


def test_create_youtube_film_analysis_job_checks_the_moments_and_analysis_models(
    step_models, youtube_film_job
):
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS), ()
    )


def test_create_youtube_film_analysis_job_copies_the_film_analysis_input_mode(
    youtube_whole_video_film_job, step_models
):
    assert youtube_whole_video_film_job.options["inputMode"] == "whole_video"
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_ANALYSIS, AiStepGroup.AUDIO),
        (AiStepGroup.AUDIO,),
    )


def test_create_youtube_film_analysis_job_in_full_video_has_no_max_frames(
    youtube_full_video_film_job, step_models
):
    assert youtube_full_video_film_job.options["inputMode"] == "full_video"
    assert "maxFrames" not in youtube_full_video_film_job.options
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.FILM_ANALYSIS,), (AiStepGroup.FILM_ANALYSIS,)
    )


def test_create_youtube_film_analysis_job_defaults_to_1000_frames(
    youtube_film_job_with_default_frames,
):
    assert youtube_film_job_with_default_frames.options["maxFrames"] == 1000


def test_create_youtube_film_analysis_job_rejects_max_frames_out_of_range(
    youtube_film_max_frames_error, video_checker, preset_service
):
    assert str(youtube_film_max_frames_error) == "Max frames must be between 10 and 1000"
    video_checker.fetch_convertible_video.assert_not_called()
    preset_service.get_job_snapshot.assert_not_called()


@pytest.fixture
def film_clone_ai_options(intake):
    return intake.resolve_film_clone_ai_options((AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE))


@pytest.fixture
def whole_video_film_clone_ai_options(intake, settings_service):
    settings_service.get_film_clone_input_mode.return_value = InputMode.WHOLE_VIDEO
    return intake.resolve_film_clone_ai_options((AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE))


def test_a_film_clone_job_takes_the_film_clone_input_mode(film_clone_ai_options, step_models):
    assert film_clone_ai_options == {"inputMode": "subtitles"}
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE), ()
    )


def test_a_film_clone_job_in_whole_video_also_checks_a_google_audio_model(
    whole_video_film_clone_ai_options, step_models
):
    assert whole_video_film_clone_ai_options == {"inputMode": "whole_video"}
    step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE, AiStepGroup.AUDIO), (AiStepGroup.AUDIO,)
    )
