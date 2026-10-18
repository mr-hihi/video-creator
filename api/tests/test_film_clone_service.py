import io
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_calls import AiModelChoice, AiStepGroup
from app.modules.app_settings.service import AppSettingService
from app.modules.app_settings.setting_rules import ScriptLanguage
from app.modules.film_clones.clone_access import CloneAccess
from app.modules.film_clones.clone_actions import (
    CloneActionService,
    CloneActionTools,
    LocalizationChoices,
)
from app.modules.film_clones.clone_activity import AiActivity, AiActivityTracker
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_generation import CloneImageQueue
from app.modules.film_clones.clone_steps import CloneSceneImageCheck
from app.modules.film_clones.errors import (
    CloneConflictError,
    FilmCloneNotFoundError,
    InvalidCloneRequestError,
)
from app.modules.film_clones.models import (
    AssetKind,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
    FrameKind,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.film_clones.service import (
    CloneOptions,
    FilmCloneService,
    FilmCloneServiceTools,
)
from app.modules.jobs.job_intake import JobIntake
from app.modules.jobs.models import JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import VideoUpload, YoutubeJobRequest
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.youtube_to_markdown.video_checker import YoutubeVideoChecker
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo
from app.modules.media_generation.models import GenerationKind, GenerationRequest
from app.modules.media_generation.service import GenerationService
from app.modules.providers.provider_catalog import ProviderId

CLONE_ID = "clone-1"
CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
ACTIVITY_STARTED_AT = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)
JOB_ID = "job-1"
PROMPT_OPTIONS = {
    "preset": {"id": "p-1", "name": "Default", "version": 3},
    "prompts": {
        "videoToMarkdown": "VTM",
        "cloneAssets": "Assets",
        "cloneShots": "Shots",
        "cloneLocalization": "Localize",
        "cloneScript": "Script",
    },
}
VIDEO_NOTES = "# T\n\n> Source: a.mp4 · Duration: 01:00 · Language: ja\n"


def build_clone(status: CloneStatus, step: CloneStep, **overrides) -> FilmClone:
    fields = {
        "id": CLONE_ID,
        "job_id": JOB_ID,
        "status": status,
        "step": step,
        "target_country": "jp",
        "change_appearance": False,
        "change_costume": False,
        "change_setting": False,
        "preset": {},
        "prompts": {},
    }
    return FilmClone(**{**fields, **overrides})


def build_asset(name: str, **overrides) -> CloneAsset:
    fields = {
        "id": f"asset-{name}",
        "clone_id": CLONE_ID,
        "kind": AssetKind.PROP,
        "name": name,
        "changed": False,
        "reference_status": CloneImageStatus.NONE,
        "reference_path": None,
        "localized_name": None,
    }
    return CloneAsset(**{**fields, **overrides})


def build_scene(scene_id: str, image_status: CloneImageStatus, image_path=None) -> CloneScene:
    return CloneScene(
        id=scene_id,
        clone_id=CLONE_ID,
        shot_id=f"shot-{scene_id}",
        position=0,
        image_status=image_status,
        image_path=image_path,
    )


