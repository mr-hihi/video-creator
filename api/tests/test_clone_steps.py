import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.modules.ai_models.ai_calls import AiCallError, AiModelChoice
from app.modules.app_settings.service import AppSettingService
from app.modules.app_settings.setting_rules import ScriptLanguage
from app.modules.film_clones.clone_ai_caller import WatchedCloneAiCaller
from app.modules.film_clones.clone_generation import CloneImageQueue
from app.modules.film_clones.clone_steps import (
    WRITING_SCRIPT_VALUES,
    CloneFrameSaver,
    CloneJobWatcher,
    CloneReferenceCheck,
    CloneSceneImageCheck,
    CloneStepRunner,
    CloneStepTools,
)
from app.modules.film_clones.errors import CloneStepFailedError
from app.modules.film_clones.models import (
    AssetKind,
    CameraAngle,
    CloneAspect,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
    FrameKind,
    ShotSize,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.jobs.film_analysis.notes_passes import CapturedFilmFrame, WrittenNotes
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.markdown import CapturedMoment
from app.modules.jobs.video_to_markdown.moments import KeyMoment
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
CLONE_ID = "clone-1"
CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash")
FINISHED_AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
VIDEO_NOTES = "# Palace escape\n\n> Source: escape.mp4 · Duration: 01:00 · Language: ko\n"
FRAME_ONE = "images/moment-01-00m05s.jpg"
FRAME_TWO = "images/moment-02-00m40s.jpg"
FRAME_THREE = "images/moment-03-00m20s.jpg"


def build_clone(**overrides) -> FilmClone:
    fields = {
        "id": CLONE_ID,
        "job_id": JOB_ID,
        "status": CloneStatus.RUNNING,
        "step": CloneStep.PROPOSING,
        "target_country": "vn",
        "change_appearance": True,
        "change_costume": False,
        "change_setting": False,
        "script_language": "vi",
        "aspect": CloneAspect.LANDSCAPE,
        "preset": {"id": "p-1", "name": "Default", "version": 1},
        "prompts": {"cloneLocalization": "Localize P", "cloneScript": "Script P"},
        "finished_at": None,
    }
    return FilmClone(**{**fields, **overrides})


def build_asset(asset_id: str, kind: AssetKind, name: str, **overrides) -> CloneAsset:
    fields = {
        "id": asset_id,
        "clone_id": CLONE_ID,
        "position": 0,
        "kind": kind,
        "name": name,
        "description": f"{name} as in the film",
        "culture": "Korean",
        "period": "Joseon dynasty",
        "frames": [FRAME_ONE],
        "reference_frame": FRAME_ONE,
        "changed": False,
        "localized_name": None,
        "localized_description": None,
        "reference_status": CloneImageStatus.NONE,
        "reference_path": None,
    }
    return CloneAsset(**{**fields, **overrides})


def build_shot(shot_id: str, position: int, **overrides) -> CloneShot:
    fields = {
        "id": shot_id,
        "clone_id": CLONE_ID,
        "position": position,
        "at_ms": 5000 + position * 35000,
        "frame": FRAME_ONE,
        "frame_kind": FrameKind.DIALOGUE,
        "shot_size": None,
        "camera_angle": None,
        "emotion": None,
        "action": None,
        "asset_ids": [],
    }
    return CloneShot(**{**fields, **overrides})


def build_scene(scene_id: str, image_status: CloneImageStatus) -> CloneScene:
    return CloneScene(
        id=scene_id,
        clone_id=CLONE_ID,
        shot_id=f"shot-of-{scene_id}",
        position=0,
        description="He runs",
        image_prompt="A scholar running",
        asset_ids=[],
        image_status=image_status,
    )


ONE_IMAGE_PER_CALL = {ProviderId.CLAUDE_CLI: 1}


def is_not_stopping() -> bool:
    return False


def build_tools(tmp_path) -> CloneStepTools:
    job_repository = MagicMock(spec=JobRepository)
    job_repository.find_by_id.return_value = None
    app_setting_service = MagicMock(spec=AppSettingService)
    app_setting_service.get_script_language.return_value = ScriptLanguage.FOLLOW_TARGET_COUNTRY
    return CloneStepTools(
        repository=MagicMock(spec=FilmCloneRepository),
        job_repository=job_repository,
        job_storage=JobStorage(tmp_path, 1024),
        ai_caller=build_ai_caller(),
        image_queue=MagicMock(spec=CloneImageQueue),
        app_setting_service=app_setting_service,
        max_images_by_provider={ProviderId.CLAUDE_CLI: 100, ProviderId.GOOGLE: 300},
        script_shots_per_call=100,
    )


def build_ai_caller():
    ai_caller = MagicMock(spec=WatchedCloneAiCaller)
    ai_caller.find_model.return_value = CLAUDE_CHOICE
    return ai_caller


def sent_request(tools: CloneStepTools, call_index: int = 0):
    return tools.ai_caller.ask.call_args_list[call_index].args[2]


def write_frame(tmp_path, frame: str, size: tuple[int, int]) -> None:
    path = tmp_path / JOB_ID / "output" / frame
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 20, 30)).save(path, "JPEG")


