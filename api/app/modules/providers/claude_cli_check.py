import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from app.common.process import Command, CommandError, CommandRunner

AUTH_STATUS_ARGS = ("auth", "status", "--json")
STATUS_MAX_AGE_SEC = 60.0
NOT_SIGNED_IN_ERROR = "Not signed in — run claude auth login"
NOT_FOUND_ERROR = "Claude CLI not found at '{claude_bin}'"


class ClaudeCliStatus(StrEnum):
    SIGNED_IN = "signedIn"
    NOT_SIGNED_IN = "notSignedIn"
    NOT_FOUND = "notFound"


@dataclass(frozen=True)
class ClaudeCliCheckConfig:
    claude_bin: str
    timeout_sec: float


class ClaudeCliCheck:
    def __init__(
        self,
        config: ClaudeCliCheckConfig,
        runner: CommandRunner,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._config = config
        self._runner = runner
        self._clock = clock
        self._lock = threading.Lock()
        self._last_status: ClaudeCliStatus | None = None
        self._checked_at = 0.0

    def check(self) -> ClaudeCliStatus:
        with self._lock:
            return self._check_now()

    def get_recent_status(self) -> ClaudeCliStatus:
        with self._lock:
            is_stale = self._clock() - self._checked_at >= STATUS_MAX_AGE_SEC
            if self._last_status is None or is_stale:
                return self._check_now()
            return self._last_status

    def describe_failure(self, status: ClaudeCliStatus) -> str | None:
        if status is ClaudeCliStatus.NOT_FOUND:
            return NOT_FOUND_ERROR.format(claude_bin=self._config.claude_bin)
        if status is ClaudeCliStatus.NOT_SIGNED_IN:
            return NOT_SIGNED_IN_ERROR
        return None

    def _check_now(self) -> ClaudeCliStatus:
        self._last_status = self._run_auth_status()
        self._checked_at = self._clock()
        return self._last_status

    def _run_auth_status(self) -> ClaudeCliStatus:
        try:
            stdout = self._runner.run(
                Command(
                    args=[self._config.claude_bin, *AUTH_STATUS_ARGS],
                    timeout_sec=self._config.timeout_sec,
                )
            )
        except CommandError as error:
            if isinstance(error.__cause__, FileNotFoundError):
                return ClaudeCliStatus.NOT_FOUND
            return ClaudeCliStatus.NOT_SIGNED_IN
        if is_logged_in(stdout):
            return ClaudeCliStatus.SIGNED_IN
        return ClaudeCliStatus.NOT_SIGNED_IN


def is_logged_in(auth_status_output: str) -> bool:
    try:
        auth_status = json.loads(auth_status_output)
    except json.JSONDecodeError:
        return False
    return isinstance(auth_status, dict) and auth_status.get("loggedIn") is True
