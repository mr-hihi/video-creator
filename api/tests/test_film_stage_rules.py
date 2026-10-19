from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.db import utc_now
from app.modules.films.errors import FilmConflictError
from app.modules.films.film_access import EpisodeContext, PartContext
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue
from app.modules.films.models import (
    Character,
    Episode,
    EpisodePart,
    EpisodeStatus,
    EpisodeStep,
    FilmProject,
    MediaStatus,
    ProjectStatus,
    Scene,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import AssembledFilm, EpisodeStageRunner, StageRunnerTools
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.media_generation.service import GenerationService

UPLOAD_MAX_MB = 20
VOICE = VoiceTemplate(id="v1", name="narrator-en")
FILM = AssembledFilm("projects/p1/episodes/e1/output/film.mp4", None, 9000)
MAI = Character(id="c1", name="Mai", reference_status=MediaStatus.NONE)
PART_BLOCKED_MESSAGE = "Part 2 already has images or clips — delete them before rewriting"


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


@dataclass(frozen=True)
class PartRewriteCase:
    expected: str
    project_values: dict = field(default_factory=dict)
    episode_status: EpisodeStatus = EpisodeStatus.PAUSED
    open_requests: tuple[GenerationRequest, ...] = ()
    part_scenes: tuple[Scene, ...] = ()


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "status": ProjectStatus.ACTIVE,
        "allow_narration": True,
        "narrator_voice_id": "v1",
        "allow_music": True,
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 1,
        "status": EpisodeStatus.DONE,
        "step": EpisodeStep.ASSEMBLING,
        "stop_points": {},
        "paused_stop_point": None,
        "music_prompt": "Slow cello",
        "music_status": MediaStatus.NONE,
    }
    return Episode(**{**defaults, **values})


def build_part(**values) -> EpisodePart:
    defaults = {
        "id": "pt2",
        "episode_id": "e1",
        "position": 1,
        "title": "The City",
        "plan": "Mai finds the city.",
        "target_duration_s": 60,
        "recap": "Mai found the drowned city.",
    }
    return EpisodePart(**{**defaults, **values})


def build_scene(scene_id: str, **values) -> Scene:
    defaults = {
        "id": scene_id,
        "episode_id": "e1",
        "part_id": "pt1",
        "character_ids": [],
        "narrator_text": None,
        "narration_status": MediaStatus.NONE,
        "clip_status": MediaStatus.DONE,
        "clip_duration_ms": 8000,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
    }
    return Scene(**{**defaults, **values})


def build_runner(tmp_path, project: FilmProject, episode: Episode, scenes: list[Scene]):
    repository = MagicMock(spec=FilmRepository)
    repository.find_project.side_effect = lambda project_id: (
        project if project_id == project.id else None
    )
    repository.find_episode.side_effect = lambda episode_id: (
        episode if episode_id == episode.id else None
    )
    repository.update_episode.side_effect = lambda episode_id, values: [
        setattr(episode, name, value) for name, value in values.items()
    ]
    repository.find_scenes.return_value = scenes
    repository.find_voice.return_value = VOICE
    repository.find_characters_by_ids.return_value = {}
    repository.find_open_requests_for_episode.return_value = []
    repository.find_part_scenes.return_value = []
    media_queue = MagicMock(spec=FilmMediaQueue)
    notify_step_worker = MagicMock()
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    runner = EpisodeStageRunner(
        StageRunnerTools(
            repository=repository,
            files=files,
            media_queue=media_queue,
            generation_service=MagicMock(spec=GenerationService),
            notify_step_worker=notify_step_worker,
            cancel_worker_step=MagicMock(),
        )
    )
    return SimpleNamespace(
        runner=runner,
        repository=repository,
        media_queue=media_queue,
        notify_step_worker=notify_step_worker,
        files=files,
        context=EpisodeContext(project=project, episode=episode),
        part_context=PartContext(project=project, episode=episode, part=build_part()),
        episode=episode,
    )


