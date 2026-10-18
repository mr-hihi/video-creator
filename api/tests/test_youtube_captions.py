from dataclasses import dataclass

import pytest

from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment
from app.modules.jobs.youtube_to_markdown.captions import (
    CaptionKind,
    CaptionTrack,
    MissingCaptionLanguageError,
    NoCaptionsError,
    find_spoken_language,
    json3_to_transcript,
    select_caption_track,
)
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo

RICK_MANUAL_CODES = ["de-DE", "en", "es-419", "ja", "pt-BR"]
CAPTION_EVENTS = [
    {"tStartMs": 0, "dDurationMs": 671_800},
    {
        "tStartMs": 240,
        "dDurationMs": 3439,
        "segs": [{"utf8": "được làm việc khá là kỹ càng với các nhà"}],
    },
    {"tStartMs": 1670, "dDurationMs": 2009, "aAppend": 1, "segs": [{"utf8": "\n"}]},
    {"tStartMs": 1680, "dDurationMs": 3920, "segs": [{"utf8": "[Âm nhạc]"}]},
    {
        "tStartMs": 3679,
        "dDurationMs": 3801,
        "segs": [{"utf8": "đầu tư giỏi"}, {"utf8": " nhất ở Nhật Bản\nấy thì họ"}],
    },
    {
        "tStartMs": 5590,
        "dDurationMs": 1890,
        "segs": [{"utf8": "đầu tư giỏi nhất ở Nhật Bản ấy thì họ"}],
    },
]


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


def build_video(
    metadata_language: str, manual_codes: list[str], auto_codes: list[str]
) -> VideoInfo:
    return VideoInfo(
        video_id="dQw4w9WgXcQ",
        title="Demo",
        duration_ms=213_000,
        live_status="not_live",
        metadata_language=metadata_language,
        manual_caption_codes=manual_codes,
        auto_caption_codes=auto_codes,
    )


def capture_selection_error(video: VideoInfo, language: str) -> Exception:
    with pytest.raises((NoCaptionsError, MissingCaptionLanguageError)) as caught:
        select_caption_track(video, language)
    return caught.value


@pytest.fixture(
    params=[
        ("auto", "en", ["en-US"], ["en-orig"], CaptionTrack("en-US", CaptionKind.MANUAL)),
        ("auto", "en", [], ["en-orig", "vi"], CaptionTrack("en-orig", CaptionKind.AUTO)),
        ("auto", "", ["ja", "de"], [], CaptionTrack("de", CaptionKind.MANUAL)),
        ("ja", "en", ["ja"], ["en-orig", "ja"], CaptionTrack("ja", CaptionKind.MANUAL)),
        ("en", "en", [], ["en-orig"], CaptionTrack("en-orig", CaptionKind.AUTO)),
        ("en", "en-US", ["en-GB", "en-US"], ["en-orig"], CaptionTrack("en-GB", CaptionKind.MANUAL)),
        ("vi", "", [], ["vi-orig", "en"], CaptionTrack("vi-orig", CaptionKind.AUTO)),
    ]
)
def selected_track(request):
    language, metadata_language, manual_codes, auto_codes, expected = request.param
    video = build_video(metadata_language, sorted(manual_codes), sorted(auto_codes))
    return Outcome(actual=select_caption_track(video, language), expected=expected)


@pytest.fixture(
    params=[
        ("auto", "en", ["ja"], []),
        ("auto", "en", [], []),
        ("vi", "en", [], []),
        ("auto", "", [], ["en", "vi"]),
    ]
)
def no_captions_error(request):
    language, metadata_language, manual_codes, auto_codes = request.param
    return capture_selection_error(
        build_video(metadata_language, manual_codes, auto_codes), language
    )


@pytest.fixture
def machine_translation_only_error():
    video = build_video("vi", [], ["en", "ja", "vi", "vi-orig"])
    return capture_selection_error(video, "en")


@pytest.fixture
def missing_language_error():
    return capture_selection_error(build_video("en", RICK_MANUAL_CODES, ["en-orig", "vi"]), "vi")


@pytest.fixture
def duplicate_primary_language_error():
    return capture_selection_error(build_video("en", ["en-GB", "en-US"], []), "ja")


@pytest.fixture
def spoken_language_from_original_track():
    return find_spoken_language(build_video("", [], ["en", "fr-orig", "vi"]))


@pytest.fixture
def track_language():
    return CaptionTrack("es-419", CaptionKind.MANUAL).language


@pytest.fixture
def converted_transcript():
    return json3_to_transcript({"events": CAPTION_EVENTS}, "vi")


@pytest.fixture
def silent_transcript():
    return json3_to_transcript({"events": [CAPTION_EVENTS[0], CAPTION_EVENTS[2]]}, "vi")


@pytest.fixture
def eventless_transcript():
    return json3_to_transcript({}, "vi")


def test_select_caption_track_picks_the_expected_track(selected_track):
    assert selected_track.actual == selected_track.expected


def test_select_caption_track_reports_no_transcript(no_captions_error):
    assert isinstance(no_captions_error, NoCaptionsError)
    assert str(no_captions_error) == "This video has no transcript on YouTube"


def test_select_caption_track_never_uses_a_machine_translation(machine_translation_only_error):
    assert str(machine_translation_only_error) == (
        "No 'en' captions on YouTube for this video. Available: vi (auto)"
    )


def test_select_caption_track_lists_every_usable_track(missing_language_error):
    assert str(missing_language_error) == (
        "No 'vi' captions on YouTube for this video. Available: de (manual), en (manual), "
        "es (manual), ja (manual), pt (manual), en (auto)"
    )


def test_select_caption_track_lists_a_language_once(duplicate_primary_language_error):
    assert str(duplicate_primary_language_error).endswith("Available: en (manual)")


def test_find_spoken_language_falls_back_to_the_original_track(
    spoken_language_from_original_track,
):
    assert spoken_language_from_original_track == "fr"


def test_caption_track_language_is_the_primary_subtag(track_language):
    assert track_language == "es"


def test_json3_to_transcript_keeps_only_distinct_spoken_lines(converted_transcript):
    assert converted_transcript.segments == [
        TranscriptSegment(
            start_ms=240, end_ms=3679, text=" được làm việc khá là kỹ càng với các nhà"
        ),
        TranscriptSegment(
            start_ms=3679, end_ms=7480, text=" đầu tư giỏi nhất ở Nhật Bản ấy thì họ"
        ),
    ]


def test_json3_to_transcript_uses_the_track_language(converted_transcript):
    assert converted_transcript.language == "vi"


def test_json3_to_transcript_is_empty_without_spoken_lines(silent_transcript, eventless_transcript):
    assert silent_transcript.segments == []
    assert eventless_transcript.segments == []
