import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.common.process import (
    STDERR_TAIL_CHARS,
    Command,
    CommandError,
    CommandOutput,
    CommandRunner,
)
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits
from app.modules.ai_models.ai_images import (
    AI_IMAGE_MEDIA_TYPE,
    AiImageEncoding,
    to_ai_jpeg_base64,
)
from app.modules.providers.model_catalog import CLAUDE_CLI_DEFAULT_MODEL

RESULT_EVENT_TYPE = "result"
STREAM_JSON_OUTPUT_ARGS = ("--output-format", "stream-json", "--verbose")
STREAM_JSON_INPUT_ARGS = ("--input-format", "stream-json")
LOCKED_DOWN_ARGS = ("--tools", "", "--no-session-persistence", "--setting-sources", "")
PARTIAL_MESSAGES_FLAG = "--include-partial-messages"


@dataclass(frozen=True)
class ClaudeCliConfig:
    claude_bin: str
    image_encoding: AiImageEncoding


class ClaudeCliClient:
    def __init__(self, config: ClaudeCliConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def ask_for_json(self, model: str, ask: AiAsk, limits: AiLimits) -> dict[str, Any]:
        result_event = output_to_result_event(self._run(model, ask, limits))
        structured_output = None if result_event is None else result_event.get("structured_output")
        if not isinstance(structured_output, dict):
            raise AiCallError("claude returned no structured output")
        return structured_output

    def ask_for_text(self, model: str, ask: AiAsk, limits: AiLimits) -> str:
        result_event = output_to_result_event(self._run(model, ask, limits))
        if result_event is None:
            raise AiCallError("claude returned no result")
        answer = str(result_event.get("result") or "").strip()
        if not answer:
            raise AiCallError("claude returned an empty answer")
        return answer

    def _run(self, model: str, ask: AiAsk, limits: AiLimits) -> CommandOutput:
        command = Command(
            args=self._build_args(model, ask, limits),
            timeout_sec=limits.timeout_sec,
            stdin_text=self._build_stdin(ask),
            # Outside the repo so the CLI does not load the project's CLAUDE.md.
            cwd=Path(tempfile.gettempdir()),
        )
        try:
            if limits.silence_limit_sec is None:
                return CommandOutput(stdout=self._runner.run(command), stderr="", returncode=0)
            return self._runner.run_watched(command, limits.silence_limit_sec, limits.on_output)
        except CommandError as error:
            raise AiCallError(str(error)) from error

    def _build_args(self, model: str, ask: AiAsk, limits: AiLimits) -> list[str]:
        args = [self._config.claude_bin, "-p", *STREAM_JSON_OUTPUT_ARGS]
        if ask.images:
            args += STREAM_JSON_INPUT_ARGS
        if ask.reply_schema is not None:
            args += ["--json-schema", json.dumps(ask.reply_schema)]
        args += ["--system-prompt", ask.instructions, *LOCKED_DOWN_ARGS]
        if limits.silence_limit_sec is not None:
            args.append(PARTIAL_MESSAGES_FLAG)
        if model != CLAUDE_CLI_DEFAULT_MODEL:
            args += ["--model", model]
        return args

    def _build_stdin(self, ask: AiAsk) -> str:
        if not ask.images:
            return ask.message
        return build_user_event(ask, self._config.image_encoding)


def build_user_event(ask: AiAsk, encoding: AiImageEncoding) -> str:
    content: list[dict[str, Any]] = [{"type": "text", "text": ask.message}]
    for image in ask.images:
        content.append({"type": "text", "text": image.label})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": AI_IMAGE_MEDIA_TYPE,
                    "data": to_ai_jpeg_base64(image.path, encoding),
                },
            }
        )
    user_event = {"type": "user", "message": {"role": "user", "content": content}}
    return json.dumps(user_event) + "\n"


def output_to_result_event(output: CommandOutput) -> dict[str, Any] | None:
    result_event = stdout_to_result_event(output.stdout)
    if result_event is None and output.returncode != 0:
        stderr_tail = output.stderr[-STDERR_TAIL_CHARS:].strip()
        raise AiCallError(f"claude exited with {output.returncode}: {stderr_tail}")
    if result_event is not None and result_event.get("is_error"):
        raise AiCallError(f"claude failed: {result_event.get('result', 'unknown error')}")
    return result_event


def stdout_to_result_event(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise AiCallError("claude returned output that is not JSON") from error
        if isinstance(event, dict) and event.get("type") == RESULT_EVENT_TYPE:
            return event
    return None