@pytest.fixture
def assembled_with_audio(tmp_path):
    scenes = [
        build_scene("s1", narrator_text="The fog never lifts."),
        build_scene("s2", narrator_text="  ", clip_duration_ms=6000, trim_end_ms=5000),
        build_scene("s3", narrator_text="Done already.", narration_status=MediaStatus.DONE),
    ]
    parts = build_runner(tmp_path, build_project(), build_episode(), scenes)
    episode = parts.runner.assemble(parts.context)
    return SimpleNamespace(parts=parts, episode=episode)


@pytest.fixture
def assembled_without_audio(tmp_path):
    project = build_project(allow_narration=False, narrator_voice_id=None, allow_music=False)
    parts = build_runner(tmp_path, project, build_episode(), [build_scene("s1")])
    parts.runner.assemble(parts.context)
    return parts


@pytest.fixture
def failed_audio(tmp_path):
    scenes = [build_scene("s1", narrator_text="Hello.", narration_status=MediaStatus.FAILED)]
    episode = build_episode(
        status=EpisodeStatus.RUNNING,
        step=EpisodeStep.GENERATING_AUDIO,
        music_status=MediaStatus.FAILED,
    )
    parts = build_runner(tmp_path, build_project(), episode, scenes)
    parts.runner.advance("e1")
    return parts.episode


@pytest.fixture
def project_wide_final(tmp_path):
    parts = build_runner(tmp_path, build_project(), build_episode(), [])
    parts.repository.find_running_episodes_of_project.return_value = [
        build_episode(id="e7"),
        build_episode(id="e8"),
    ]
    parts.runner.advance = MagicMock(return_value=False)
    parts.runner.on_request_final(
        GenerationRequest(kind=GenerationKind.CHARACTER_IMAGE, project_id="p1", episode_id=None)
    )
    parts.runner.on_request_final(
        GenerationRequest(kind=GenerationKind.CHARACTER_IMAGE, project_id=None, episode_id=None)
    )
    return parts


@pytest.fixture(
    params=[
        build_episode(status=EpisodeStatus.RUNNING, step=EpisodeStep.WRITING_OUTLINE),
        build_episode(status=EpisodeStatus.RUNNING, step=EpisodeStep.WRITING_SCRIPT),
        build_episode(status=EpisodeStatus.RUNNING, step=EpisodeStep.UPDATING_STORY_BIBLE),
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.GENERATING_CLIPS),
        build_episode(status=EpisodeStatus.RUNNING, step=None),
    ]
)
def idle_advance(request, tmp_path):
    parts = build_runner(tmp_path, build_project(), request.param, [])
    return SimpleNamespace(moved=parts.runner.advance("e1"), parts=parts)


@pytest.fixture
def missing_episode_advance(tmp_path):
    parts = build_runner(tmp_path, build_project(), build_episode(), [])
    return parts.runner.advance("unknown")


@pytest.fixture
def worker_results_on_a_paused_episode(tmp_path):
    episode = build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.WRITING_SCRIPT)
    parts = build_runner(tmp_path, build_project(), episode, [])
    parts.runner.finish_worker_stage("e1", EpisodeStep.WRITING_SCRIPT)
    parts.runner.finish_assembly("e1", FILM)
    parts.runner.fail_worker_step("e1", EpisodeStep.WRITING_SCRIPT, "claude failed: Overloaded")
    return parts


@pytest.fixture
def missing_project_error(tmp_path):
    episode = build_episode(
        project_id="gone", status=EpisodeStatus.RUNNING, step=EpisodeStep.GENERATING_CLIPS
    )
    parts = build_runner(tmp_path, build_project(), episode, [])
    with pytest.raises(LookupError) as error:
        parts.runner.advance("e1")
    return error.value


