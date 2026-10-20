import pytest

from app.modules.jobs.video_to_markdown.markdown import (
    CapturedMoment,
    MarkdownSource,
    Speaker,
    SpeakerVoices,
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


SPOKEN_TRANSCRIPT = Transcript(
    language="vi",
    segments=[
        TranscriptSegment(start_ms=0, end_ms=1500, text=" Chào anh."),
        TranscriptSegment(start_ms=2000, end_ms=3500, text=" Chào em."),
        TranscriptSegment(start_ms=4000, end_ms=5500, text=" Đi thôi."),
        TranscriptSegment(start_ms=5800, end_ms=6000, text="  "),
    ],
)
SPEAKER_VOICES = SpeakerVoices(
    speakers=[Speaker("Mai", "young woman, soft voice"), Speaker("Long", "")],
    speaker_names_by_start_ms={0: "Mai", 2000: "Long"},
)
EXPECTED_SPOKEN_MARKDOWN = """# Gặp gỡ

> Source: phim.mp4 · Duration: 00:10 · Language: vi

Hai người gặp nhau.

Speakers:
- **Mai** — young woman, soft voice
- **Long**

## 00:00 — Gặp gỡ

![00:00 — Gặp gỡ](images/moment-01-00m00s.jpg)

**Mai:** Chào anh.

**Long:** Chào em.

Đi thôi.
"""


def build_spoken_markdown(voices: SpeakerVoices) -> str:
    return build_markdown(
        MarkdownSource(
            title="Gặp gỡ",
            summary="Hai người gặp nhau.",
            source_label="phim.mp4",
            duration_ms=10_000,
            transcript=SPOKEN_TRANSCRIPT,
            captured_moments=[
                CapturedMoment(KeyMoment(at_ms=0, title="Gặp gỡ"), "images/moment-01-00m00s.jpg")
            ],
            voices=voices,
        )
    )


@pytest.fixture
def spoken_markdown():
    return build_spoken_markdown(SPEAKER_VOICES)


@pytest.fixture
def unspoken_markdown():
    return build_spoken_markdown(SpeakerVoices())


@pytest.fixture
def spoken_leading_markdown():
    return build_markdown(
        MarkdownSource(
            title="Gặp gỡ",
            summary="",
            source_label="phim.mp4",
            duration_ms=10_000,
            transcript=SPOKEN_TRANSCRIPT,
            captured_moments=[
                CapturedMoment(KeyMoment(at_ms=4000, title="Đi"), "images/moment-01-00m04s.jpg")
            ],
            voices=SPEAKER_VOICES,
        )
    )


def test_markdown_with_speakers_lists_them_and_gives_each_line_its_speaker(spoken_markdown):
    assert spoken_markdown == EXPECTED_SPOKEN_MARKDOWN


def test_markdown_without_speakers_joins_each_moment_into_one_paragraph(unspoken_markdown):
    assert "Speakers:" not in unspoken_markdown
    assert unspoken_markdown.endswith("Chào anh. Chào em. Đi thôi.\n")


def test_markdown_with_speakers_splits_the_lines_before_the_first_moment(
    spoken_leading_markdown,
):
    assert (
        "- **Long**\n\n**Mai:** Chào anh.\n\n**Long:** Chào em.\n\n## 00:04 — Đi"
        in spoken_leading_markdown
    )
