import pytest

from app.modules.jobs.video_to_markdown.moments import KeyMoment, normalize_moments

RAW_MOMENTS = [
    KeyMoment(at_ms=9000, title=" Setup "),
    KeyMoment(at_ms=-500, title="Intro"),
    KeyMoment(at_ms=1000, title="Too close to intro"),
    KeyMoment(at_ms=20_000, title="   "),
    KeyMoment(at_ms=99_000, title="After the end"),
]


@pytest.fixture
def normalized_moments():
    return normalize_moments(RAW_MOMENTS, duration_ms=60_000, max_moments=10)


@pytest.fixture
def capped_moments():
    return normalize_moments(RAW_MOMENTS, duration_ms=60_000, max_moments=2)


@pytest.fixture
def moments_of_very_short_video():
    return normalize_moments([KeyMoment(at_ms=5000, title="Only")], duration_ms=200, max_moments=5)


def test_normalize_moments_sorts_clamps_trims_and_drops_close_or_blank(normalized_moments):
    assert normalized_moments == [
        KeyMoment(at_ms=0, title="Intro"),
        KeyMoment(at_ms=9000, title="Setup"),
        KeyMoment(at_ms=59_500, title="After the end"),
    ]


def test_normalize_moments_caps_to_max_moments(capped_moments):
    assert capped_moments == [
        KeyMoment(at_ms=0, title="Intro"),
        KeyMoment(at_ms=9000, title="Setup"),
    ]


def test_normalize_moments_clamps_to_zero_when_video_is_shorter_than_margin(
    moments_of_very_short_video,
):
    assert moments_of_very_short_video == [KeyMoment(at_ms=0, title="Only")]
