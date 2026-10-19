import logging
from collections.abc import Callable
from dataclasses import dataclass

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import Episode, EpisodeStep
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import (
    WORKER_STEPS,
    EpisodeAssembler,
    EpisodeStageRunner,
    OutlineWriter,
    ScriptWriter,
    StoryBibleUpdater,
)
from app.modules.films.step_commands import EpisodeStepCommands

GENERATION_STEPS = frozenset(
    {
        EpisodeStep.GENERATING_REFERENCES,
        EpisodeStep.GENERATING_SCENE_IMAGES,
        EpisodeStep.GENERATING_CLIPS,
        EpisodeStep.GENERATING_AUDIO,
    }
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EpisodeStepTools:
    repository: FilmRepository
    stage_runner: EpisodeStageRunner
    outline_writer: OutlineWriter
    script_writer: ScriptWriter
    story_bible_updater: StoryBibleUpdater
    assembler: EpisodeAssembler
    commands: EpisodeStepCommands


class EpisodeStepRunner:
    def __init__(self, tools: EpisodeStepTools):
        self._tools = tools

    def run_next(self, is_stopping: Callable[[], bool]) -> bool:
        worker_episodes = self._tools.repository.find_running_episodes(WORKER_STEPS)
        if worker_episodes:
            self._run_step(worker_episodes[0], is_stopping)
            return True
        return self._advance_stalled_stages()

    def _run_step(self, episode: Episode, is_stopping: Callable[[], bool]) -> None:
        step = episode.step or EpisodeStep.WRITING_OUTLINE
        logger.info("Episode %s step %s started", episode.id, step)
        try:
            with self._tools.commands.running(episode.id):
                self._run_worker_step(episode, step)
        except Exception as error:
            if is_stopping():
                logger.warning("Episode %s step %s interrupted by shutdown", episode.id, step)
                return
            self._fail(episode, step, error)
            return
        logger.info("Episode %s step %s finished", episode.id, step)

    def _run_worker_step(self, episode: Episode, step: EpisodeStep) -> None:
        if step is EpisodeStep.WRITING_OUTLINE:
            self._write_outline(episode)
        elif step is EpisodeStep.WRITING_SCRIPT:
            self._write_next_part(episode)
        elif step is EpisodeStep.UPDATING_STORY_BIBLE:
            self._tools.story_bible_updater.update_story_bible(episode.id)
            self._tools.stage_runner.finish_worker_stage(episode.id, step)
        else:
            film = self._tools.assembler.assemble(episode.id)
            self._tools.stage_runner.finish_assembly(episode.id, film)

    def _write_outline(self, episode: Episode) -> None:
        if not self._tools.repository.find_parts(episode.id):
            self._tools.outline_writer.write_outline(episode.id)
        self._tools.stage_runner.finish_worker_stage(episode.id, EpisodeStep.WRITING_OUTLINE)

    def _write_next_part(self, episode: Episode) -> None:
        parts = self._tools.repository.find_parts(episode.id)
        scene_counts_by_part_id = self._tools.repository.count_scenes_by_part(
            [part.id for part in parts]
        )
        unwritten_parts = [part for part in parts if not scene_counts_by_part_id.get(part.id)]
        if unwritten_parts:
            self._tools.script_writer.write_part(unwritten_parts[0].id)
            return
        self._tools.stage_runner.finish_worker_stage(episode.id, EpisodeStep.WRITING_SCRIPT)

    def _fail(self, episode: Episode, step: EpisodeStep, error: Exception) -> None:
        if isinstance(error, EpisodeStepFailedError):
            error_message = str(error)
        else:
            logger.exception("Episode %s step %s raised", episode.id, step)
            error_message = str(error) or type(error).__name__
        self._tools.stage_runner.fail_worker_step(episode.id, step, error_message)

    def _advance_stalled_stages(self) -> bool:
        return any(
            self._tools.stage_runner.advance(episode.id)
            for episode in self._tools.repository.find_running_episodes(GENERATION_STEPS)
        )