def build_parts(tmp_path, clone: FilmClone | None = None, open_requests=()):
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_by_id.return_value = clone
    repository.add_with_job.side_effect = lambda job, added_clone: added_clone
    job_repository = MagicMock(spec=JobRepository)
    job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: VIDEO_NOTES}
    generation_service = MagicMock(spec=GenerationService)
    generation_service.find_open_for_clone.return_value = list(open_requests)
    intake = MagicMock(spec=JobIntake)
    intake.resolve_prompt_options.return_value = PROMPT_OPTIONS
    intake.resolve_film_clone_ai_options.return_value = {"inputMode": "whole_video"}
    app_settings = MagicMock(spec=AppSettingService)
    app_settings.get_script_language.return_value = ScriptLanguage.FOLLOW_TARGET_COUNTRY
    files = MagicMock(spec=CloneFiles)
    image_queue = MagicMock(spec=CloneImageQueue)
    scene_check = MagicMock(spec=CloneSceneImageCheck)
    video_checker = MagicMock(spec=YoutubeVideoChecker)
    video_checker.fetch_convertible_video.return_value = VideoInfo(
        video_id="vfjegxHDOwI",
        title="Palace Escape",
        duration_ms=60000,
        live_status="not_live",
        metadata_language="ko",
        manual_caption_codes=["ko"],
        auto_caption_codes=[],
    )
    notify_worker = MagicMock()
    job_storage = MagicMock(spec=JobStorage)
    ai_activity = AiActivityTracker(lambda: ACTIVITY_STARTED_AT)
    access = CloneAccess(repository, generation_service)
    clones = FilmCloneService(
        FilmCloneServiceTools(
            repository=repository,
            job_repository=job_repository,
            job_storage=job_storage,
            files=files,
            intake=intake,
            video_checker=video_checker,
            generation_service=generation_service,
            notify_worker=notify_worker,
            ai_activity=ai_activity,
        ),
        access,
    )
    actions = CloneActionService(
        CloneActionTools(
            repository=repository,
            job_repository=job_repository,
            files=files,
            app_setting_service=app_settings,
            image_queue=image_queue,
            scene_image_check=scene_check,
            notify_worker=notify_worker,
        ),
        access,
    )
    return SimpleNamespace(
        clones=clones,
        actions=actions,
        repository=repository,
        job_storage=job_storage,
        generation_service=generation_service,
        app_settings=app_settings,
        files=files,
        image_queue=image_queue,
        scene_check=scene_check,
        notify_worker=notify_worker,
        ai_activity=ai_activity,
        intake=intake,
    )


def capture(error_class, call):
    with pytest.raises(error_class) as caught:
        call()
    return caught.value


def choices(target_country="jp", target_setting=None, **flags) -> LocalizationChoices:
    return LocalizationChoices(
        target_country=target_country,
        target_setting=target_setting,
        change_appearance=flags.get("appearance", False),
        change_costume=flags.get("costume", False),
        change_setting=flags.get("setting", False),
    )


def clone_options(
    max_frames=None, should_run_automatically=False, localization=None
) -> CloneOptions:
    return CloneOptions(
        max_frames=max_frames,
        should_run_automatically=should_run_automatically,
        choices=localization or choices("jp", appearance=True),
    )


def upload(filename="escape.mp4", language="vi") -> VideoUpload:
    return VideoUpload(
        filename=filename, stream=io.BytesIO(b"v"), language=language, preset_id=None
    )


@pytest.fixture
def created(tmp_path):
    parts = build_parts(tmp_path)
    summary = parts.clones.create_from_upload(upload(), clone_options(30))
    job, clone = parts.repository.add_with_job.call_args.args
    return SimpleNamespace(parts=parts, summary=summary, job=job, clone=clone)


@pytest.fixture
def created_automatically(tmp_path):
    parts = build_parts(tmp_path)
    parts.clones.create_from_upload(
        upload(),
        clone_options(30, True, choices("jp", "a modern Tokyo office district", appearance=True)),
    )
    return parts.repository.add_with_job.call_args.args[1]


@pytest.fixture(
    params=[
        (choices("xx"), "Unknown country 'xx'"),
        (
            choices(None, costume=True),
            "Pick a target country to change appearance, costume or setting",
        ),
    ]
)
def automatic_choices_error(request, tmp_path):
    localization, expected = request.param
    parts = build_parts(tmp_path)
    error = capture(
        InvalidCloneRequestError,
        lambda: parts.clones.create_from_upload(upload(), clone_options(30, True, localization)),
    )
    return SimpleNamespace(error=error, expected=expected, parts=parts)


@pytest.fixture
def created_from_youtube(tmp_path):
    parts = build_parts(tmp_path)
    parts.clones.create_from_youtube(
        YoutubeJobRequest(link="https://youtu.be/vfjegxHDOwI", language="auto", preset_id=None),
        clone_options(),
    )
    return parts.repository.add_with_job.call_args.args[0]


