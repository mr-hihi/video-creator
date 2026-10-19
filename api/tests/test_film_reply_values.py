from dataclasses import dataclass

import pytest

from app.modules.films.reply_values import to_entries, to_seconds_within, to_text

SECONDS_RANGE = (4, 30)
DEFAULT_S = 6


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


@pytest.fixture(
    params=[
        ("  Mai hears a bell.  ", "Mai hears a bell."),
        ("   ", ""),
        (None, ""),
        (42, ""),
        (["Mai"], ""),
    ]
)
def text_outcome(request):
    value, expected = request.param
    return Outcome(actual=to_text(value), expected=expected)


@pytest.fixture(
    params=[
        (
            {"parts": [{"title": "A"}, "not a mapping", 3, None, {"title": "B"}]},
            [{"title": "A"}, {"title": "B"}],
        ),
        ({"parts": []}, []),
        ({"parts": "none"}, []),
        ({"parts": {"title": "A"}}, []),
        ({}, []),
    ]
)
def entries_outcome(request):
    reply, expected = request.param
    return Outcome(actual=to_entries(reply, "parts"), expected=expected)


@pytest.fixture(
    params=[
        (12, 12),
        (12.4, 12),
        (12.6, 13),
        (4, 4),
        (30, 30),
        (2, 4),
        (-5, 4),
        (45, 30),
        (30.6, 30),
        ("10", DEFAULT_S),
        (True, DEFAULT_S),
        (False, DEFAULT_S),
        (None, DEFAULT_S),
        (float("nan"), DEFAULT_S),
        (float("inf"), DEFAULT_S),
        (float("-inf"), DEFAULT_S),
    ]
)
def seconds_outcome(request):
    value, expected = request.param
    return Outcome(actual=to_seconds_within(value, SECONDS_RANGE, DEFAULT_S), expected=expected)


def test_text_is_trimmed_and_anything_but_a_string_is_blank(text_outcome):
    assert text_outcome.actual == text_outcome.expected


def test_entries_keep_only_the_mappings_of_a_list(entries_outcome):
    assert entries_outcome.actual == entries_outcome.expected


def test_seconds_are_rounded_into_range_or_take_the_default(seconds_outcome):
    assert seconds_outcome.actual == seconds_outcome.expected
