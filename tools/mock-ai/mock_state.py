from __future__ import annotations

import base64
import fcntl
import json
import os
import struct
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATE_DIR_ENV = "MOCK_AI_STATE_DIR"
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / "video-tool-mock-ai"
CALLS_FILE_NAME = "calls.jsonl"
SCENARIO_FILE_NAME = "scenario.json"
SCENARIO_USES_FILE_NAME = "scenario-uses.json"
LOCK_FILE_NAME = ".lock"
TEXT_PREVIEW_CHARS = 300
PROMPT_AIS = frozenset({"claude", "gemini", "openai"})
CLAUDE_AUTH_AI = "claude-auth"
WHISPER_AI = "whisper"
JPEG_START_OF_FRAME_MARKERS = frozenset(
    {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
)
JPEG_MARKERS_WITHOUT_LENGTH = frozenset({0xD8, 0x01, *range(0xD0, 0xD8)})


@dataclass(frozen=True)
class SentImage:
    label: str
    data: bytes


@dataclass(frozen=True)
class AskView:
    ai: str
    model: str
    instructions: str
    message: str
    images: list[SentImage] = field(default_factory=list)
    reply_schema: dict[str, Any] | None = None

    @property
    def image_labels(self) -> list[str]:
        return [image.label for image in self.images]


def find_state_dir() -> Path:
    state_dir = Path(os.environ.get(STATE_DIR_ENV) or DEFAULT_STATE_DIR)
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@contextmanager
def lock_state(state_dir: Path) -> Iterator[None]:
    with (state_dir / LOCK_FILE_NAME).open("a") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def record_call(state_dir: Path, entry: dict[str, Any]) -> None:
    line = json.dumps({"at": time.strftime("%H:%M:%S"), **entry}, ensure_ascii=False)
    with lock_state(state_dir), (state_dir / CALLS_FILE_NAME).open("a", encoding="utf-8") as calls:
        calls.write(line + "\n")


def take_scenario_rule(state_dir: Path, ai: str, text: str) -> dict[str, Any] | None:
    with lock_state(state_dir):
        rules = read_json(state_dir / SCENARIO_FILE_NAME, [])
        uses = read_json(state_dir / SCENARIO_USES_FILE_NAME, {})
        for index, rule in enumerate(rules):
            used_count = uses.get(str(index), 0)
            is_used_up = rule.get("times") is not None and used_count >= rule["times"]
            if is_used_up or not is_rule_for(rule, ai, text):
                continue
            uses[str(index)] = used_count + 1
            (state_dir / SCENARIO_USES_FILE_NAME).write_text(json.dumps(uses))
            return rule
    return None


def is_rule_for(rule: dict[str, Any], ai: str, text: str) -> bool:
    rule_ai = rule.get("ai")
    is_same_ai = rule_ai == ai or (rule_ai is None and ai in PROMPT_AIS)
    return is_same_ai and str(rule.get("match", "")) in text


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8") or "null") or default


def describe_ask(ask: AskView) -> dict[str, Any]:
    return {
        "ai": ask.ai,
        "model": ask.model,
        "instructions": ask.instructions[:TEXT_PREVIEW_CHARS],
        "message": ask.message[:TEXT_PREVIEW_CHARS],
        "messageChars": len(ask.message),
        "replySchemaKeys": sorted((ask.reply_schema or {}).get("properties", {})),
        "images": [describe_image(image) for image in ask.images],
    }


def describe_image(image: SentImage) -> dict[str, Any]:
    width, height = read_jpeg_size(image.data)
    return {"label": image.label, "width": width, "height": height, "bytes": len(image.data)}


def decode_base64_image(label: str, data: str) -> SentImage:
    return SentImage(label=label, data=base64.b64decode(data))


def read_jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    position = 2
    while position + 4 <= len(data) and data[position] == 0xFF:
        marker = data[position + 1]
        if marker in JPEG_MARKERS_WITHOUT_LENGTH:
            position += 2
            continue
        segment_length = struct.unpack(">H", data[position + 2 : position + 4])[0]
        if marker in JPEG_START_OF_FRAME_MARKERS:
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + segment_length
    return None, None


def split_into_chunks(text: str, chunk_count: int) -> list[str]:
    if not text:
        return [text]
    size = max(1, -(-len(text) // chunk_count))
    return [text[start : start + size] for start in range(0, len(text), size)]
