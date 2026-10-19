from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.films.episode_rules import TITLE_LIMIT, build_default_title
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.part_rules import (
    MAX_PART_DURATION_S,
    MIN_PART_DURATION_S,
    PART_PLAN_LIMIT,
    PART_TITLE_LIMIT,
)
from app.modules.films.reply_values import to_entries, to_seconds_within, to_text

NO_PARTS_MESSAGE = "{model} returned no parts"

_STRING = {"type": "string"}
OUTLINE_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": _STRING,
        "logline": _STRING,
        "parts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": _STRING,
                    "plan": _STRING,
                    "durationS": {"type": "integer"},
                },
                "required": ["title", "plan", "durationS"],
            },
        },
        "musicPrompt": _STRING,
        "thumbnailPrompt": _STRING,
    },
    "required": ["title", "logline", "parts", "musicPrompt", "thumbnailPrompt"],
}


@dataclass(frozen=True)
class OutlineShape:
    episode_number: int
    ai_name: str


@dataclass(frozen=True)
class WrittenPart:
    title: str
    plan: str
    target_duration_s: int


@dataclass(frozen=True)
class WrittenOutline:
    title: str
    logline: str | None
    parts: tuple[WrittenPart, ...]
    music_prompt: str | None
    thumbnail_prompt: str | None


def normalize_outline_reply(reply: Mapping[str, Any], shape: OutlineShape) -> WrittenOutline:
    parts = _to_parts(reply)
    if not parts:
        raise EpisodeStepFailedError(NO_PARTS_MESSAGE.format(model=shape.ai_name))
    title = to_text(reply.get("title")) or build_default_title(shape.episode_number)
    return WrittenOutline(
        title=title[:TITLE_LIMIT],
        logline=to_text(reply.get("logline")) or None,
        parts=parts,
        music_prompt=to_text(reply.get("musicPrompt")) or None,
        thumbnail_prompt=to_text(reply.get("thumbnailPrompt")) or None,
    )


def _to_parts(reply: Mapping[str, Any]) -> tuple[WrittenPart, ...]:
    return tuple(
        WrittenPart(
            title=to_text(entry.get("title"))[:PART_TITLE_LIMIT],
            plan=to_text(entry.get("plan"))[:PART_PLAN_LIMIT],
            target_duration_s=to_seconds_within(
                entry.get("durationS"),
                (MIN_PART_DURATION_S, MAX_PART_DURATION_S),
                MAX_PART_DURATION_S,
            ),
        )
        for entry in to_entries(reply, "parts")
        if to_text(entry.get("title")) and to_text(entry.get("plan"))
    )
