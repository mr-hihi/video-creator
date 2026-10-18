from collections.abc import Mapping
from typing import Any

from app.modules.jobs.video_to_markdown.moments import KeyMoment, VideoOutline

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "moments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"atMs": {"type": "integer"}, "title": {"type": "string"}},
                "required": ["atMs", "title"],
            },
        },
    },
    "required": ["title", "summary", "moments"],
}


class MomentPickerError(Exception):
    pass


def reply_to_outline(reply: Mapping[str, Any], ai_name: str) -> VideoOutline:
    try:
        moments = [
            KeyMoment(at_ms=int(moment["atMs"]), title=str(moment["title"]))
            for moment in reply.get("moments", [])
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise MomentPickerError(f"{ai_name} returned a malformed moment: {error}") from error
    return VideoOutline(
        title=str(reply.get("title", "")).strip(),
        summary=str(reply.get("summary", "")).strip(),
        moments=moments,
    )
