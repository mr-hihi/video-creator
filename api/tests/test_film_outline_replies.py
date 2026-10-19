from dataclasses import dataclass

import pytest

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.outline_replies import (
    OUTLINE_REPLY_SCHEMA,
    OutlineShape,
    WrittenOutline,
    WrittenPart,
    normalize_outline_reply,
)

SHAPE = OutlineShape(episode_number=3, ai_name="gemini")


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


def build_part(title: str, **values) -> dict:
    return {"title": title, "plan": f"{title} plan", "durationS": 60, **values}


@pytest.fixture
def messy_outline():
    reply = {
        "title": "  The Bell  ",
        "logline": " Mai hears a bell. ",
        "parts": [
            build_part(" The Pier ", plan=" Mai walks to the pier. "),
            build_part("   "),
            build_part("No plan", plan="  "),
            "not a mapping",
            build_part("The Boat", plan=" Mai rows out. "),
        ],
        "musicPrompt": " Slow cello ",
        "thumbnailPrompt": " A bell in fog ",
    }
    return normalize_outline_reply(reply, SHAPE)


@pytest.fixture
def bare_outline():
    reply = {
        "title": "  ",
        "logline": "   ",
        "parts": [build_part("T" * 200, plan="p" * 6000)],
        "thumbnailPrompt": 7,
    }
    return normalize_outline_reply(reply, SHAPE)


@pytest.fixture
def long_title_outline():
    reply = {"title": "T" * 200, "parts": [build_part("The Pier")]}
    return normalize_outline_reply(reply, SHAPE)


@pytest.fixture(
    params=[
        (60, 60),
        (45.4, 45),
        (12.6, 13),
        (8, 8),
        (600, 600),
        (2, 8),
        (900, 600),
        ("30", 600),
        (True, 600),
        (None, 600),
        (float("nan"), 600),
    ]
)
def duration_outcome(request):
    duration_s, expected = request.param
    outline = normalize_outline_reply(
        {"parts": [build_part("The Pier", durationS=duration_s)]}, SHAPE
    )
    return Outcome(actual=outline.parts[0].target_duration_s, expected=expected)


@pytest.fixture
def missing_duration_outline():
    part = build_part("The Pier")
    del part["durationS"]
    return normalize_outline_reply({"parts": [part]}, SHAPE)


@pytest.fixture(
    params=[
        {},
        {"parts": "none"},
        {"parts": []},
        {"title": "The Bell", "parts": [build_part(" "), build_part("No plan", plan="")]},
    ]
)
def no_parts_error(request):
    with pytest.raises(EpisodeStepFailedError) as error:
        normalize_outline_reply(request.param, SHAPE)
    return error.value


def test_the_outline_keeps_trimmed_texts_and_the_usable_parts(messy_outline):
    assert messy_outline == WrittenOutline(
        title="The Bell",
        logline="Mai hears a bell.",
        parts=(
            WrittenPart(title="The Pier", plan="Mai walks to the pier.", target_duration_s=60),
            WrittenPart(title="The Boat", plan="Mai rows out.", target_duration_s=60),
        ),
        music_prompt="Slow cello",
        thumbnail_prompt="A bell in fog",
    )


def test_a_blank_title_falls_back_to_the_episode_number(bare_outline):
    assert bare_outline.title == "Episode 3"


def test_blank_or_missing_texts_are_null(bare_outline):
    assert (bare_outline.logline, bare_outline.music_prompt, bare_outline.thumbnail_prompt) == (
        None,
        None,
        None,
    )


def test_part_titles_are_cut_to_150_and_plans_to_5000(bare_outline):
    assert bare_outline.parts == (
        WrittenPart(title="T" * 150, plan="p" * 5000, target_duration_s=60),
    )


def test_a_long_title_is_cut_to_150(long_title_outline):
    assert long_title_outline.title == "T" * 150


def test_part_lengths_are_rounded_into_8_to_600_or_take_600(duration_outcome):
    assert duration_outcome.actual == duration_outcome.expected


def test_a_part_without_a_length_takes_600(missing_duration_outline):
    assert missing_duration_outline.parts[0].target_duration_s == 600


def test_no_usable_part_fails_the_step(no_parts_error):
    assert str(no_parts_error) == "gemini returned no parts"


def test_the_reply_schema_requires_the_fixed_shape():
    assert OUTLINE_REPLY_SCHEMA["required"] == [
        "title",
        "logline",
        "parts",
        "musicPrompt",
        "thumbnailPrompt",
    ]


def test_every_part_of_the_reply_states_its_title_plan_and_length():
    assert OUTLINE_REPLY_SCHEMA["properties"]["parts"]["items"]["required"] == [
        "title",
        "plan",
        "durationS",
    ]
