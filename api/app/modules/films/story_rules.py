from app.modules.films.field_rules import to_optional_text

STORY_BIBLE_LIMIT = 20000
SUMMARY_LIMIT = 10000
STORY_BIBLE_MESSAGE = f"Story bible must be at most {STORY_BIBLE_LIMIT} characters"
SUMMARY_MESSAGE = f"Summary must be at most {SUMMARY_LIMIT} characters"


def to_valid_story_bible(story_bible: str | None) -> str | None:
    return to_optional_text(story_bible, STORY_BIBLE_LIMIT, STORY_BIBLE_MESSAGE)


def to_valid_summary(summary: str | None) -> str | None:
    return to_optional_text(summary, SUMMARY_LIMIT, SUMMARY_MESSAGE)
