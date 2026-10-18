import base64
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.common.process import CommandError, CommandOutput, CommandRunner
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AttachedImage
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.claude_cli_client import ClaudeCliClient, ClaudeCliConfig

CONFIG = ClaudeCliConfig(claude_bin="claude", image_encoding=AiImageEncoding(480, 60))
LIMITS = AiLimits(timeout_sec=600)
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}}}
JSON_ASK = AiAsk(instructions="Rules", message="Notes", reply_schema=SCHEMA)
TEXT_ASK = AiAsk(instructions="Rules", message="Notes")
LOCKED_DOWN_ARGS = ["--tools", "", "--no-session-persistence", "--setting-sources", ""]


def to_stdout(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events) + "\n"


def result_event(**values) -> dict:
    return {"type": "result", "is_error": False, **values}


def build_runner(stdout: str, returncode: int = 0, stderr: str = "") -> MagicMock:
    runner = MagicMock(spec=CommandRunner)
    runner.run.return_value = stdout
    runner.run_watched.return_value = CommandOutput(
        stdout=stdout, stderr=stderr, returncode=returncode
    )
    return runner


def capture_call_error(action) -> str:
    with pytest.raises(AiCallError) as caught:
        action()
    return str(caught.value)


@pytest.fixture
def json_run():
    runner = build_runner(
        to_stdout({"type": "system"}, result_event(structured_output={"title": "Tour"})) + "  \n"
    )
    reply = ClaudeCliClient(CONFIG, runner).ask_for_json("default", JSON_ASK, LIMITS)
    return SimpleNamespace(reply=reply, command=runner.run.call_args.args[0], runner=runner)


@pytest.fixture
def opus_command():
    runner = build_runner(to_stdout(result_event(result="## A")))
    ClaudeCliClient(CONFIG, runner).ask_for_text("opus", TEXT_ASK, LIMITS)
    return runner.run.call_args.args[0]


@pytest.fixture
def image_run(tmp_path):
    frame_path = tmp_path / "moment-01.png"
    Image.new("RGB", (1000, 500)).save(frame_path)
    runner = build_runner(to_stdout(result_event(result="## Character A")))
    ask = AiAsk(
        instructions="Rules",
        message="Notes",
        images=[AttachedImage(label="images/moment-01.jpg", path=frame_path)],
    )
    answer = ClaudeCliClient(CONFIG, runner).ask_for_text("default", ask, LIMITS)
    command = runner.run.call_args.args[0]
    event = json.loads(command.stdin_text)
    image_source = event["message"]["content"][2]["source"]
    with Image.open(io.BytesIO(base64.b64decode(image_source["data"]))) as sent_image:
        sent_size = sent_image.size
    return SimpleNamespace(
        answer=answer, command=command, event=event, source=image_source, sent_size=sent_size
    )


@pytest.fixture
def watched_run():
    outputs: list[str] = []
    runner = build_runner(to_stdout(result_event(structured_output={"assets": []})))
    limits = AiLimits(
        timeout_sec=3600, silence_limit_sec=900, on_output=lambda: outputs.append("output")
    )
    reply = ClaudeCliClient(CONFIG, runner).ask_for_json("sonnet", JSON_ASK, limits)
    command, silence_limit_sec, on_output = runner.run_watched.call_args.args
    on_output()
    return SimpleNamespace(
        reply=reply,
        command=command,
        silence_limit_sec=silence_limit_sec,
        outputs=outputs,
        runner=runner,
    )


@pytest.fixture(
    params=[
        ("not json\n", "claude returned output that is not JSON"),
        (to_stdout({"type": "system"}), "claude returned no structured output"),
        (to_stdout(result_event(structured_output=[1])), "claude returned no structured output"),
        (to_stdout(result_event(is_error=True, result="Overloaded")), "claude failed: Overloaded"),
        (to_stdout(result_event(is_error=True)), "claude failed: unknown error"),
    ]
)
def json_failure(request):
    stdout, expected = request.param
    client = ClaudeCliClient(CONFIG, build_runner(stdout))
    return SimpleNamespace(
        actual=capture_call_error(lambda: client.ask_for_json("default", JSON_ASK, LIMITS)),
        expected=expected,
    )


