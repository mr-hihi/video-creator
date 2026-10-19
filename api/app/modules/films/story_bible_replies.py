from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.reply_values import to_text
from app.modules.films.story_rules import STORY_BIBLE_LIMIT, SUMMARY_LIMIT

EMPTY_STORY_BIBLE_MESSAGE = "{model} returned an empty story bible"
LONG_STORY_BIBLE_MESSAGE = "{model} returned a story bible over {limit} characters"

_STRING = {"type": "string"}
STORY_BIBLE_REPLY_SCHEMA = {
    "type": "object",
    "properties": {"summary": _STRING, "storyBible": _STRING},
    "required": ["summary", "storyBible"],
}


@dataclass(frozen=True)
class WrittenStoryBible:
    summary: str | None
    story_bible: str


def normalize_story_bible_reply(reply: Mapping[str, Any], ai_name: str) -> WrittenStoryBible:
    story_bible = to_text(reply.get("storyBible"))
    if not story_bible:
        raise EpisodeStepFailedError(EMPTY_STORY_BIBLE_MESSAGE.format(model=ai_name))
    if len(story_bible) > STORY_BIBLE_LIMIT:
        raise EpisodeStepFailedError(
            LONG_STORY_BIBLE_MESSAGE.format(model=ai_name, limit=STORY_BIBLE_LIMIT)
        )
    return WrittenStoryBible(
        summary=to_text(reply.get("summary"))[:SUMMARY_LIMIT] or None,
        story_bible=story_bible,
    )