@pytest.fixture(
    params=[
        (
            {"afterOutline": False},
            None,
            (EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT, None, 1),
        ),
        (
            {"afterOutline": True},
            None,
            (EpisodeStatus.PAUSED, EpisodeStep.WRITING_OUTLINE, EpisodeStep.WRITING_OUTLINE, 0),
        ),
        (
            {"afterOutline": True},
            EpisodeStep.WRITING_OUTLINE,
            (EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT, EpisodeStep.WRITING_OUTLINE, 1),
        ),
    ]
)
def finished_outline(request, tmp_path):
    stop_points, paused_stop_point, expected = request.param
    episode = build_episode(
        status=EpisodeStatus.RUNNING,
        step=EpisodeStep.WRITING_OUTLINE,
        stop_points=stop_points,
        paused_stop_point=paused_stop_point,
    )
    parts = build_runner(tmp_path, build_project(), episode, [])
    parts.runner.finish_worker_stage("e1", EpisodeStep.WRITING_OUTLINE)
    return Outcome(
        (
            episode.status,
            episode.step,
            episode.paused_stop_point,
            parts.notify_step_worker.call_count,
        ),
        expected,
    )


@pytest.fixture
def finished_story_bible(tmp_path):
    episode = build_episode(
        status=EpisodeStatus.RUNNING,
        step=EpisodeStep.UPDATING_STORY_BIBLE,
        stop_points={"afterOutline": True, "afterScript": True},
    )
    project = build_project()
    parts = build_runner(tmp_path, project, episode, [build_scene("s1", character_ids=["c1"])])
    parts.repository.find_characters_by_ids.return_value = {"c1": MAI}
    parts.runner.finish_worker_stage("e1", EpisodeStep.UPDATING_STORY_BIBLE)
    return SimpleNamespace(parts=parts, project=project)


@pytest.fixture(
    params=[
        ("e1", EpisodeStatus.PAUSED, EpisodeStep.WRITING_OUTLINE, EpisodeStep.WRITING_OUTLINE),
        ("e1", EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT, EpisodeStep.WRITING_OUTLINE),
        (
            "e1",
            EpisodeStatus.FAILED,
            EpisodeStep.UPDATING_STORY_BIBLE,
            EpisodeStep.UPDATING_STORY_BIBLE,
        ),
        (
            "unknown",
            EpisodeStatus.RUNNING,
            EpisodeStep.UPDATING_STORY_BIBLE,
            EpisodeStep.UPDATING_STORY_BIBLE,
        ),
    ]
)
def ignored_stage_finish(request, tmp_path):
    episode_id, status, step, finished_step = request.param
    episode = build_episode(status=status, step=step)
    parts = build_runner(tmp_path, build_project(), episode, [])
    parts.runner.finish_worker_stage(episode_id, finished_step)
    return parts


@pytest.fixture(
    params=[
        (EpisodeStatus.PAUSED, EpisodeStageRunner.continue_episode),
        (EpisodeStatus.FAILED, EpisodeStageRunner.resume),
    ]
)
def restarted_without_a_step(request, tmp_path):
    status, restart = request.param
    parts = build_runner(tmp_path, build_project(), build_episode(status=status, step=None), [])
    episode = restart(parts.runner, parts.context)
    return SimpleNamespace(parts=parts, episode=episode)