@pytest.fixture(
    params=[
        (to_stdout({"type": "system"}), "claude returned no result"),
        (to_stdout(result_event(result="   ")), "claude returned an empty answer"),
        (to_stdout(result_event()), "claude returned an empty answer"),
    ]
)
def text_failure(request):
    stdout, expected = request.param
    client = ClaudeCliClient(CONFIG, build_runner(stdout))
    return SimpleNamespace(
        actual=capture_call_error(lambda: client.ask_for_text("default", TEXT_ASK, LIMITS)),
        expected=expected,
    )


@pytest.fixture(
    params=[
        (CommandOutput(stdout="", stderr="  boom  ", returncode=1), "claude exited with 1: boom"),
        (
            CommandOutput(
                stdout=to_stdout(result_event(is_error=True, result="API Error: 529")),
                stderr="",
                returncode=1,
            ),
            "claude failed: API Error: 529",
        ),
    ]
)
def watched_exit_failure(request):
    output, expected = request.param
    runner = MagicMock(spec=CommandRunner)
    runner.run_watched.return_value = output
    limits = AiLimits(timeout_sec=3600, silence_limit_sec=900)
    client = ClaudeCliClient(CONFIG, runner)
    return SimpleNamespace(
        actual=capture_call_error(lambda: client.ask_for_json("default", JSON_ASK, limits)),
        expected=expected,
    )


@pytest.fixture
def command_error_message():
    runner = MagicMock(spec=CommandRunner)
    runner.run.side_effect = CommandError("claude timed out after 600s")
    client = ClaudeCliClient(CONFIG, runner)
    return capture_call_error(lambda: client.ask_for_text("default", TEXT_ASK, LIMITS))


def test_a_call_without_images_streams_json_out_and_sends_the_message_as_text(json_run):
    assert json_run.command.args == [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
        json.dumps(SCHEMA),
        "--system-prompt",
        "Rules",
        *LOCKED_DOWN_ARGS,
    ]
    assert json_run.command.stdin_text == "Notes"


def test_the_cli_runs_outside_the_repo_within_the_limit(json_run):
    assert json_run.command.cwd == Path(tempfile.gettempdir())
    assert json_run.command.timeout_sec == 600
    json_run.runner.run_watched.assert_not_called()


def test_the_structured_output_of_the_last_result_event_is_the_reply(json_run):
    assert json_run.reply == {"title": "Tour"}


def test_a_chosen_model_is_passed_and_a_text_step_sends_no_schema(opus_command):
    assert opus_command.args[-2:] == ["--model", "opus"]
    assert "--json-schema" not in opus_command.args


def test_a_call_with_images_sends_one_stream_json_user_event(image_run):
    assert image_run.command.args[5:7] == ["--input-format", "stream-json"]
    assert [part["type"] for part in image_run.event["message"]["content"]] == [
        "text",
        "text",
        "image",
    ]
    assert image_run.event["message"]["content"][1]["text"] == "images/moment-01.jpg"


def test_each_image_is_scaled_before_it_is_sent(image_run):
    assert (image_run.source["media_type"], image_run.sent_size) == ("image/jpeg", (480, 240))


def test_a_markdown_step_answers_the_trimmed_result(image_run):
    assert image_run.answer == "## Character A"


def test_a_watched_call_streams_partial_messages_and_reports_output(watched_run):
    assert "--include-partial-messages" in watched_run.command.args
    assert watched_run.command.args[-2:] == ["--model", "sonnet"]
    assert (watched_run.command.timeout_sec, watched_run.silence_limit_sec) == (3600, 900)
    assert watched_run.outputs == ["output"]
    assert watched_run.reply == {"assets": []}
    watched_run.runner.run.assert_not_called()


def test_a_structured_step_reports_each_bad_reply(json_failure):
    assert json_failure.actual == json_failure.expected


def test_a_markdown_step_reports_each_bad_reply(text_failure):
    assert text_failure.actual == text_failure.expected


def test_a_failed_exit_reports_the_result_error_or_the_exit_code(watched_exit_failure):
    assert watched_exit_failure.actual == watched_exit_failure.expected


def test_a_command_error_fails_the_call_with_its_message(command_error_message):
    assert command_error_message == "claude timed out after 600s"