def build_frame_shots() -> list[CloneShot]:
    return [
        build_shot("shot-1", 0, frame=FRAME_ONE, at_ms=5000),
        build_shot("shot-2", 1, frame=FRAME_TWO, at_ms=40000, frame_kind=FrameKind.SCENE),
    ]


def build_analysis_tools(tmp_path, step: CloneStep, **clone_overrides) -> CloneStepTools:
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = build_clone(step=step, **clone_overrides)
    tools.repository.find_shots.return_value = build_frame_shots()
    tools.job_repository.find_by_id.return_value = Job(
        id=JOB_ID, options={"prompts": {"cloneAssets": "A P", "cloneShots": "S P"}}
    )
    tools.job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: VIDEO_NOTES}
    return tools


@pytest.fixture
def saved_frames(tmp_path):
    write_frame(tmp_path, FRAME_ONE, (180, 320))
    write_frame(tmp_path, FRAME_TWO, (180, 320))
    tools = build_tools(tmp_path)
    tools.repository.find_by_job_id.return_value = build_clone(step=CloneStep.ANALYZING)
    steps = []
    job = Job(id=JOB_ID, type=JobType.FILM_CLONE, options={"prompts": {"cloneAssets": "A P"}})
    notes = WrittenNotes(
        VIDEO_NOTES,
        [
            CapturedFilmFrame(
                CapturedMoment(KeyMoment(5000, "Greeting"), FRAME_ONE), FrameKind.DIALOGUE
            ),
            CapturedFilmFrame(
                CapturedMoment(KeyMoment(20000, "Ambient: a dog barks"), FRAME_THREE),
                FrameKind.SOUND,
            ),
            CapturedFilmFrame(
                CapturedMoment(KeyMoment(40000, "Scene change"), FRAME_TWO), FrameKind.SCENE
            ),
        ],
    )
    CloneFrameSaver(tools).run(job, notes, steps.append)
    assets, shots = tools.repository.replace_assets_and_shots.call_args.args[1:]
    return SimpleNamespace(tools=tools, steps=steps, assets=assets, shots=shots)


@pytest.fixture
def unknown_clone_error(tmp_path):
    tools = build_tools(tmp_path)
    tools.repository.find_by_job_id.return_value = None
    with pytest.raises(CloneStepFailedError) as caught:
        CloneFrameSaver(tools).run(Job(id=JOB_ID, options={}), WrittenNotes("", []), print)
    return caught.value


@pytest.fixture
def analyzed_without_strays(tmp_path):
    tools = build_analysis_tools(tmp_path, CloneStep.ANALYZING_SHOTS)
    tools.repository.find_assets.return_value = []
    tools.ai_caller.ask.return_value = {"shots": [{"frame": FRAME_ONE, "shotSize": "full"}]}
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


@pytest.fixture(
    params=[
        ({"shots": []}, "claude returned no shots"),
        (
            {"shots": [{"frame": "Frame 9", "shotSize": "wide"}, {"frame": "moment-99.jpg"}]},
            "claude named no captured frame: ['Frame 9', 'moment-99.jpg']",
        ),
        (
            {"shots": [{"frame": f"moment-9{index}.jpg"} for index in range(6)]},
            "claude named no captured frame: "
            "['moment-90.jpg', 'moment-91.jpg', 'moment-92.jpg', 'moment-93.jpg', 'moment-94.jpg']",
        ),
    ]
)
def unplaced_shots(request, tmp_path):
    reply, expected_message = request.param
    tools = build_analysis_tools(tmp_path, CloneStep.ANALYZING_SHOTS)
    tools.repository.find_assets.return_value = []
    tools.ai_caller.ask.return_value = reply
    CloneStepRunner(tools).run_next(is_not_stopping)
    return SimpleNamespace(tools=tools, expected_message=expected_message)


@pytest.fixture
def gemini_shot_analysis(tmp_path):
    tools = build_analysis_tools(tmp_path, CloneStep.ANALYZING_SHOTS)
    tools.job_repository.find_by_id.return_value = Job(
        id=JOB_ID, options={"prompts": {"cloneShots": "S P"}}
    )
    tools.repository.find_assets.return_value = []
    tools.ai_caller.find_model.return_value = GEMINI_CHOICE
    tools.ai_caller.ask.return_value = {"shots": []}
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


