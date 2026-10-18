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
    ScriptWriter,
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
    script_writer: ScriptWriter
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
        step = episode.step or EpisodeStep.WRITING_SCRIPT
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
        if step is EpisodeStep.WRITING_SCRIPT:
            self._write_script(episode)
            return
        film = self._tools.assembler.assemble(episode.id)
        self._tools.stage_runner.finish_assembly(episode.id, film)

    def _write_script(self, episode: Episode) -> None:
        if not self._tools.repository.find_scenes(episode.id):
            self._tools.script_writer.write_script(episode.id)
        self._tools.stage_runner.finish_script(episode.id)

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
