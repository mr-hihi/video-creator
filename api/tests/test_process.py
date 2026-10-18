import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import Command, CommandError, CommandRunner

REAL_POPEN = subprocess.Popen
COMMAND = Command(args=["whisper-cli", "-f", "audio.wav"], timeout_sec=5, stdin_text="input")


def build_process(stdout: str, stderr: str, returncode: int) -> MagicMock:
    process = MagicMock(spec=REAL_POPEN)
    process.communicate.return_value = (stdout, stderr)
    process.returncode = returncode
    return process


def capture_command_error(runner: CommandRunner) -> CommandError:
    with pytest.raises(CommandError) as caught:
        runner.run(COMMAND)
    return caught.value


@pytest.fixture
def popen(monkeypatch):
    popen_mock = MagicMock()
    monkeypatch.setattr("app.common.process.subprocess.Popen", popen_mock)
    return popen_mock


@pytest.fixture
def runner():
    return CommandRunner()


@pytest.fixture
def successful_process(popen):
    popen.return_value = build_process("done", "", 0)
    return popen.return_value


@pytest.fixture
def successful_stdout(runner, successful_process):
    return runner.run(COMMAND)


@pytest.fixture
def exit_error(runner, popen):
    popen.return_value = build_process("", "model not found\n", 2)
    return capture_command_error(runner)


@pytest.fixture
def timed_out_process(popen):
    process = build_process("", "", -9)
    process.communicate.side_effect = [subprocess.TimeoutExpired("whisper-cli", 5), ("", "")]
    popen.return_value = process
    return process


@pytest.fixture
def timeout_error(runner, timed_out_process):
    return capture_command_error(runner)


@pytest.fixture
def missing_program_error(runner, popen):
    popen.side_effect = FileNotFoundError("whisper-cli")
    return capture_command_error(runner)


@pytest.fixture
def process_terminated_mid_run(runner, popen):
    process = build_process("", "", 0)
    process.communicate.side_effect = lambda stdin_text, timeout: (
        runner.terminate_all() or ("partial", "")
    )
    popen.return_value = process
    runner.run(COMMAND)
    return process


@pytest.fixture
def process_after_finished_run(runner, successful_process, successful_stdout):
    runner.terminate_all()
    return successful_process


def test_run_returns_stdout_on_success(successful_stdout):
    assert successful_stdout == "done"


def test_run_sends_stdin_and_timeout(successful_process, successful_stdout):
    successful_process.communicate.assert_called_once_with("input", timeout=5)


def test_run_raises_with_exit_code_and_stderr_tail(exit_error):
    assert str(exit_error) == "whisper-cli exited with 2: model not found"


def test_run_kills_process_on_timeout(timed_out_process, timeout_error):
    assert str(timeout_error) == "whisper-cli timed out after 5s"
    timed_out_process.kill.assert_called_once_with()


def test_run_raises_when_program_is_missing(missing_program_error):
    assert str(missing_program_error) == "whisper-cli is not installed or not on PATH"


def test_terminate_all_stops_a_running_process(process_terminated_mid_run):
    process_terminated_mid_run.terminate.assert_called_once_with()


def test_terminate_all_ignores_finished_processes(process_after_finished_run):
    process_after_finished_run.terminate.assert_not_called()


STEADY_OUTPUT_SCRIPT = (
    "import time\nfor number in range(8):\n    print(number, flush=True)\n    time.sleep(0.1)\n"
)
SILENT_SCRIPT = "import time\nprint('started', flush=True)\ntime.sleep(5)\n"
ENDLESS_OUTPUT_SCRIPT = (
    "import time\nwhile True:\n    print('tick', flush=True)\n    time.sleep(0.05)\n"
)
ECHO_STDIN_SCRIPT = "import sys\nprint(len(sys.stdin.read()))\n"
STDIN_IGNORING_SCRIPT = "print('done')\n"
LARGE_STDIN_TEXT = "x" * 2_000_000
FAILING_SCRIPT = (
    "import sys\n"
    'print(\'{"type": "result"}\', flush=True)\n'
    "sys.stderr.write('boom')\n"
    "sys.exit(1)\n"
)