def test_a_gemini_call_asks_with_its_model_and_names_it_in_the_error(gemini_shot_analysis):
    clone_id, choice, ask = gemini_shot_analysis.ai_caller.ask.call_args.args
    assert (clone_id, choice, ask.instructions) == (CLONE_ID, GEMINI_CHOICE, "S P")
    assert gemini_shot_analysis.repository.update_clone.call_args.args[1]["error_message"] == (
        "gemini returned no shots"
    )


def test_each_ai_step_records_its_model_before_the_call(gemini_shot_analysis):
    gemini_shot_analysis.repository.save_ai_used.assert_called_once_with(
        CLONE_ID, CloneStep.ANALYZING_SHOTS, GEMINI_CHOICE
    )


@pytest.fixture
def gemini_script(tmp_path):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = build_clone(step=CloneStep.WRITING_SCRIPT)
    tools.repository.find_shots.return_value = build_frame_shots()
    tools.repository.find_assets.return_value = []
    tools.job_repository.find_by_id.return_value = Job(
        id=JOB_ID, source_filename="escape.mp4", options={}
    )
    tools.job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: VIDEO_NOTES}
    tools.ai_caller.find_model.return_value = GEMINI_CHOICE
    tools.ai_caller.ask.return_value = {"scenes": []}
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


def test_a_gemini_script_names_gemini_for_missing_scenes(gemini_script):
    assert gemini_script.repository.update_clone.call_args.args[1]["error_message"] == (
        "gemini returned no scene for 2 of 2 shots"
    )


@pytest.fixture
def extracted(tmp_path):
    tools = build_analysis_tools(tmp_path, CloneStep.EXTRACTING_ASSETS)
    tools.ai_caller.ask.return_value = {
        "assets": [
            {
                "kind": "character",
                "name": "Min-jun",
                "description": "A scholar",
                "culture": "Korean",
                "period": "Joseon dynasty",
                "frames": [FRAME_TWO],
            }
        ]
    }
    CloneStepRunner(tools).run_next(is_not_stopping)
    _clone_id, assets, clone_values = tools.repository.save_assets.call_args.args
    return SimpleNamespace(tools=tools, assets=assets, clone_values=clone_values)


@pytest.fixture
def extracted_from_spread_frames(tmp_path):
    tools = replace(
        build_analysis_tools(tmp_path, CloneStep.EXTRACTING_ASSETS),
        max_images_by_provider=ONE_IMAGE_PER_CALL,
    )
    tools.ai_caller.ask.return_value = {
        "assets": [{"kind": "prop", "name": "Fan", "frames": [FRAME_TWO]}]
    }
    CloneStepRunner(tools).run_next(is_not_stopping)
    (asset,) = tools.repository.save_assets.call_args.args[1]
    return SimpleNamespace(
        sent_frames=[image.label for image in sent_request(tools).images], asset=asset
    )


@pytest.fixture
def analyzed_in_batches(tmp_path):
    tools = replace(
        build_analysis_tools(tmp_path, CloneStep.ANALYZING_SHOTS),
        max_images_by_provider=ONE_IMAGE_PER_CALL,
    )
    tools.repository.find_assets.return_value = []
    tools.ai_caller.ask.side_effect = [
        {"shots": [{"frame": FRAME_ONE, "shotSize": "close_up"}]},
        {"shots": [{"frame": FRAME_TWO, "shotSize": "wide"}]},
    ]
    CloneStepRunner(tools).run_next(is_not_stopping)
    values_by_shot_id = tools.repository.save_shot_analysis.call_args.args[1]
    return SimpleNamespace(
        sent_frames=[
            [image.label for image in call.args[2].images]
            for call in tools.ai_caller.ask.call_args_list
        ],
        shot_sizes=[values_by_shot_id[shot_id]["shot_size"] for shot_id in ("shot-1", "shot-2")],
    )


@pytest.fixture
def written_in_batches(tmp_path):
    tools = replace(build_tools(tmp_path), script_shots_per_call=1)
    tools.repository.find_oldest_running.return_value = build_clone(step=CloneStep.WRITING_SCRIPT)
    tools.repository.find_shots.return_value = [build_shot("shot-1", 0), build_shot("shot-2", 1)]
    tools.repository.find_assets.return_value = []
    tools.job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: VIDEO_NOTES}
    tools.ai_caller.ask.side_effect = [
        {
            "title": "Palace Escape",
            "logline": "A scholar flees",
            "scenes": [{"shotId": "shot-1", "description": "He runs", "imagePrompt": "P1"}],
        },
        {
            "title": "Second Title",
            "logline": "Second logline",
            "scenes": [{"shotId": "shot-2", "description": "He hides", "imagePrompt": "P2"}],
        },
    ]
    CloneStepRunner(tools).run_next(is_not_stopping)
    scenes, clone_values = tools.repository.save_scenes.call_args.args[1:]
    return SimpleNamespace(
        sent_messages=[call.args[2].message for call in tools.ai_caller.ask.call_args_list],
        scene_shot_ids=[scene.shot_id for scene in scenes],
        clone_values=clone_values,
    )


