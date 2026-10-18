from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError, CommandRunner
from app.modules.providers.claude_cli_check import (
    ClaudeCliCheck,
    ClaudeCliCheckConfig,
    ClaudeCliStatus,
)

CONFIG = ClaudeCliCheckConfig(claude_bin="/opt/bin/claude", timeout_sec=15)


def to_missing_cli_error() -> CommandError:
    error = CommandError("/opt/bin/claude is not installed or not on PATH")
    error.__cause__ = FileNotFoundError("claude")
    return error


def build_check(run_result, clock_values=(0.0,)):
    runner = MagicMock(spec=CommandRunner)
    if isinstance(run_result, Exception):
        runner.run.side_effect = run_result
    else:
        runner.run.return_value = run_result
    clock = iter(clock_values)
    return SimpleNamespace(check=ClaudeCliCheck(CONFIG, runner, lambda: next(clock)), runner=runner)


@pytest.fixture(
    params=[
        ('{"loggedIn": true, "authMethod": "claude.ai"}', ClaudeCliStatus.SIGNED_IN),
        ('{"loggedIn": false}', ClaudeCliStatus.NOT_SIGNED_IN),
        ("[]", ClaudeCliStatus.NOT_SIGNED_IN),
        ("not json", ClaudeCliStatus.NOT_SIGNED_IN),
        (CommandError("/opt/bin/claude exited with 1: "), ClaudeCliStatus.NOT_SIGNED_IN),
        (to_missing_cli_error(), ClaudeCliStatus.NOT_FOUND),
    ]
)
def checked_status(request):
    run_result, expected = request.param
    return SimpleNamespace(actual=build_check(run_result).check.check(), expected=expected)


@pytest.fixture
def auth_status_command():
    rig = build_check('{"loggedIn": true}')
    rig.check.check()
    return rig.runner.run.call_args.args[0]


@pytest.fixture
def statuses_within_a_minute():
    rig = build_check('{"loggedIn": true}', clock_values=(0.0, 0.0, 30.0))
    return SimpleNamespace(
        statuses=[rig.check.get_recent_status(), rig.check.get_recent_status()],
        run_count=rig.runner.run.call_count,
    )


@pytest.fixture
def statuses_after_a_minute():
    rig = build_check('{"loggedIn": true}', clock_values=(0.0, 0.0, 60.0, 60.0))
    rig.check.get_recent_status()
    rig.check.get_recent_status()
    return rig.runner.run.call_count


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ClaudeCliStatus.SIGNED_IN, None),
        (ClaudeCliStatus.NOT_SIGNED_IN, "Not signed in — run claude auth login"),
        (ClaudeCliStatus.NOT_FOUND, "Claude CLI not found at '/opt/bin/claude'"),
    ],
)
def test_each_failed_status_has_a_message(status, expected):
    assert build_check("").check.describe_failure(status) == expected


def test_the_check_reads_the_auth_status_of_the_cli(checked_status):
    assert checked_status.actual == checked_status.expected


def test_the_check_runs_claude_auth_status_as_json_within_the_test_limit(auth_status_command):
    assert auth_status_command.args == ["/opt/bin/claude", "auth", "status", "--json"]
    assert auth_status_command.timeout_sec == 15


def test_a_recent_status_is_reused_within_a_minute(statuses_within_a_minute):
    assert statuses_within_a_minute.statuses == [ClaudeCliStatus.SIGNED_IN] * 2
    assert statuses_within_a_minute.run_count == 1


def test_a_status_older_than_a_minute_is_checked_again(statuses_after_a_minute):
    assert statuses_after_a_minute == 2