@pytest.fixture(params=[9, 1001])
def max_frames_error(request, tmp_path):
    parts = build_parts(tmp_path)
    error = capture(
        InvalidCloneRequestError,
        lambda: parts.clones.create_from_upload(upload(), clone_options(request.param)),
    )
    return SimpleNamespace(error=error, parts=parts)


@pytest.fixture
def running_delete_error(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.RUNNING, CloneStep.ANALYZING))
    return capture(CloneConflictError, lambda: parts.clones.delete(CLONE_ID))


@pytest.fixture
def busy_delete_error(tmp_path):
    parts = build_parts(
        tmp_path,
        build_clone(CloneStatus.DONE, CloneStep.GENERATING_SCENE_IMAGES),
        [GenerationRequest(id="r-1", kind=GenerationKind.CLONE_SCENE_IMAGE)],
    )
    return capture(CloneConflictError, lambda: parts.clones.delete(CLONE_ID))


@pytest.fixture
def deleted(tmp_path):
    clone = build_clone(CloneStatus.FAILED, CloneStep.ANALYZING)
    parts = build_parts(tmp_path, clone)
    parts.clones.delete(CLONE_ID)
    return SimpleNamespace(parts=parts, clone=clone)


@pytest.fixture
def detail_while_ai_runs(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.RUNNING, CloneStep.ANALYZING_SHOTS))
    parts.ai_activity.start(CLONE_ID, CLAUDE_CHOICE)
    return parts.clones.get_detail(CLONE_ID)


@pytest.fixture
def missing_clone_error(tmp_path):
    parts = build_parts(tmp_path, None)
    return capture(FilmCloneNotFoundError, lambda: parts.clones.get_detail("nope"))


def localize(tmp_path, localization: LocalizationChoices, clone: FilmClone | None = None):
    parts = build_parts(
        tmp_path, clone or build_clone(CloneStatus.WAITING, CloneStep.CHOOSING_LOCALIZATION)
    )
    parts.actions.localize(CLONE_ID, localization)
    return SimpleNamespace(parts=parts, values=parts.repository.update_clone.call_args.args[1])


@pytest.fixture
def localized_with_flag(tmp_path):
    return localize(tmp_path, choices("kr", appearance=True))


@pytest.fixture
def localized_without_flag(tmp_path):
    return localize(tmp_path, choices(None))


@pytest.fixture
def localized_with_setting_only(tmp_path):
    return localize(tmp_path, choices(None, "  a modern Western city  "))


@pytest.fixture
def localized_with_blank_setting(tmp_path):
    return localize(tmp_path, choices("us", "   ", setting=True))


@pytest.fixture
def localized_with_long_setting(tmp_path):
    return localize(tmp_path, choices("us", "a" * 20_000, setting=True))


@pytest.fixture(
    params=[
        (ScriptLanguage.FOLLOW_TARGET_COUNTRY, "kr", "ko"),
        (ScriptLanguage.ENGLISH, "jp", "en"),
        (ScriptLanguage.ENGLISH, None, "en"),
        (ScriptLanguage.FOLLOW_TARGET_COUNTRY, None, "ja"),
    ]
)
def script_language(request, tmp_path):
    setting, target_country, expected = request.param
    parts = build_parts(tmp_path, build_clone(CloneStatus.WAITING, CloneStep.CHOOSING_LOCALIZATION))
    parts.app_settings.get_script_language.return_value = setting
    parts.actions.localize(CLONE_ID, choices(target_country))
    actual = parts.repository.update_clone.call_args.args[1]["script_language"]
    return SimpleNamespace(actual=actual, expected=expected)