@pytest.fixture
def extracting_without_job(tmp_path):
    tools = build_analysis_tools(tmp_path, CloneStep.EXTRACTING_ASSETS)
    tools.job_repository.find_by_id.return_value = None
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


@pytest.fixture
def analyzed(tmp_path):
    tools = build_analysis_tools(tmp_path, CloneStep.ANALYZING_SHOTS)
    tools.repository.find_assets.return_value = [build_asset("a-1", AssetKind.CHARACTER, "Min-jun")]
    tools.ai_caller.ask.return_value = {
        "shots": [
            {
                "frame": FRAME_TWO,
                "shotSize": "wide",
                "cameraAngle": "high",
                "emotion": "Calm",
                "action": "Reads",
                "assetNames": ["min-jun"],
            },
            {"frame": "Frame 9", "shotSize": "wide"},
        ]
    }
    CloneStepRunner(tools).run_next(is_not_stopping)
    _clone_id, values_by_shot_id, clone_values = tools.repository.save_shot_analysis.call_args.args
    return SimpleNamespace(
        tools=tools, values_by_shot_id=values_by_shot_id, clone_values=clone_values
    )


@pytest.fixture(
    params=[
        (
            JobStatus.DONE,
            None,
            {"status": CloneStatus.RUNNING, "step": CloneStep.EXTRACTING_ASSETS},
        ),
        (
            JobStatus.FAILED,
            "claude failed: Overloaded",
            {"status": CloneStatus.FAILED, "error_message": "claude failed: Overloaded"},
        ),
    ]
)
def watched_job(request):
    job_status, error_message, expected_values = request.param
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_by_job_id.return_value = build_clone(step=CloneStep.ANALYZING)
    repository.find_jobs.return_value = {
        JOB_ID: Job(id=JOB_ID, status=job_status, error_message=error_message)
    }
    CloneJobWatcher(repository).on_job_finished(JOB_ID)
    return SimpleNamespace(repository=repository, expected_values=expected_values)


@pytest.fixture(
    params=[
        (
            {
                "target_country": "vn",
                "target_setting": "a modern Saigon street",
                "change_appearance": True,
            },
            {"script_language": "vi", "step": CloneStep.PROPOSING},
        ),
        (
            {"target_country": None, "target_setting": None, "change_appearance": False},
            {"script_language": "ko", "step": CloneStep.WRITING_SCRIPT},
        ),
    ]
)
def analyzed_automatically(request, tmp_path):
    choice_overrides, expected_changes = request.param
    tools = build_analysis_tools(
        tmp_path,
        CloneStep.ANALYZING_SHOTS,
        should_run_automatically=True,
        **choice_overrides,
    )
    tools.repository.find_assets.return_value = []
    tools.ai_caller.ask.return_value = {"shots": [{"frame": FRAME_ONE, "shotSize": "full"}]}
    CloneStepRunner(tools).run_next(is_not_stopping)
    expected = {
        "change_costume": False,
        "change_setting": False,
        "status": CloneStatus.RUNNING,
        "error_message": None,
        **choice_overrides,
        **expected_changes,
    }
    actual = tools.repository.save_shot_analysis.call_args.args[2]
    return SimpleNamespace(actual=actual, expected=expected)


def run_proposing(tmp_path, clone: FilmClone):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = clone
    min_jun = build_asset("a-1", AssetKind.CHARACTER, "Min-jun")
    palace = build_asset("a-2", AssetKind.LOCATION, "Palace")
    changed_min_jun = build_asset(
        "a-1",
        AssetKind.CHARACTER,
        "Min-jun",
        changed=True,
        localized_name="Minh",
        localized_description="A Vietnamese scholar",
    )
    tools.repository.find_assets.side_effect = [[min_jun, palace], [changed_min_jun, palace]]
    tools.ai_caller.ask.return_value = {
        "assets": [
            {
                "name": "Min-jun",
                "changed": True,
                "localizedName": "Minh",
                "localizedDescription": "A Vietnamese scholar",
                "note": "Moved to Vietnam",
            }
        ]
    }
    was_run = CloneStepRunner(tools).run_next(is_not_stopping)
    return SimpleNamespace(tools=tools, was_run=was_run, changed_min_jun=changed_min_jun)


@pytest.fixture
def proposed(tmp_path):
    return run_proposing(tmp_path, build_clone())


@pytest.fixture
def proposed_with_target_setting(tmp_path):
    return run_proposing(tmp_path, build_clone(target_setting="a modern Saigon street"))