@pytest.fixture(params=[EpisodeStatus.PAUSED, EpisodeStatus.FAILED, EpisodeStatus.DONE])
def rewritten_part(request, tmp_path):
    episode = build_episode(
        status=request.param,
        step=EpisodeStep.GENERATING_SCENE_IMAGES,
        paused_stop_point=EpisodeStep.WRITING_SCRIPT,
        finished_at=utc_now(),
        error_message="1 scene image(s) failed — fix them and resume",
    )
    parts = build_runner(tmp_path, build_project(), episode, [])
    parts.repository.find_part_scenes.return_value = [
        build_scene("s3", part_id="pt2"),
        build_scene("s4", part_id="pt2"),
    ]
    part_scene_dirs = [parts.files.scene_dir("p1", "e1", scene_id) for scene_id in ("s3", "s4")]
    other_scene_dir = parts.files.scene_dir("p1", "e1", "s1")
    for scene_dir in [*part_scene_dirs, other_scene_dir]:
        scene_dir.mkdir(parents=True)
    rewritten = parts.runner.rewrite_part(parts.part_context)
    return SimpleNamespace(
        parts=parts,
        episode=rewritten,
        has_part_scene_dirs=any(scene_dir.exists() for scene_dir in part_scene_dirs),
        has_other_scene_dir=other_scene_dir.exists(),
    )


@pytest.fixture(
    params=[
        PartRewriteCase(
            "Cannot rewrite a part of episode 1 while it is draft",
            episode_status=EpisodeStatus.DRAFT,
        ),
        PartRewriteCase(
            "Cannot rewrite a part of episode 1 while it is running",
            episode_status=EpisodeStatus.RUNNING,
        ),
        PartRewriteCase(
            "Film project p1 is archived",
            project_values={"status": ProjectStatus.ARCHIVED},
        ),
        PartRewriteCase(
            "Pick a narrator voice for the project or turn narration off",
            project_values={"narrator_voice_id": None},
        ),
        PartRewriteCase(
            "Episode 1 has generation running",
            open_requests=(
                GenerationRequest(
                    id="r1",
                    kind=GenerationKind.SCENE_IMAGE,
                    episode_id="e1",
                    scene_id="s1",
                    status=GenerationStatus.PROCESSING,
                ),
            ),
        ),
        PartRewriteCase(
            PART_BLOCKED_MESSAGE,
            part_scenes=(
                build_scene("s3", part_id="pt2"),
                build_scene("s4", part_id="pt2", image_path="projects/p1/s4/image.png"),
            ),
        ),
        PartRewriteCase(
            PART_BLOCKED_MESSAGE,
            part_scenes=(build_scene("s3", part_id="pt2", clip_path="projects/p1/s3/clip.mp4"),),
        ),
    ]
)
def refused_part_rewrite(request, tmp_path):
    case = request.param
    project = build_project(**case.project_values)
    parts = build_runner(tmp_path, project, build_episode(status=case.episode_status), [])
    parts.repository.find_open_requests_for_episode.return_value = list(case.open_requests)
    parts.repository.find_part_scenes.return_value = list(case.part_scenes)
    with pytest.raises(FilmConflictError) as error:
        parts.runner.rewrite_part(parts.part_context)
    return SimpleNamespace(outcome=Outcome(str(error.value), case.expected), parts=parts)


def test_assemble_runs_the_audio_stage_from_done(assembled_with_audio):
    episode = assembled_with_audio.episode
    assert (episode.status, episode.step, episode.finished_at) == (
        EpisodeStatus.RUNNING,
        EpisodeStep.GENERATING_AUDIO,
        None,
    )


def test_assemble_queues_the_missing_narration_only(assembled_with_audio):
    calls = assembled_with_audio.parts.media_queue.queue_narration.call_args_list
    assert [(call.args[0].scene.id, call.args[1]) for call in calls] == [("s1", VOICE)]


def test_assemble_asks_for_music_as_long_as_the_kept_clips(assembled_with_audio):
    call = assembled_with_audio.parts.media_queue.queue_music.call_args
    assert call.args[2] == 7 + 4 + 7


def test_audio_stage_waits_while_an_item_is_still_none(assembled_with_audio):
    assembled_with_audio.parts.notify_step_worker.assert_not_called()


def test_assemble_without_audio_moves_straight_to_assembling(assembled_without_audio):
    assert assembled_without_audio.episode.step is EpisodeStep.ASSEMBLING
    assembled_without_audio.notify_step_worker.assert_called_once_with()
    assembled_without_audio.media_queue.queue_narration.assert_not_called()
    assembled_without_audio.media_queue.queue_music.assert_not_called()


