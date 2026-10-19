from dataclasses import dataclass

import pytest

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.story_bible_replies import (
    STORY_BIBLE_REPLY_SCHEMA,
    WrittenStoryBible,
    normalize_story_bible_reply,
)

AI_NAME = "gemini"


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


@pytest.fixture
def trimmed_story_bible():
    reply = {"summary": "  Mai rings the bell.  ", "storyBible": "  Mai keeps the bell.  "}
    return normalize_story_bible_reply(reply, AI_NAME)


@pytest.fixture(
    params=[
        ("s" * 10001, "s" * 10000),
        ("   ", None),
        (None, None),
        (42, None),
    ]
)
def summary_outcome(request):
    summary, expected = request.param
    written = normalize_story_bible_reply({"summary": summary, "storyBible": "Bible"}, AI_NAME)
    return Outcome(actual=written.summary, expected=expected)


@pytest.fixture
def missing_summary_story_bible():
    return normalize_story_bible_reply({"storyBible": "Bible"}, AI_NAME)


@pytest.fixture
def longest_story_bible():
    reply = {"summary": "Summary", "storyBible": "  " + "b" * 20000 + "  "}
    return normalize_story_bible_reply(reply, AI_NAME)


@pytest.fixture(params=[{}, {"storyBible": "   "}, {"storyBible": None}, {"storyBible": ["Mai"]}])
def empty_story_bible_error(request):
    with pytest.raises(EpisodeStepFailedError) as error:
        normalize_story_bible_reply({"summary": "Summary", **request.param}, AI_NAME)
    return error.value


@pytest.fixture
def long_story_bible_error():
    with pytest.raises(EpisodeStepFailedError) as error:
        normalize_story_bible_reply({"summary": "Summary", "storyBible": "b" * 20001}, AI_NAME)
    return error.value


def test_both_texts_are_trimmed(trimmed_story_bible):
    assert trimmed_story_bible == WrittenStoryBible(
        summary="Mai rings the bell.", story_bible="Mai keeps the bell."
    )


def test_the_summary_is_cut_to_10000_and_null_when_blank(summary_outcome):
    assert summary_outcome.actual == summary_outcome.expected


def test_a_missing_summary_is_null(missing_summary_story_bible):
    assert missing_summary_story_bible.summary is None


def test_a_story_bible_of_20000_characters_after_trimming_is_kept(longest_story_bible):
    assert longest_story_bible.story_bible == "b" * 20000


def test_an_empty_story_bible_fails_the_step(empty_story_bible_error):
    assert str(empty_story_bible_error) == "gemini returned an empty story bible"


def test_a_story_bible_over_20000_characters_fails_the_step(long_story_bible_error):
    assert str(long_story_bible_error) == "gemini returned a story bible over 20000 characters"


def test_the_reply_schema_requires_the_fixed_shape():
    assert STORY_BIBLE_REPLY_SCHEMA["required"] == ["summary", "storyBible"]
