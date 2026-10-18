from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.films.film_access import EpisodeContext
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue
from app.modules.films.models import (
    Episode,
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
from app.modules.media_generation.models import GenerationKind, GenerationRequest
from app.modules.media_generation.service import GenerationService

UPLOAD_MAX_MB = 20
VOICE = VoiceTemplate(id="v1", name="narrator-en")
FILM = AssembledFilm("projects/p1/episodes/e1/output/film.mp4", None, 9000)


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


def build_scene(scene_id: str, **values) -> Scene:
    defaults = {
        "id": scene_id,
        "episode_id": "e1",
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
    media_queue = MagicMock(spec=FilmMediaQueue)
    notify_step_worker = MagicMock()
    runner = EpisodeStageRunner(
        StageRunnerTools(
            repository=repository,
            files=FilmFiles(tmp_path, UPLOAD_MAX_MB),
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
        context=EpisodeContext(project=project, episode=episode),
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
        build_episode(status=EpisodeStatus.RUNNING, step=EpisodeStep.WRITING_SCRIPT),
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
    parts.runner.finish_script("e1")
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
