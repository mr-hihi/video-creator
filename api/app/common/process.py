import queue
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO

STDERR_TAIL_CHARS = 2000
WATCH_CHECK_EVERY_SEC = 0.1


class CommandError(Exception):
    pass


@dataclass(frozen=True)
class Command:
    args: list[str]
    timeout_sec: float
    stdin_text: str = ""
    cwd: Path | None = None

    @property
    def program(self) -> str:
        return self.args[0]


@dataclass(frozen=True)
class CommandOutput:
    stdout: str
    stderr: str
    returncode: int


class CommandRunner:
    def __init__(self):
        self._running_processes: set[subprocess.Popen[str]] = set()
        self._lock = threading.Lock()

    def run(self, command: Command) -> str:
        process = self._start(command)
        try:
            stdout, stderr = process.communicate(command.stdin_text, timeout=command.timeout_sec)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.communicate()
            raise CommandError(
                f"{command.program} timed out after {command.timeout_sec}s"
            ) from error
        finally:
            self._forget(process)
        if process.returncode != 0:
            stderr_tail = stderr[-STDERR_TAIL_CHARS:].strip()
            raise CommandError(f"{command.program} exited with {process.returncode}: {stderr_tail}")
        return stdout

    def run_watched(
        self, command: Command, silence_limit_sec: float, on_output: Callable[[], None]
    ) -> CommandOutput:
        process = self._start(command)
        try:
            stdout, stderr = _watch_output(process, command, silence_limit_sec, on_output)
        finally:
            self._forget(process)
        return CommandOutput(stdout=stdout, stderr=stderr, returncode=process.returncode)

    def terminate_all(self) -> None:
        with self._lock:
            processes = list(self._running_processes)
        for process in processes:
            process.terminate()

    def _start(self, command: Command) -> subprocess.Popen[str]:
        try:
            process = subprocess.Popen(
                command.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=command.cwd,
            )
        except FileNotFoundError as error:
            raise CommandError(f"{command.program} is not installed or not on PATH") from error
        with self._lock:
            self._running_processes.add(process)
        return process

    def _forget(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._running_processes.discard(process)


def _watch_output(
    process: subprocess.Popen[str],
    command: Command,
    silence_limit_sec: float,
    on_output: Callable[[], None],
) -> tuple[str, str]:
    lines: queue.Queue[str | None] = queue.Queue()
    stderr_parts: list[str] = []
    _start_daemon(_write_stdin, process.stdin, command.stdin_text)
    _start_daemon(_read_lines, process.stdout, lines)
    stderr_reader = _start_daemon(_read_all, process.stderr, stderr_parts)
    output_lines: list[str] = []
    started_at = last_output_at = time.monotonic()
    while (line := _next_line(lines)) is not None:
        now = time.monotonic()
        if line:
            output_lines.append(line)
            last_output_at = now
            on_output()
        elif now - last_output_at > silence_limit_sec:
            _kill(process)
            raise CommandError(f"{command.program} stopped responding for {silence_limit_sec}s")
        if now - started_at > command.timeout_sec:
            _kill(process)
            raise CommandError(f"{command.program} timed out after {command.timeout_sec}s")
    process.wait()
    stderr_reader.join()
    return "".join(output_lines), "".join(stderr_parts)


def _next_line(lines: queue.Queue[str | None]) -> str | None:
    try:
        return lines.get(timeout=WATCH_CHECK_EVERY_SEC)
    except queue.Empty:
        return ""


def _start_daemon(target: Callable[..., None], *args: object) -> threading.Thread:
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def _write_stdin(stdin: IO[str], stdin_text: str) -> None:
    try:
        stdin.write(stdin_text)
        stdin.close()
    except OSError:
        return


def _read_lines(stream: IO[str], lines: queue.Queue[str | None]) -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


def _read_all(stream: IO[str], parts: list[str]) -> None:
    parts.append(stream.read())


def _kill(process: subprocess.Popen[str]) -> None:
    process.kill()
    process.wait()
