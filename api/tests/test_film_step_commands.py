import sys
import threading
import time
from types import SimpleNamespace

import pytest

from app.common.process import Command, CommandError
from app.modules.films.step_commands import EpisodeStepCommands

LONG_SLEEP_SEC = 30
STARTED_WAIT_SEC = 10
LONG_COMMAND = Command(
    args=[
        sys.executable,
        "-c",
        f"import time; print('started', flush=True); time.sleep({LONG_SLEEP_SEC})",
    ],
    timeout_sec=LONG_SLEEP_SEC * 2,
)
QUICK_COMMAND = Command(args=[sys.executable, "-c", "print('done')"], timeout_sec=10)


def capture_command_error(action) -> str:
    with pytest.raises(CommandError) as caught:
        action()
    return str(caught.value)


@pytest.fixture
def commands():
    return EpisodeStepCommands()


@pytest.fixture
def killed_run(commands):
    started = threading.Event()
    outcome = SimpleNamespace(output=None)

    def run_step() -> None:
        with commands.running("e1"):
            outcome.output = commands.run_watched(LONG_COMMAND, LONG_SLEEP_SEC, started.set)

    began_at = time.monotonic()
    worker = threading.Thread(target=run_step)
    worker.start()
    started.wait(STARTED_WAIT_SEC)
    commands.cancel("e1")
    worker.join(LONG_SLEEP_SEC)
    outcome.elapsed_sec = time.monotonic() - began_at
    return outcome


@pytest.fixture
def run_after_cancel(commands):
    with commands.running("e1"):
        commands.cancel("e1")
        return capture_command_error(lambda: commands.run(QUICK_COMMAND))


@pytest.fixture
def run_after_other_cancel(commands):
    with commands.running("e1"):
        commands.cancel("e2")
        return commands.run(QUICK_COMMAND)


@pytest.fixture
def run_in_next_step(commands):
    with commands.running("e1"):
        commands.cancel("e1")
    with commands.running("e2"):
        return commands.run(QUICK_COMMAND)


@pytest.fixture
def run_after_step_cancel(commands):
    with commands.running("e1"):
        pass
    commands.cancel("e1")
    with commands.running("e1"):
        return commands.run(QUICK_COMMAND)


def test_cancel_kills_the_running_command(killed_run):
    assert (killed_run.output.returncode != 0, killed_run.elapsed_sec < LONG_SLEEP_SEC) == (
        True,
        True,
    )


def test_a_command_after_cancel_is_refused(run_after_cancel):
    assert run_after_cancel == f"{sys.executable} was stopped with the episode"


def test_cancel_of_another_episode_changes_nothing(run_after_other_cancel):
    assert run_after_other_cancel == "done\n"


def test_the_next_step_runs_its_commands(run_in_next_step):
    assert run_in_next_step == "done\n"


def test_cancel_between_steps_changes_nothing(run_after_step_cancel):
    assert run_after_step_cancel == "done\n"
