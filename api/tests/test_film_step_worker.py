import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from app.common.process import Command
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import Episode, EpisodePart, EpisodeStatus, EpisodeStep
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import (
    AssembledFilm,
    EpisodeAssembler,
    EpisodeStageRunner,
    OutlineWriter,
    ScriptWriter,
    StoryBibleUpdater,
)
from app.modules.films.step_commands import EpisodeStepCommands
from app.modules.films.step_worker import EpisodeStepRunner, EpisodeStepTools

FILM = AssembledFilm(
    video_path="projects/p1/episodes/e1/output/x.mp4", subtitles_path=None, duration_ms=9000
)
THREE_PARTS = ("pt1", "pt2", "pt3")


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_episode(step: EpisodeStep | None) -> Episode:
    return Episode(id="e1", status=EpisodeStatus.RUNNING, step=step)


def build_parts(part_ids) -> list[EpisodePart]:
    return [
        EpisodePart(id=part_id, episode_id="e1", position=position)
        for position, part_id in enumerate(part_ids)
    ]


def build_worker(
    worker_episodes,
    generation_episodes=(),
    part_ids=(),
    scene_counts_by_part_id=None,
):
    repository = MagicMock(spec=FilmRepository)
    repository.find_running_episodes.side_effect = lambda steps: (
        list(worker_episodes) if EpisodeStep.WRITING_SCRIPT in steps else list(generation_episodes)
    )
    repository.find_parts.return_value = build_parts(part_ids)
    repository.count_scenes_by_part.return_value = dict(scene_counts_by_part_id or {})
    stage_runner = MagicMock(spec=EpisodeStageRunner)
    stage_runner.advance.return_value = False
    outline_writer = MagicMock(spec=OutlineWriter)
    script_writer = MagicMock(spec=ScriptWriter)
    story_bible_updater = MagicMock(spec=StoryBibleUpdater)
    assembler = MagicMock(spec=EpisodeAssembler)
    assembler.assemble.return_value = FILM
    commands = EpisodeStepCommands()
    worker = EpisodeStepRunner(
        EpisodeStepTools(
            repository=repository,
            stage_runner=stage_runner,
            outline_writer=outline_writer,
            script_writer=script_writer,
            story_bible_updater=story_bible_updater,
            assembler=assembler,
            commands=commands,
        )
    )
    return SimpleNamespace(
        worker=worker,
        repository=repository,
        stage_runner=stage_runner,
        outline_writer=outline_writer,
        script_writer=script_writer,
        story_bible_updater=story_bible_updater,
        assembler=assembler,
        commands=commands,
    )


def never_stopping() -> bool:
    return False


def always_stopping() -> bool:
    return True


@pytest.fixture(params=[EpisodeStep.WRITING_OUTLINE, None])
def outline_run(request):
    parts = build_worker([build_episode(request.param)])
    had_work = parts.worker.run_next(never_stopping)
    return SimpleNamespace(parts=parts, had_work=had_work)


@pytest.fixture
def outline_run_with_parts():
    parts = build_worker([build_episode(EpisodeStep.WRITING_OUTLINE)], part_ids=["pt1"])
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def failed_outline_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_OUTLINE)])
    parts.outline_writer.write_outline.side_effect = EpisodeStepFailedError(
        "claude returned no parts"
    )
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def script_run():
    parts = build_worker(
        [build_episode(EpisodeStep.WRITING_SCRIPT)],
        part_ids=THREE_PARTS,
        scene_counts_by_part_id={"pt1": 2},
    )
    had_work = parts.worker.run_next(never_stopping)
    return SimpleNamespace(parts=parts, had_work=had_work)


@pytest.fixture
def script_run_with_every_part_written():
    parts = build_worker(
        [build_episode(EpisodeStep.WRITING_SCRIPT)],
        part_ids=THREE_PARTS,
        scene_counts_by_part_id={"pt1": 2, "pt2": 1, "pt3": 4},
    )
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def failed_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)], part_ids=["pt1"])
    parts.script_writer.write_part.side_effect = EpisodeStepFailedError(
        "Part 1: claude returned no scenes"
    )
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture(
    params=[
        (KeyError("scenes"), "'scenes'"),
        (RuntimeError(), "RuntimeError"),
    ]
)
def crashed_script_run(request):
    error, expected_message = request.param
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)], part_ids=["pt1"])
    parts.script_writer.write_part.side_effect = error
    parts.worker.run_next(never_stopping)
    return Outcome(parts.stage_runner.fail_worker_step.call_args_list, expected_message)


