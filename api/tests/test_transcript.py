from dataclasses import dataclass

import pytest

from app.modules.jobs.video_to_markdown.transcript import (
    TranscriptSegment,
    format_timestamp,
    join_segment_texts,
    whisper_json_to_transcript,
)

WHISPER_JSON = {
    "result": {"language": "en"},
    "transcription": [
        {"offsets": {"from": 0, "to": 2000}, "text": " Hello there."},
        {"offsets": {"from": 2000, "to": 3000}, "text": " [BLANK_AUDIO]"},
        {"offsets": {"from": 3000, "to": 4000}, "text": "   "},
        {"offsets": {"from": 4000, "to": 6000}, "text": " (music)"},
        {"offsets": {"from": 6000, "to": 8000}, "text": " Next step."},
    ],
}


@dataclass(frozen=True)
class Outcome:
    actual: str
    expected: str


@pytest.fixture
def transcript():
    return whisper_json_to_transcript(WHISPER_JSON, "auto")


@pytest.fixture
def transcript_without_result():
    return whisper_json_to_transcript({}, "vi")


@pytest.fixture(params=[(0, "00:00"), (83_999, "01:23"), (3_723_000, "1:02:03")])
def formatted_timestamp(request):
    position_ms, expected = request.param
    return Outcome(actual=format_timestamp(position_ms), expected=expected)


@pytest.fixture
def joined_text():
    return join_segment_texts(
        [TranscriptSegment(0, 1, " First."), TranscriptSegment(1, 2, " Second. ")]
    )


def test_whisper_json_to_transcript_keeps_only_speech_segments(transcript):
    assert transcript.segments == [
        TranscriptSegment(0, 2000, " Hello there."),
        TranscriptSegment(6000, 8000, " Next step."),
    ]


def test_whisper_json_to_transcript_uses_detected_language(transcript):
    assert transcript.language == "en"


def test_whisper_json_to_transcript_falls_back_to_requested_language(transcript_without_result):
    assert transcript_without_result.language == "vi"


def test_whisper_json_to_transcript_is_empty_without_transcription(transcript_without_result):
    assert transcript_without_result.segments == []


def test_format_timestamp_shows_hours_only_when_present(formatted_timestamp):
    assert formatted_timestamp.actual == formatted_timestamp.expected


def test_join_segment_texts_concatenates_and_trims(joined_text):
    assert joined_text == "First. Second."