@pytest.fixture
def proposed_automatically(tmp_path):
    return run_proposing(tmp_path, build_clone(should_run_automatically=True))


def run_proposing_without_candidates(tmp_path, clone: FilmClone) -> CloneStepTools:
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = clone
    tools.repository.find_assets.return_value = [build_asset("a-1", AssetKind.CHARACTER, "Min-jun")]
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


@pytest.fixture
def proposed_without_candidates(tmp_path):
    return run_proposing_without_candidates(
        tmp_path, build_clone(change_appearance=False, change_setting=True)
    )


@pytest.fixture
def proposed_automatically_without_candidates(tmp_path):
    return run_proposing_without_candidates(
        tmp_path,
        build_clone(change_appearance=False, change_setting=True, should_run_automatically=True),
    )


def write_script(tmp_path, clone: FilmClone):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = clone
    tools.repository.find_assets.return_value = [
        build_asset(
            "a-1",
            AssetKind.CHARACTER,
            "Min-jun",
            changed=True,
            localized_name="Minh",
            localized_description="A Vietnamese scholar",
        ),
        build_asset("a-2", AssetKind.LOCATION, "Palace"),
    ]
    shots = [
        build_shot(
            "shot-1",
            0,
            shot_size=ShotSize.CLOSE_UP,
            camera_angle=CameraAngle.LOW,
            emotion="Afraid",
            action="Runs",
            asset_ids=["a-1", "a-2"],
        ),
        build_shot("shot-2", 1),
    ]
    tools.repository.find_shots.return_value = shots
    tools.job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: VIDEO_NOTES}
    tools.job_repository.find_by_id.return_value = Job(
        source_filename="Palace Escape.mp4", options={}
    )
    tools.ai_caller.ask.return_value = {
        "title": "",
        "logline": "A scholar flees",
        "scenes": [
            {"shotId": "shot-2", "description": "He hides", "dialogue": "", "imagePrompt": "P2"},
            {
                "shotId": "shot-1",
                "description": "He runs",
                "dialogue": "Minh: Chạy!",
                "imagePrompt": "P1",
            },
        ],
    }
    CloneStepRunner(tools).run_next(is_not_stopping)
    scenes, clone_values = tools.repository.save_scenes.call_args.args[1:]
    return SimpleNamespace(tools=tools, scenes=scenes, clone_values=clone_values, shots=shots)


@pytest.fixture
def written_script(tmp_path):
    return write_script(tmp_path, build_clone(step=CloneStep.WRITING_SCRIPT))


@pytest.fixture
def written_script_with_target_setting(tmp_path):
    return write_script(
        tmp_path,
        build_clone(step=CloneStep.WRITING_SCRIPT, target_setting="a modern Saigon street"),
    )


@pytest.fixture
def failed_step(tmp_path):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = build_clone()
    tools.repository.find_assets.return_value = [build_asset("a-1", AssetKind.CHARACTER, "Min-jun")]
    tools.ai_caller.ask.side_effect = AiCallError("claude timed out after 900s")
    CloneStepRunner(tools).run_next(is_not_stopping)
    return tools


@pytest.fixture
def interrupted_step(tmp_path):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = build_clone(step=CloneStep.WRITING_SCRIPT)
    tools.repository.find_shots.return_value = build_frame_shots()
    tools.ai_caller.ask.side_effect = AiCallError("claude exited with 143: ")
    was_run = CloneStepRunner(tools).run_next(lambda: True)
    return SimpleNamespace(tools=tools, was_run=was_run)


@pytest.fixture
def idle_runner(tmp_path):
    tools = build_tools(tmp_path)
    tools.repository.find_oldest_running.return_value = None
    return CloneStepRunner(tools).run_next(is_not_stopping)


def check_references(clone: FilmClone | None, assets: list[CloneAsset]) -> SimpleNamespace:
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_by_id.return_value = clone
    repository.find_assets.return_value = assets
    notify_worker = MagicMock()
    CloneReferenceCheck(repository, notify_worker).check(CLONE_ID)
    return SimpleNamespace(repository=repository, notify_worker=notify_worker)


DONE_REFERENCE_ASSET = build_asset(
    "a-1", AssetKind.CHARACTER, "Min-jun", changed=True, reference_status=CloneImageStatus.DONE
)
FAILED_REFERENCE_ASSET = build_asset(
    "a-2", AssetKind.COSTUME, "Hanbok", changed=True, reference_status=CloneImageStatus.FAILED
)
UNCHANGED_ASSET = build_asset("a-3", AssetKind.LOCATION, "Palace")
AUTOMATIC_REVIEWING_CLONE = build_clone(
    status=CloneStatus.WAITING, step=CloneStep.REVIEWING, should_run_automatically=True
)