@pytest.fixture
def interrupted_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)], part_ids=["pt1"])
    parts.script_writer.write_part.side_effect = EpisodeStepFailedError("claude failed: killed")
    parts.worker.run_next(always_stopping)
    return parts


@pytest.fixture
def stopped_script_run():
    parts = build_worker([build_episode(EpisodeStep.WRITING_SCRIPT)], part_ids=["pt1"])

    def stop_then_run_claude(part_id: str) -> None:
        parts.commands.cancel("e1")
        parts.commands.run(Command(args=[sys.executable, "-c", "pass"], timeout_sec=10))

    parts.script_writer.write_part.side_effect = stop_then_run_claude
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def story_bible_run():
    parts = build_worker([build_episode(EpisodeStep.UPDATING_STORY_BIBLE)])
    parts.worker.run_next(never_stopping)
    return parts


@pytest.fixture
def failed_story_bible_run():
    parts = build_worker([build_episode(EpisodeStep.UPDATING_STORY_BIBLE)])
    parts.story_bible_updater.update_story_bible.side_effect = EpisodeStepFailedError(
        "claude returned an empty story bible"
    )
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


def test_outline_step_writes_the_outline_then_finishes(outline_run):
    assert outline_run.had_work is True
    outline_run.parts.outline_writer.write_outline.assert_called_once_with("e1")
    outline_run.parts.stage_runner.finish_worker_stage.assert_called_once_with(
        "e1", EpisodeStep.WRITING_OUTLINE
    )


def test_outline_step_with_parts_skips_the_outline_call(outline_run_with_parts):
    outline_run_with_parts.outline_writer.write_outline.assert_not_called()
    outline_run_with_parts.stage_runner.finish_worker_stage.assert_called_once_with(
        "e1", EpisodeStep.WRITING_OUTLINE
    )


def test_failed_outline_fails_the_step_with_its_message(failed_outline_run):
    failed_outline_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_OUTLINE, "claude returned no parts"
    )
    failed_outline_run.stage_runner.finish_worker_stage.assert_not_called()


def test_script_step_writes_only_the_first_part_without_scenes(script_run):
    assert script_run.had_work is True
    script_run.parts.repository.count_scenes_by_part.assert_called_once_with(["pt1", "pt2", "pt3"])
    script_run.parts.script_writer.write_part.assert_called_once_with("pt2")


def test_script_step_does_not_finish_after_writing_a_part(script_run):
    script_run.parts.stage_runner.finish_worker_stage.assert_not_called()


def test_script_step_finishes_once_every_part_has_scenes(script_run_with_every_part_written):
    script_run_with_every_part_written.script_writer.write_part.assert_not_called()
    script_run_with_every_part_written.stage_runner.finish_worker_stage.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT
    )


def test_failed_part_fails_the_step_with_its_message(failed_script_run):
    failed_script_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT, "Part 1: claude returned no scenes"
    )


def test_unexpected_error_fails_the_step_with_its_text_or_type(crashed_script_run):
    assert crashed_script_run.actual == [
        call("e1", EpisodeStep.WRITING_SCRIPT, crashed_script_run.expected)
    ]


def test_shutdown_leaves_the_step_running(interrupted_script_run):
    interrupted_script_run.stage_runner.fail_worker_step.assert_not_called()
    interrupted_script_run.stage_runner.finish_worker_stage.assert_not_called()


def test_stop_during_a_step_stops_its_commands(stopped_script_run):
    stopped_script_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.WRITING_SCRIPT, f"{sys.executable} was stopped with the episode"
    )


def test_story_bible_step_updates_the_bible_then_finishes(story_bible_run):
    story_bible_run.story_bible_updater.update_story_bible.assert_called_once_with("e1")
    story_bible_run.stage_runner.finish_worker_stage.assert_called_once_with(
        "e1", EpisodeStep.UPDATING_STORY_BIBLE
    )


def test_failed_story_bible_fails_the_step_without_finishing(failed_story_bible_run):
    failed_story_bible_run.stage_runner.fail_worker_step.assert_called_once_with(
        "e1", EpisodeStep.UPDATING_STORY_BIBLE, "claude returned an empty story bible"
    )
    failed_story_bible_run.stage_runner.finish_worker_stage.assert_not_called()


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
