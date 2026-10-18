import pytest

from app.modules.jobs.video_to_markdown.markdown import (
    CapturedMoment,
    MarkdownSource,
    build_markdown,
    build_markdown_with_moment_links,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment
from app.modules.jobs.video_to_markdown.transcript import Transcript, TranscriptSegment

TRANSCRIPT = Transcript(
    language="en",
    segments=[
        TranscriptSegment(start_ms=0, end_ms=1000, text=" Welcome."),
        TranscriptSegment(start_ms=5000, end_ms=7000, text=" First topic."),
        TranscriptSegment(start_ms=7000, end_ms=9000, text=" More detail."),
        TranscriptSegment(start_ms=20_000, end_ms=22_000, text=" Wrap up."),
    ],
)
CAPTURED_MOMENTS = [
    CapturedMoment(KeyMoment(at_ms=5000, title="First [topic]"), "images/moment-01-00m05s.jpg"),
    CapturedMoment(KeyMoment(at_ms=20_000, title="Wrap"), "images/moment-02-00m20s.jpg"),
]
EXPECTED_MARKDOWN = """# Demo

> Source: demo.mp4 · Duration: 01:05 · Language: en

A short demo.

Welcome.

## 00:05 — First [topic]

![00:05 — First (topic)](images/moment-01-00m05s.jpg)

First topic. More detail.

## 00:20 — Wrap

![00:20 — Wrap](images/moment-02-00m20s.jpg)

Wrap up.
"""
EXPECTED_MINIMAL_MARKDOWN = """# Silent part

> Source: demo.mp4 · Duration: 00:30 · Language: en

## 00:00 — Opening

![00:00 — Opening](images/moment-01-00m00s.jpg)
"""
EXPECTED_LINKED_HEADINGS = [
    "## [00:05](https://video.example/v1?t=5) — First [topic]",
    "## [00:20](https://video.example/v1?t=20) — Wrap",
]
LINKED_SOURCE_LINE = "> Source: https://video.example/v1 · Duration: 01:05 · Language: en"
LINKED_ALT_TEXT_LINE = "![00:05 — First (topic)](images/moment-01-00m05s.jpg)"


@pytest.fixture
def markdown():
    return build_markdown(
        MarkdownSource(
            title="Demo",
            summary="A short demo.",
            source_label="demo.mp4",
            duration_ms=65_000,
            transcript=TRANSCRIPT,
            captured_moments=CAPTURED_MOMENTS,
        )
    )


@pytest.fixture
def minimal_markdown():
    return build_markdown(
        MarkdownSource(
            title="Silent part",
            summary="",
            source_label="demo.mp4",
            duration_ms=30_000,
            transcript=Transcript(language="en", segments=[]),
            captured_moments=[
                CapturedMoment(KeyMoment(at_ms=0, title="Opening"), "images/moment-01-00m00s.jpg")
            ],
        )
    )


def test_build_markdown_places_each_segment_under_its_moment(markdown):
    assert markdown == EXPECTED_MARKDOWN


def test_build_markdown_omits_empty_summary_leading_text_and_section_text(minimal_markdown):
    assert minimal_markdown == EXPECTED_MINIMAL_MARKDOWN


@pytest.fixture
def linked_markdown_lines():
    markdown = build_markdown_with_moment_links(
        MarkdownSource(
            title="Demo",
            summary="A short demo.",
            source_label="https://video.example/v1",
            duration_ms=65_000,
            transcript=TRANSCRIPT,
            captured_moments=CAPTURED_MOMENTS,
        ),
        lambda at_ms: f"https://video.example/v1?t={at_ms // 1000}",
    )
    return markdown.splitlines()


@pytest.fixture
def linked_headings(linked_markdown_lines):
    return [line for line in linked_markdown_lines if line.startswith("## ")]


def test_build_markdown_with_moment_links_links_every_heading_timestamp(linked_headings):
    assert linked_headings == EXPECTED_LINKED_HEADINGS


def test_build_markdown_with_moment_links_shows_the_source_label(linked_markdown_lines):
    assert LINKED_SOURCE_LINE in linked_markdown_lines


def test_build_markdown_with_moment_links_keeps_alt_text_plain(linked_markdown_lines):
    assert LINKED_ALT_TEXT_LINE in linked_markdown_lines