@pytest.fixture
def references_done_check():
    return check_references(AUTOMATIC_REVIEWING_CLONE, [DONE_REFERENCE_ASSET, UNCHANGED_ASSET])


@pytest.fixture(
    params=[
        (AUTOMATIC_REVIEWING_CLONE, [DONE_REFERENCE_ASSET, FAILED_REFERENCE_ASSET]),
        (
            build_clone(status=CloneStatus.WAITING, step=CloneStep.REVIEWING),
            [DONE_REFERENCE_ASSET],
        ),
        (
            build_clone(
                status=CloneStatus.RUNNING,
                step=CloneStep.WRITING_SCRIPT,
                should_run_automatically=True,
            ),
            [DONE_REFERENCE_ASSET],
        ),
        (None, []),
    ],
    ids=["reference-failed", "step-by-step-clone", "past-reviewing", "unknown-clone"],
)
def references_unmoved_check(request):
    clone, assets = request.param
    return check_references(clone, assets)


def check_scene_images(clone: FilmClone, scenes: list[CloneScene]) -> MagicMock:
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_by_id.return_value = clone
    repository.find_scenes.return_value = scenes
    CloneSceneImageCheck(repository).check(CLONE_ID)
    return repository


@pytest.fixture
def all_done_check():
    return check_scene_images(
        build_clone(step=CloneStep.GENERATING_SCENE_IMAGES),
        [build_scene("s-1", CloneImageStatus.DONE), build_scene("s-2", CloneImageStatus.DONE)],
    )


@pytest.fixture
def one_failed_check():
    return check_scene_images(
        build_clone(step=CloneStep.GENERATING_SCENE_IMAGES),
        [build_scene("s-1", CloneImageStatus.DONE), build_scene("s-2", CloneImageStatus.FAILED)],
    )


@pytest.fixture
def still_running_check():
    return check_scene_images(
        build_clone(step=CloneStep.GENERATING_SCENE_IMAGES),
        [build_scene("s-1", CloneImageStatus.DONE), build_scene("s-2", CloneImageStatus.QUEUED)],
    )


@pytest.fixture
def finished_clone_check():
    return check_scene_images(
        build_clone(
            step=CloneStep.GENERATING_SCENE_IMAGES,
            status=CloneStatus.DONE,
            finished_at=FINISHED_AT,
        ),
        [build_scene("s-1", CloneImageStatus.DONE)],
    )


def test_frame_saver_asks_the_ai_nothing_and_reports_no_step(saved_frames):
    assert saved_frames.steps == []
    saved_frames.tools.ai_caller.ask.assert_not_called()


def test_frame_saver_saves_one_empty_shot_per_frame(saved_frames):
    first, second, third = saved_frames.shots
    assert saved_frames.assets == []
    assert (first.frame, first.frame_kind, first.at_ms) == (FRAME_ONE, FrameKind.DIALOGUE, 5000)
    assert (second.frame, second.frame_kind, second.at_ms) == (FRAME_THREE, FrameKind.SOUND, 20000)
    assert (third.frame, third.frame_kind, third.at_ms) == (FRAME_TWO, FrameKind.SCENE, 40000)
    assert (third.position, third.shot_size, third.asset_ids) == (2, None, [])


def test_frame_saver_sets_the_aspect_from_the_frames(saved_frames):
    saved_frames.tools.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"aspect": CloneAspect.PORTRAIT}
    )


def test_frame_saver_without_clone_fails(unknown_clone_error):
    assert str(unknown_clone_error) == "No film clone uses job job-1"


def test_extracting_sends_every_frame_with_its_path(extracted):
    request = sent_request(extracted.tools)
    assert extracted.tools.ai_caller.ask.call_args.args[0] == CLONE_ID
    assert request.instructions == "A P"
    assert [image.label for image in request.images] == [FRAME_ONE, FRAME_TWO]
    assert "Video notes:" in request.message


def test_extracting_sends_at_most_the_call_limit_of_frames_spread_evenly(
    extracted_from_spread_frames,
):
    assert extracted_from_spread_frames.sent_frames == [FRAME_ONE]
    assert extracted_from_spread_frames.asset.reference_frame == FRAME_TWO


def test_analyzing_sends_the_frames_in_batches_and_joins_the_replies(analyzed_in_batches):
    assert analyzed_in_batches.sent_frames == [[FRAME_ONE], [FRAME_TWO]]
    assert analyzed_in_batches.shot_sizes == [ShotSize.CLOSE_UP, ShotSize.WIDE]


def test_script_is_written_in_batches_of_shots(written_in_batches):
    first_message, second_message = written_in_batches.sent_messages
    assert ("shot-1 ·" in first_message, "shot-2 ·" in first_message) == (True, False)
    assert ("shot-1 ·" in second_message, "shot-2 ·" in second_message) == (False, True)
    assert written_in_batches.scene_shot_ids == ["shot-1", "shot-2"]
    assert (
        written_in_batches.clone_values["script_title"],
        written_in_batches.clone_values["logline"],
    ) == ("Palace Escape", "A scholar flees")