def python_command(script: str, timeout_sec: float = 5, stdin_text: str = "") -> Command:
    return Command(
        args=[sys.executable, "-c", script], timeout_sec=timeout_sec, stdin_text=stdin_text
    )


def capture_watched_error(command: Command, silence_limit_sec: float) -> CommandError:
    with pytest.raises(CommandError) as caught:
        CommandRunner().run_watched(command, silence_limit_sec, lambda: None)
    return caught.value


@pytest.fixture
def steady_run():
    output_count = []
    output = CommandRunner().run_watched(
        python_command(STEADY_OUTPUT_SCRIPT), 0.5, lambda: output_count.append(1)
    )
    return SimpleNamespace(output=output, output_count=len(output_count))


@pytest.fixture
def silent_error():
    started_at = time.monotonic()
    error = capture_watched_error(python_command(SILENT_SCRIPT), 0.3)
    return SimpleNamespace(error=error, elapsed_sec=time.monotonic() - started_at)


@pytest.fixture
def endless_error():
    return capture_watched_error(python_command(ENDLESS_OUTPUT_SCRIPT, timeout_sec=0.5), 5)


@pytest.fixture
def echoed_stdin_output():
    return CommandRunner().run_watched(
        python_command(ECHO_STDIN_SCRIPT, stdin_text="abc"), 5, lambda: None
    )


@pytest.fixture
def stdin_ignored_output():
    return CommandRunner().run_watched(
        python_command(STDIN_IGNORING_SCRIPT, stdin_text=LARGE_STDIN_TEXT), 5, lambda: None
    )


@pytest.fixture
def failed_run_output():
    return CommandRunner().run_watched(python_command(FAILING_SCRIPT), 5, lambda: None)


@pytest.fixture
def missing_program_watched_error(popen):
    popen.side_effect = FileNotFoundError("claude")
    return capture_watched_error(Command(args=["claude"], timeout_sec=5), 5)


@pytest.fixture
def terminated_watched_output():
    runner = CommandRunner()
    stopper = threading.Timer(0.3, runner.terminate_all)
    stopper.start()
    output = runner.run_watched(python_command(ENDLESS_OUTPUT_SCRIPT), 5, lambda: None)
    stopper.join()
    return output


def test_run_watched_keeps_a_process_that_keeps_writing(steady_run):
    assert steady_run.output.stdout.split() == [str(number) for number in range(8)]
    assert steady_run.output.returncode == 0
    assert steady_run.output_count == 8


def test_run_watched_kills_a_process_silent_past_the_limit(silent_error):
    assert str(silent_error.error) == f"{sys.executable} stopped responding for 0.3s"
    assert silent_error.elapsed_sec < 3


def test_run_watched_kills_a_process_past_the_run_limit(endless_error):
    assert str(endless_error) == f"{sys.executable} timed out after 0.5s"


def test_run_watched_sends_stdin(echoed_stdin_output):
    assert echoed_stdin_output.stdout.strip() == "3"


def test_run_watched_finishes_when_the_process_ignores_stdin(stdin_ignored_output):
    assert stdin_ignored_output.stdout.strip() == "done"
    assert stdin_ignored_output.returncode == 0


def test_run_watched_returns_the_output_of_a_failed_process(failed_run_output):
    assert failed_run_output.returncode == 1
    assert failed_run_output.stdout.strip() == '{"type": "result"}'
    assert failed_run_output.stderr == "boom"


def test_run_watched_raises_when_program_is_missing(missing_program_watched_error):
    assert str(missing_program_watched_error) == "claude is not installed or not on PATH"


def test_terminate_all_stops_a_watched_process(terminated_watched_output):
    assert terminated_watched_output.returncode != 0
