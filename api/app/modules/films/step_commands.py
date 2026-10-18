import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.common.process import Command, CommandError, CommandOutput, CommandRunner

STOPPED_MESSAGE = "{program} was stopped with the episode"

logger = logging.getLogger(__name__)


class EpisodeStepCommands(CommandRunner):
    def __init__(self):
        super().__init__()
        self._step_lock = threading.Lock()
        self._episode_id: str | None = None
        self._is_cancelled = False

    @contextmanager
    def running(self, episode_id: str) -> Iterator[None]:
        with self._step_lock:
            self._episode_id = episode_id
            self._is_cancelled = False
        try:
            yield
        finally:
            with self._step_lock:
                self._episode_id = None

    def cancel(self, episode_id: str) -> None:
        with self._step_lock:
            if self._episode_id != episode_id:
                return
            self._is_cancelled = True
            self.terminate_all()
        logger.info("Episode %s worker step stopped by the user", episode_id)

    def run(self, command: Command) -> str:
        self._ensure_not_cancelled(command)
        return super().run(command)

    def run_watched(
        self, command: Command, silence_limit_sec: float, on_output: Callable[[], None]
    ) -> CommandOutput:
        self._ensure_not_cancelled(command)
        return super().run_watched(command, silence_limit_sec, on_output)

    def _ensure_not_cancelled(self, command: Command) -> None:
        with self._step_lock:
            if self._is_cancelled:
                raise CommandError(STOPPED_MESSAGE.format(program=command.program))
