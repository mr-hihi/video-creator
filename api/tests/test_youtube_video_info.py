import pytest

from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo, info_json_to_video_info

FULL_INFO = {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 213.5,
    "live_status": "was_live",
    "language": "en",
    "subtitles": {"ja": [], "live_chat": [], "en": []},
    "automatic_captions": {"vi": [], "en-orig": []},
}


@pytest.fixture
def full_video():
    return info_json_to_video_info(FULL_INFO)


@pytest.fixture
def sparse_video():
    return info_json_to_video_info(
        {"id": "vfjegxHDOwI", "duration": None, "language": None, "subtitles": None}
    )


def test_info_json_to_video_info_reads_every_field(full_video):
    assert full_video == VideoInfo(
        video_id="dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        duration_ms=213_500,
        live_status="was_live",
        metadata_language="en",
        manual_caption_codes=["en", "ja"],
        auto_caption_codes=["en-orig", "vi"],
    )


def test_info_json_to_video_info_fills_missing_fields_with_empty_values(sparse_video):
    assert sparse_video == VideoInfo(
        video_id="vfjegxHDOwI",
        title="vfjegxHDOwI",
        duration_ms=0,
        live_status="",
        metadata_language="",
        manual_caption_codes=[],
        auto_caption_codes=[],
    )