def test_failed_narration_and_music_are_counted_together(failed_audio):
    assert (failed_audio.status, failed_audio.error_message) == (
        EpisodeStatus.FAILED,
        "1 narration(s) and 1 music track(s) failed — fix them and resume",
    )


def test_a_project_request_moves_every_running_episode_of_the_project(project_wide_final):
    assert [call.args for call in project_wide_final.runner.advance.call_args_list] == [
        ("e7",),
        ("e8",),
    ]


def test_advance_ignores_worker_steps_paused_and_unstarted_episodes(idle_advance):
    assert idle_advance.moved is False
    idle_advance.parts.media_queue.assert_not_called()


def test_advance_ignores_a_missing_episode(missing_episode_advance):
    assert missing_episode_advance is False


def test_worker_results_do_not_touch_an_episode_that_stopped(worker_results_on_a_paused_episode):
    worker_results_on_a_paused_episode.repository.update_episode.assert_not_called()


def test_a_stage_of_a_missing_project_raises(missing_project_error):
    assert missing_project_error.args == ("gone",)


def test_finishing_the_outline_pauses_only_at_a_new_after_outline_stop(finished_outline):
    assert finished_outline.actual == finished_outline.expected


def test_finishing_the_story_bible_runs_the_reference_stage(finished_story_bible):
    episode = finished_story_bible.parts.episode
    assert (episode.status, episode.step, episode.paused_stop_point) == (
        EpisodeStatus.RUNNING,
        EpisodeStep.GENERATING_REFERENCES,
        None,
    )
    finished_story_bible.parts.media_queue.queue_character_image.assert_called_once_with(
        finished_story_bible.project, MAI, "e1"
    )


def test_a_stage_finish_for_an_episode_not_running_at_that_step_is_ignored(
    ignored_stage_finish,
):
    ignored_stage_finish.repository.update_episode.assert_not_called()
    ignored_stage_finish.notify_step_worker.assert_not_called()


def test_continue_and_resume_without_a_step_run_from_the_outline(restarted_without_a_step):
    assert (restarted_without_a_step.episode.status, restarted_without_a_step.episode.step) == (
        EpisodeStatus.RUNNING,
        EpisodeStep.WRITING_OUTLINE,
    )
    restarted_without_a_step.parts.notify_step_worker.assert_called_once_with()


def test_rewrite_part_clears_the_script_of_that_part_only(rewritten_part):
    rewritten_part.parts.repository.find_part_scenes.assert_called_once_with("pt2")
    rewritten_part.parts.repository.clear_part_script.assert_called_once_with("pt2")
    rewritten_part.parts.repository.delete_script.assert_not_called()


def test_rewrite_part_deletes_the_scene_folders_of_that_part_only(rewritten_part):
    assert (rewritten_part.has_part_scene_dirs, rewritten_part.has_other_scene_dir) == (
        False,
        True,
    )


def test_rewrite_part_runs_from_writing_the_script(rewritten_part):
    episode = rewritten_part.episode
    assert (
        episode.status,
        episode.step,
        episode.finished_at,
        episode.paused_stop_point,
        episode.error_message,
    ) == (EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT, None, None, None)


def test_rewrite_part_wakes_the_step_worker(rewritten_part):
    rewritten_part.parts.notify_step_worker.assert_called_once_with()


def test_rewrite_part_is_refused_with_its_reason(refused_part_rewrite):
    assert refused_part_rewrite.outcome.actual == refused_part_rewrite.outcome.expected


def test_a_refused_part_rewrite_changes_nothing(refused_part_rewrite):
    refused_part_rewrite.parts.repository.clear_part_script.assert_not_called()
    refused_part_rewrite.parts.repository.update_episode.assert_not_called()
    refused_part_rewrite.parts.notify_step_worker.assert_not_called()
