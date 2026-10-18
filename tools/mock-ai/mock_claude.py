#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ai_answers import build_scenario_answer
from mock_state import (
    CLAUDE_AUTH_AI,
    AskView,
    SentImage,
    decode_base64_image,
    describe_ask,
    find_state_dir,
    record_call,
    split_into_chunks,
    take_scenario_rule,
)

AI_NAME = "claude"
DEFAULT_MODEL = "default"
MOCK_VERSION = "9.9.9 (Mock Claude Code)"
STREAM_JSON = "stream-json"
FLAGS_WITH_VALUE = frozenset(
    {
        "--output-format",
        "--input-format",
        "--json-schema",
        "--system-prompt",
        "--append-system-prompt",
        "--model",
        "--tools",
        "--setting-sources",
        "--permission-mode",
        "--max-turns",
    }
)
DEFAULT_CHUNK_COUNT = 3


@dataclass
class CliRequest:
    flags: dict[str, str] = field(default_factory=dict)
    switches: set[str] = field(default_factory=set)

    @property
    def model(self) -> str:
        return self.flags.get("--model", DEFAULT_MODEL)

    @property
    def wants_partial_messages(self) -> bool:
        return "--include-partial-messages" in self.switches


def parse_args(args: list[str]) -> CliRequest:
    request = CliRequest()
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in FLAGS_WITH_VALUE and index + 1 < len(args):
            request.flags[arg] = args[index + 1]
            index += 2
            continue
        request.switches.add(arg)
        index += 1
    return request


def read_ask(request: CliRequest, stdin_text: str) -> AskView:
    schema_text = request.flags.get("--json-schema")
    message, images = stdin_to_message(stdin_text, request.flags.get("--input-format"))
    return AskView(
        ai=AI_NAME,
        model=request.model,
        instructions=request.flags.get("--system-prompt", ""),
        message=message,
        images=images,
        reply_schema=json.loads(schema_text) if schema_text else None,
    )


def stdin_to_message(stdin_text: str, input_format: str | None) -> tuple[str, list[SentImage]]:
    if input_format != STREAM_JSON:
        return stdin_text, []
    texts: list[str] = []
    images: list[SentImage] = []
    for line in stdin_text.splitlines():
        if not line.strip():
            continue
        content = json.loads(line).get("message", {}).get("content", [])
        for block in content:
            if block.get("type") == "text":
                texts.append(block["text"])
            elif block.get("type") == "image":
                label = texts.pop() if len(texts) > 1 else ""
                images.append(decode_base64_image(label, block["source"]["data"]))
    return (texts[0] if texts else ""), images


def write_event(event: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def build_result_event(answer: str, ask: AskView, rule: dict[str, Any]) -> dict[str, Any]:
    if rule.get("fail"):
        return {
            "type": "result",
            "subtype": "error_during_execution",
            "is_error": True,
            "result": rule["fail"],
        }
    event: dict[str, Any] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": answer,
        "session_id": str(uuid.uuid4()),
        "num_turns": 1,
    }
    if ask.reply_schema is not None:
        try:
            structured_output = json.loads(answer)
        except json.JSONDecodeError:
            structured_output = None
        if isinstance(structured_output, dict):
            event["structured_output"] = structured_output
    return event


def stream_answer(request: CliRequest, answer: str, rule: dict[str, Any]) -> None:
    chunks = rule.get("chunks") or split_into_chunks(answer, DEFAULT_CHUNK_COUNT)
    for chunk in chunks:
        time.sleep(float(rule.get("chunk_every_sec", 0)))
        if request.wants_partial_messages:
            write_event(
                {
                    "type": "stream_event",
                    "event": {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": chunk},
                    },
                }
            )


def answer_print_request(request: CliRequest, stdin_text: str) -> int:
    state_dir = find_state_dir()
    ask = read_ask(request, stdin_text)
    rule = take_scenario_rule(state_dir, AI_NAME, f"{ask.instructions}\n{ask.message}") or {}
    record_call(
        state_dir,
        {
            **describe_ask(ask),
            "hasModelFlag": "--model" in request.flags,
            "partialMessages": request.wants_partial_messages,
            "inputFormat": request.flags.get("--input-format", "text"),
            "scenario": rule or None,
        },
    )
    time.sleep(float(rule.get("silent_sec", 0)))
    if rule.get("exit"):
        sys.stderr.write(str(rule.get("stderr", "mock claude failed")) + "\n")
        return int(rule["exit"])
    answer = build_scenario_answer(ask, rule)
    write_event(
        {"type": "system", "subtype": "init", "model": ask.model, "session_id": str(uuid.uuid4())}
    )
    stream_answer(request, answer, rule)
    write_event(
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": answer}]},
        }
    )
    result_event = build_result_event(answer, ask, rule)
    if request.flags.get("--output-format") == STREAM_JSON:
        write_event(result_event)
    else:
        sys.stdout.write(json.dumps(result_event, ensure_ascii=False))
    return 0


def answer_auth_status() -> int:
    rule = take_scenario_rule(find_state_dir(), CLAUDE_AUTH_AI, "auth status") or {}
    is_logged_in = not rule.get("logged_out")
    write_event({"loggedIn": is_logged_in, "authMethod": "mock", "apiProvider": "firstParty"})
    return 0 if is_logged_in else 1


def main(args: list[str]) -> int:
    if args[:2] == ["auth", "status"]:
        return answer_auth_status()
    if "--version" in args or "-v" in args:
        print(MOCK_VERSION)
        return 0
    request = parse_args(args)
    if not request.switches & {"-p", "--print"}:
        sys.stderr.write("mock claude only answers -p / --print and auth status\n")
        return 2
    return answer_print_request(request, sys.stdin.read())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