@pytest.fixture(
    params=[
        (choices("xx"), "Unknown country 'xx'"),
        (
            choices(None, costume=True),
            "Pick a target country to change appearance, costume or setting",
        ),
    ]
)
def localization_error(request, tmp_path):
    localization, expected = request.param
    parts = build_parts(tmp_path, build_clone(CloneStatus.WAITING, CloneStep.CHOOSING_LOCALIZATION))
    error = capture(
        InvalidCloneRequestError, lambda: parts.actions.localize(CLONE_ID, localization)
    )
    return SimpleNamespace(error=error, expected=expected)


@pytest.fixture
def wrong_step_error(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.WAITING, CloneStep.REVIEWING))
    return capture(CloneConflictError, lambda: parts.actions.localize(CLONE_ID, choices()))


@pytest.fixture
def missing_references_error(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.WAITING, CloneStep.REVIEWING))
    parts.repository.find_assets.return_value = [
        build_asset("Palace", changed=True, reference_status=CloneImageStatus.DONE),
        build_asset("Fan", changed=True, localized_name="Fan"),
        build_asset("Bowl"),
    ]
    return capture(CloneConflictError, lambda: parts.actions.write_script(CLONE_ID))


@pytest.fixture
def script_started(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.WAITING, CloneStep.REVIEWING))
    parts.repository.find_assets.return_value = [
        build_asset("Palace", changed=True, reference_status=CloneImageStatus.DONE)
    ]
    parts.actions.write_script(CLONE_ID)
    return parts


@pytest.fixture
def resumed_images(tmp_path):
    clone = build_clone(CloneStatus.FAILED, CloneStep.GENERATING_SCENE_IMAGES)
    parts = build_parts(tmp_path, clone)
    parts.repository.find_shots.return_value = [
        CloneShot(
            id=f"shot-{scene_id}", position=0, frame="images/f.jpg", frame_kind=FrameKind.SCENE
        )
        for scene_id in ("s-1", "s-2", "s-3")
    ]
    parts.repository.find_scenes.return_value = [
        build_scene("s-1", CloneImageStatus.DONE, "clone-1/scenes/s-1.png"),
        build_scene("s-2", CloneImageStatus.FAILED),
        build_scene("s-3", CloneImageStatus.NONE),
    ]
    parts.actions.resume(CLONE_ID)
    return parts


@pytest.fixture
def resumed_script(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.FAILED, CloneStep.WRITING_SCRIPT))
    parts.actions.resume(CLONE_ID)
    return parts


@pytest.fixture(params=[CloneStep.EXTRACTING_ASSETS, CloneStep.ANALYZING_SHOTS])
def resumed_analysis(request, tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.FAILED, request.param))
    parts.actions.resume(CLONE_ID)
    return parts


@pytest.fixture
def analysis_relocalize_error(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.FAILED, CloneStep.EXTRACTING_ASSETS))
    return capture(CloneConflictError, lambda: parts.actions.relocalize(CLONE_ID))


@pytest.fixture
def analyzing_resume_error(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.FAILED, CloneStep.ANALYZING))
    return capture(CloneConflictError, lambda: parts.actions.resume(CLONE_ID))


@pytest.fixture
def busy_relocalize_error(tmp_path):
    parts = build_parts(
        tmp_path,
        build_clone(CloneStatus.FAILED, CloneStep.GENERATING_SCENE_IMAGES),
        [GenerationRequest(id="r-1", kind=GenerationKind.CLONE_SCENE_IMAGE)],
    )
    return capture(CloneConflictError, lambda: parts.actions.relocalize(CLONE_ID))


@pytest.fixture
def relocalized(tmp_path):
    parts = build_parts(tmp_path, build_clone(CloneStatus.DONE, CloneStep.GENERATING_SCENE_IMAGES))
    parts.repository.find_scenes.return_value = [
        build_scene("s-1", CloneImageStatus.DONE, "clone-1/scenes/s-1.png")
    ]
    parts.repository.find_assets.return_value = [
        build_asset("Fan", changed=True, reference_path="clone-1/references/asset-Fan.png")
    ]
    parts.actions.relocalize(CLONE_ID)
    return parts


