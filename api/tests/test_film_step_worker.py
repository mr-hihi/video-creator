import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import Command
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import Episode, EpisodeStatus, EpisodeStep, Scene
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import AssembledFilm, EpisodeStageRunner
from app.modules.films.step_commands import EpisodeStepCommands
from app.modules.films.step_worker import EpisodeStepRunner, EpisodeStepTools

FILM = AssembledFilm(
    video_path="projects/p1/episodes/e1/output/x.mp4", subtitles_path=None, duration_ms=9000
)


def build_episode(step: EpisodeStep) -> Episode:
    return Episode(id="e1", status=EpisodeStatus.RUNNING, step=step)


def build_worker(worker_episodes, generation_episodes=(), scenes=()):
    repository = MagicMock(spec=FilmRepository)
    repository.find_running_episodes.side_effect = lambda steps: (
        list(worker_episodes) if EpisodeStep.WRITING_SCRIPT in steps else list(generation_episodes)
    )
    repository.find_scenes.return_value = list(scenes)
    stage_runner = MagicMock(spec=EpisodeStageRunner)
    stage_runner.advance.return_value = False
    script_writer = MagicMock()
    assembler = MagicMock()
    assembler.assemble.return_value = FILM
    commands = EpisodeStepCommands()
    worker = EpisodeStepRunner(
        EpisodeStepTools(
            repository=repository,
            stage_runner=stage_runner,
            script_writer=script_writer,
            assembler=assembler,
            commands=commands,
        )
    )
    return SimpleNamespace(
        worker=worker,
        repository=repository,
        stage_runner=stage_runner,
        script_writer=script_writer,
        assembler=assembler,
        commands=commands,
    )


def never_stopping() -> bool:
    return False


def always_stopping() -> bool:
    return True


@pytest.fixture
def script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)])
    had_work = parts.worker.run_next(never_stopping)
    return SimpleNamespace(parts=parts, had_work=had_work)


@pytest.fixture
def script_run_with_scenes():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)], scenes=[Scene(id="s1")])
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def failed_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)])
    parts.script_writer.write_script.side_effect = EpisodeStepFailedError(
        "claude returned no scenes"
    )
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def crashed_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)])
    parts.script_writer.write_script.side_effect = KeyError("scenes")
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def interrupted_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)])
    parts.script_writer.write_script.side_effect = EpisodeStepFailedError("claude failed: killed")
    parts.worker.run_next(always_stopping)
    return parts


@pytest.fixture
def stopped_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)])

    def stop_then_run_claude(episode_id: str) -> None:
        parts.commands.cancel(episode_id)
        parts.commands.run(Command(args=[sys.executable, "-c", "pass"], timeout_sec=10))

    parts.script_writer.write_script.side_effect = stop_then_run_claude
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def assembly_run():
    parts = build_worker([build_episode(EpisodeStep.ASSEMBLING)])
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def failed_assembly_run():
    parts = build_worker([build_episode(EpisodeStep.ASSEMBLING)])
    parts.assembler.assemble.side_effect = EpisodeStepFailedError("Scene 2 has no clip")
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def stalled_stage_run():
    parts = build_worker([], generation_episodes=[build_episode(EpisodeStep.GENERATING_CLIPS)])
    parts.stage_runner.advance.return_value = True
    had_work = parts.worker.run_next(never_stopping)
    return SimpleNamespace(parts=parts, had_work=had_work)


@pytest.fixture
def idle_run():
    parts = build_worker([], generation_episodes=[build_episode(EpisodeStep.GENERATING_CLIPS)])
    return parts.worker.run_next(never_stopping)


def test_script_step_writes_then_finishes(script_run):
    assert script_run.had_work is True
    script_run.parts.script_writer.write_script.assert_called_once_with("e1")
    script_run.parts.stage_runner.finish_script.assert_called_once_with("e1")


def test_script_step_with_scenes_skips_claude(script_run_with_scenes):
    script_run_with_scenes.script_writer.write_script.assert_not_called()
    script_run_with_scenes.stage_runner.finish_script.assert_called_once_with("e1")


def test_failed_script_fails_the_step_with_its_message(failed_script_run):
    failed_script_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT, "claude returned no scenes"
    )


def test_unexpected_error_fails_the_step_with_its_text(crashed_script_run):
    crashed_script_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT, "'scenes'"
    )


def test_shutdown_leaves_the_step_running(interrupted_script_run):
    interrupted_script_run.stage_runner.fail_worker_step.assert_not_called()
    interrupted_script_run.stage_runner.finish_script.assert_not_called()


def test_stop_during_a_step_stops_its_commands(stopped_script_run):
    stopped_script_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT, f"{sys.executable} was stopped with the episode"
    )


def test_assembly_step_finishes_with_the_film(assembly_run):
    assembly_run.stage_runner.finish_assembly.assert_called_once_with("e1", FILM)


def test_failed_assembly_fails_the_step(failed_assembly_run):
    failed_assembly_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.ASSEMBLING, "Scene 2 has no clip"
    )


def test_stalled_generation_stage_is_advanced(stalled_stage_run):
    assert stalled_stage_run.had_work is True
    stalled_stage_run.parts.stage_runner.advance.assert_called_once_with("e1")


def test_nothing_to_do_reports_idle(idle_run):
    assert idle_run is False