def test_extracting_saves_the_assets_then_analyzes_shots(extracted):
    (asset,) = extracted.assets
    assert (asset.name, asset.reference_frame) == ("Min-jun", FRAME_TWO)
    assert extracted.clone_values == {"step": CloneStep.ANALYZING_SHOTS}


def test_extracting_without_its_job_fails_the_clone(extracting_without_job):
    extracting_without_job.repository.update_clone.assert_called_once_with(
        CLONE_ID,
        {
            "status": CloneStatus.FAILED,
            "error_message": "Job job-1 of film clone clone-1 not found",
        },
    )


def test_analyzing_lists_the_assets_for_the_shot_call(analyzed):
    request = sent_request(analyzed.tools)
    assert request.instructions == "S P"
    assert "Min-jun (character)" in request.message
    assert request.message.startswith("Give exactly one entry per frame.")


def test_analyzing_saves_values_per_shot_linked_to_assets(analyzed):
    assert analyzed.values_by_shot_id["shot-1"] == {
        "shot_size": None,
        "camera_angle": None,
        "emotion": None,
        "action": None,
        "asset_ids": [],
    }
    assert analyzed.values_by_shot_id["shot-2"] == {
        "shot_size": ShotSize.WIDE,
        "camera_angle": CameraAngle.HIGH,
        "emotion": "Calm",
        "action": "Reads",
        "asset_ids": ["a-1"],
    }


def test_analyzing_then_waits_for_the_localization_choices(analyzed):
    assert analyzed.clone_values == {
        "status": CloneStatus.WAITING,
        "step": CloneStep.CHOOSING_LOCALIZATION,
    }


def test_automatic_analyzing_applies_the_stored_choices(analyzed_automatically):
    assert analyzed_automatically.actual == analyzed_automatically.expected


def test_analyzing_with_every_reply_frame_placed_warns_nothing(caplog, analyzed_without_strays):
    assert [
        record for record in caplog.get_records("setup") if record.levelno == logging.WARNING
    ] == []
    analyzed_without_strays.repository.save_shot_analysis.assert_called_once()


def test_analyzing_fails_when_no_shot_names_a_captured_frame(unplaced_shots):
    unplaced_shots.tools.repository.save_shot_analysis.assert_not_called()
    unplaced_shots.tools.repository.update_clone.assert_called_once_with(
        CLONE_ID,
        {"status": CloneStatus.FAILED, "error_message": unplaced_shots.expected_message},
    )


def test_analyzing_warns_about_reply_frames_it_cannot_place(caplog, analyzed):
    assert [
        record.getMessage()
        for record in caplog.get_records("setup")
        if record.levelno == logging.WARNING
    ] == ["Film clone clone-1: 1 shot entries name no captured frame: ['Frame 9']"]


def test_finished_job_moves_the_analyzing_clone(watched_job):
    watched_job.repository.update_clone_if_step.assert_called_once_with(
        CLONE_ID, CloneStep.ANALYZING, watched_job.expected_values
    )


def test_proposing_sends_candidates_with_their_frames(proposed):
    request = sent_request(proposed.tools)
    assert proposed.was_run is True
    assert request.instructions == "Localize P"
    assert request.message.startswith("Target country: Vietnam")
    assert "Min-jun (character) — Min-jun as in the film. Culture: Korean." in request.message
    assert "Palace" not in request.message
    assert [image.label for image in request.images] == [FRAME_ONE]
    assert "Target setting:" not in request.message


def test_proposing_sends_the_target_setting_after_the_country(proposed_with_target_setting):
    assert sent_request(proposed_with_target_setting.tools).message.startswith(
        "Target country: Vietnam\n\nTarget setting: a modern Saigon street\n"
        "Follow the target setting where it differs from the original period or place.\n\n"
        "Change only: "
    )


def test_proposing_saves_replacements_then_waits_for_review(proposed):
    values_by_asset_id = proposed.tools.repository.update_assets.call_args.args[0]
    assert values_by_asset_id["a-1"]["changed"] is True
    assert values_by_asset_id["a-1"]["localized_name"] == "Minh"
    assert values_by_asset_id["a-1"]["localization_note"] == "Moved to Vietnam"
    proposed.tools.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.WAITING, "step": CloneStep.REVIEWING}
    )


def test_proposing_queues_one_reference_per_changed_asset(proposed):
    (queued_call,) = proposed.tools.image_queue.queue_reference.call_args_list
    assert queued_call.args[1] is proposed.changed_min_jun