def test_create_stores_job_and_clone_together(created):
    assert created.job.type is JobType.FILM_CLONE
    assert created.job.status is JobStatus.PENDING
    assert created.clone.job_id == created.job.id
    assert (created.clone.status, created.clone.step) == (CloneStatus.RUNNING, CloneStep.ANALYZING)
    created.parts.notify_worker.assert_called_once_with()


def test_create_splits_prompts_between_job_and_clone(created):
    assert created.job.options["maxFrames"] == 30
    assert created.job.options["cloneId"] == created.clone.id
    assert created.job.options["inputMode"] == "whole_video"
    assert created.job.options["prompts"] == {
        "videoToMarkdown": "VTM",
        "cloneAssets": "Assets",
        "cloneShots": "Shots",
    }
    assert created.clone.prompts == {"cloneLocalization": "Localize", "cloneScript": "Script"}
    assert created.clone.preset == {"id": "p-1", "name": "Default", "version": 3}


def test_step_by_step_clone_ignores_the_choices(created):
    clone = created.clone
    assert clone.should_run_automatically is False
    assert clone.target_country is None
    assert clone.target_setting is None
    assert (clone.change_appearance, clone.change_costume, clone.change_setting) == (
        False,
        False,
        False,
    )


def test_automatic_clone_stores_its_choices(created_automatically):
    clone = created_automatically
    assert clone.should_run_automatically is True
    assert clone.target_country == "jp"
    assert clone.target_setting == "a modern Tokyo office district"
    assert (clone.change_appearance, clone.change_costume, clone.change_setting) == (
        True,
        False,
        False,
    )


def test_automatic_clone_with_wrong_choices_is_refused(automatic_choices_error):
    assert str(automatic_choices_error.error) == automatic_choices_error.expected
    automatic_choices_error.parts.job_storage.save_source.assert_not_called()


def test_youtube_clone_uses_the_youtube_job_type(created_from_youtube):
    assert created_from_youtube.type is JobType.YOUTUBE_FILM_CLONE
    assert created_from_youtube.options["maxFrames"] == 1000
    assert created_from_youtube.options["videoId"] == "vfjegxHDOwI"
    assert created_from_youtube.options["inputMode"] == "whole_video"


def test_a_clone_checks_the_moments_and_film_clone_models(created):
    created.parts.intake.resolve_film_clone_ai_options.assert_called_once_with(
        (AiStepGroup.MOMENTS, AiStepGroup.FILM_CLONE)
    )


def test_max_frames_outside_10_to_1000_is_refused(max_frames_error):
    assert str(max_frames_error.error) == "Max frames must be between 10 and 1000"
    max_frames_error.parts.job_storage.save_source.assert_not_called()


def test_delete_refuses_a_running_clone(running_delete_error):
    assert str(running_delete_error) == "Film clone clone-1 is still running"


def test_delete_refuses_while_images_generate(busy_delete_error):
    assert str(busy_delete_error) == "Film clone clone-1 is still running"


def test_delete_removes_requests_rows_and_files(deleted):
    deleted.parts.generation_service.delete_for_clone.assert_called_once_with(CLONE_ID)
    deleted.parts.repository.delete_with_job.assert_called_once_with(deleted.clone)
    deleted.parts.job_storage.delete_job_files.assert_called_once_with(JOB_ID)
    deleted.parts.files.delete_clone_files.assert_called_once_with(CLONE_ID)


def test_unknown_clone_is_not_found(missing_clone_error):
    assert str(missing_clone_error) == "Film clone nope not found"


def test_localize_with_a_flag_starts_proposing(localized_with_flag):
    assert localized_with_flag.values["status"] is CloneStatus.RUNNING
    assert localized_with_flag.values["step"] is CloneStep.PROPOSING
    assert localized_with_flag.values["target_country"] == "kr"
    localized_with_flag.parts.notify_worker.assert_called_once_with()