def test_proposing_without_candidates_skips_the_ai(proposed_without_candidates):
    proposed_without_candidates.ai_caller.ask.assert_not_called()
    proposed_without_candidates.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.WAITING, "step": CloneStep.REVIEWING}
    )


def test_automatic_proposing_with_changes_waits_for_the_references(proposed_automatically):
    proposed_automatically.tools.repository.update_clone.assert_called_once_with(
        CLONE_ID, {"status": CloneStatus.WAITING, "step": CloneStep.REVIEWING}
    )
    proposed_automatically.tools.image_queue.queue_reference.assert_called_once()


def test_automatic_proposing_without_changes_writes_the_script(
    proposed_automatically_without_candidates,
):
    tools = proposed_automatically_without_candidates
    tools.repository.update_clone.assert_called_once_with(CLONE_ID, WRITING_SCRIPT_VALUES)
    tools.image_queue.queue_reference.assert_not_called()


def test_every_reference_done_writes_the_script(references_done_check):
    references_done_check.repository.update_clone.assert_called_once_with(
        CLONE_ID, WRITING_SCRIPT_VALUES
    )
    references_done_check.notify_worker.assert_called_once_with()


def test_reference_check_otherwise_leaves_the_clone(references_unmoved_check):
    references_unmoved_check.repository.update_clone.assert_not_called()
    references_unmoved_check.notify_worker.assert_not_called()


def test_script_message_lists_assets_and_shots(written_script):
    request = sent_request(written_script.tools)
    assert request.instructions == "Script P"
    assert request.images == ()
    assert request.message.startswith(
        "Script language: Vietnamese. Keep the tone and register of the original dialogue."
    )
    assert "Setting: Vietnam" in request.message
    assert "Minh (character) — A Vietnamese scholar (replaces Min-jun)" in request.message
    assert (
        "shot-1 · 00:05 · Close-up · Low angle · emotion: Afraid · action: Runs · "
        "assets: Minh, Palace"
    ) in request.message
    assert "shot-2 · 00:40 · — · — · emotion: — · action: — · assets: —" in request.message


def test_script_message_adds_the_target_setting_to_the_country(
    written_script_with_target_setting,
):
    request = sent_request(written_script_with_target_setting.tools)
    assert "\n\nSetting: Vietnam. a modern Saigon street\n\n" in request.message
    assert "Keep the tone and register of the original dialogue." in request.message


def test_script_scenes_follow_shot_order(written_script):
    first, second = written_script.scenes
    assert (first.shot_id, first.description, first.dialogue) == (
        "shot-1",
        "He runs",
        "Minh: Chạy!",
    )
    assert first.asset_ids == ["a-1", "a-2"]
    assert (second.shot_id, second.dialogue, second.image_status) == (
        "shot-2",
        None,
        CloneImageStatus.NONE,
    )


def test_script_moves_to_scene_images_and_queues_them(written_script):
    assert written_script.clone_values == {
        "script_title": "Palace Escape",
        "logline": "A scholar flees",
        "step": CloneStep.GENERATING_SCENE_IMAGES,
    }
    queued_shots = [
        call.args[2] for call in written_script.tools.image_queue.queue_scene_image.call_args_list
    ]
    assert queued_shots == written_script.shots


def test_failing_step_fails_the_clone_at_that_step(failed_step):
    failed_step.repository.update_clone.assert_called_once_with(
        CLONE_ID,
        {"status": CloneStatus.FAILED, "error_message": "claude timed out after 900s"},
    )


def test_step_cut_by_shutdown_leaves_the_clone_running(interrupted_step):
    assert interrupted_step.was_run is True
    interrupted_step.tools.repository.update_clone.assert_not_called()
    interrupted_step.tools.repository.save_scenes.assert_not_called()


def test_runner_without_work_reports_nothing_done(idle_runner):
    assert idle_runner is False


def test_all_scene_images_done_finishes_the_clone(all_done_check):
    clone_id, values = all_done_check.update_clone.call_args.args
    assert values["status"] is CloneStatus.DONE
    assert values["error_message"] is None
    assert values["finished_at"] is not None


def test_failed_scene_image_fails_the_clone(one_failed_check):
    one_failed_check.update_clone.assert_called_once_with(
        CLONE_ID,
        {
            "status": CloneStatus.FAILED,
            "error_message": "1 scene image(s) failed — fix them and resume",
        },
    )


def test_scene_images_still_running_change_nothing(still_running_check):
    still_running_check.update_clone.assert_not_called()


def test_done_clone_keeps_its_finished_time(finished_clone_check):
    assert finished_clone_check.update_clone.call_args.args[1]["finished_at"] == FINISHED_AT


def test_reply_schema_is_valid_json(extracted):
    assert json.loads(json.dumps(sent_request(extracted.tools).reply_schema))["required"] == [
        "assets"
    ]