def test_localize_without_a_flag_writes_the_script(localized_without_flag):
    assert localized_without_flag.values["step"] is CloneStep.WRITING_SCRIPT
    assert localized_without_flag.values["target_country"] is None
    assert localized_without_flag.values["target_setting"] is None


def test_a_target_setting_needs_no_country_and_ticks_no_flag(localized_with_setting_only):
    assert localized_with_setting_only.values["target_setting"] == "a modern Western city"
    assert localized_with_setting_only.values["step"] is CloneStep.WRITING_SCRIPT


def test_a_blank_target_setting_is_stored_as_none(localized_with_blank_setting):
    assert localized_with_blank_setting.values["target_setting"] is None
    assert localized_with_blank_setting.values["step"] is CloneStep.PROPOSING


def test_a_target_setting_is_stored_whole(localized_with_long_setting):
    assert localized_with_long_setting.values["target_setting"] == "a" * 20_000


def test_script_language_follows_the_setting_table(script_language):
    assert script_language.actual == script_language.expected


def test_localize_choices_are_checked(localization_error):
    assert str(localization_error.error) == localization_error.expected


def test_localize_at_another_step_is_refused(wrong_step_error):
    assert str(wrong_step_error) == (
        "Cannot localize clone clone-1 while it is waiting at reviewing"
    )


def test_write_script_needs_every_changed_reference(missing_references_error):
    assert str(missing_references_error) == "Reference images missing for: Fan"


def test_write_script_starts_the_step(script_started):
    script_started.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.RUNNING, "step": CloneStep.WRITING_SCRIPT}
    )
    script_started.notify_worker.assert_called_once_with()


def test_resume_queues_only_unfinished_scene_images(resumed_images):
    queued_scene_ids = [
        call.args[1].id for call in resumed_images.image_queue.queue_scene_image.call_args_list
    ]
    assert queued_scene_ids == ["s-2", "s-3"]
    resumed_images.scene_check.check.assert_called_once_with(CLONE_ID)


def test_resume_of_a_claude_step_wakes_the_worker(resumed_script):
    resumed_script.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.RUNNING, "error_message": None}
    )
    resumed_script.notify_worker.assert_called_once_with()


def test_resume_of_a_failed_claude_analysis_step_wakes_the_worker(resumed_analysis):
    resumed_analysis.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.RUNNING, "error_message": None}
    )
    resumed_analysis.notify_worker.assert_called_once_with()


def test_relocalize_of_a_failed_analysis_step_is_refused(analysis_relocalize_error):
    assert str(analysis_relocalize_error) == (
        "Cannot relocalize clone clone-1 while it is failed at extracting_assets"
    )


def test_detail_carries_the_running_ai_activity(detail_while_ai_runs):
    assert detail_while_ai_runs.ai_activity == AiActivity(
        choice=CLAUDE_CHOICE, started_at=ACTIVITY_STARTED_AT, last_output_at=None
    )


def test_resume_of_a_failed_analysis_is_refused(analyzing_resume_error):
    assert str(analyzing_resume_error) == (
        "Cannot resume clone clone-1 while it is failed at analyzing"
    )


def test_relocalize_waits_for_running_images(busy_relocalize_error):
    assert str(busy_relocalize_error) == "Film clone clone-1 has image generation running"


def test_relocalize_deletes_images_and_returns_to_the_choices(relocalized):
    relocalized.files.delete.assert_any_call("clone-1/scenes/s-1.png")
    relocalized.files.delete.assert_any_call("clone-1/references/asset-Fan.png")
    clone_id, values = relocalized.repository.reset_localization.call_args.args
    assert values["status"] is CloneStatus.WAITING
    assert values["step"] is CloneStep.CHOOSING_LOCALIZATION
    assert values["script_title"] is None


def test_relocalize_turns_the_automatic_run_off(relocalized):
    values = relocalized.repository.reset_localization.call_args.args[1]
    assert values["should_run_automatically"] is False
