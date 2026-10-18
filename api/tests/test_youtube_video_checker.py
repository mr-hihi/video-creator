from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError
from app.modules.jobs.errors import InvalidYoutubeJobError, YoutubeUnreachableError
from app.modules.jobs.youtube_to_markdown.video_checker import (
    YoutubeVideoChecker,
    ytdlp_failure_to_error,
)
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader

VIDEO_ID = "vfjegxHDOwI"
VIDEO_LINK = f"https://youtu.be/{VIDEO_ID}?si=abc"


def build_info(live_status: str, duration_sec: int) -> dict:
    return {
        "id": VIDEO_ID,
        "title": "30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này!",
        "duration": duration_sec,
        "live_status": live_status,
        "language": "vi",
    }


def capture_check_error(checker: YoutubeVideoChecker, link: str) -> Exception:
    with pytest.raises((InvalidYoutubeJobError, YoutubeUnreachableError)) as caught:
        checker.fetch_convertible_video(link)
    return caught.value


@pytest.fixture
def downloader():
    ytdlp_downloader = MagicMock(spec=YtDlpDownloader)
    ytdlp_downloader.read_video_info.return_value = build_info("not_live", 670)
    return ytdlp_downloader


@pytest.fixture
def checker(downloader):
    return YoutubeVideoChecker(downloader, max_duration_min=180)


@pytest.fixture
def checked_video(checker):
    return checker.fetch_convertible_video(VIDEO_LINK)


@pytest.fixture(params=["not_live", "was_live"])
def accepted_video(request, downloader, checker):
    downloader.read_video_info.return_value = build_info(request.param, 670)
    return checker.fetch_convertible_video(VIDEO_LINK)


@pytest.fixture(params=["is_live", "is_upcoming", "post_live"])
def live_video_error(request, downloader, checker):
    downloader.read_video_info.return_value = build_info(request.param, 0)
    return capture_check_error(checker, VIDEO_LINK)


@pytest.fixture
def too_long_error(downloader):
    return capture_check_error(YoutubeVideoChecker(downloader, max_duration_min=5), VIDEO_LINK)


@pytest.fixture
def video_at_the_limit(downloader):
    downloader.read_video_info.return_value = build_info("not_live", 300)
    return YoutubeVideoChecker(downloader, max_duration_min=5).fetch_convertible_video(VIDEO_LINK)


@pytest.fixture
def bad_link_error(checker):
    return capture_check_error(checker, "https://vimeo.com/76979871")


@pytest.fixture
def refused_video_error(downloader, checker):
    downloader.read_video_info.side_effect = CommandError(
        f"yt-dlp exited with 1: ERROR: [youtube] {VIDEO_ID}: This video is unavailable"
    )
    return capture_check_error(checker, VIDEO_LINK)


@pytest.fixture(
    params=[
        f"yt-dlp exited with 1: ERROR: [youtube] {VIDEO_ID}: Unable to download API page: "
        "<urlopen error [Errno 8] nodename nor servname provided>",
        f"yt-dlp exited with 1: ERROR: [youtube] {VIDEO_ID}: Sign in to confirm you're not a bot",
        f"yt-dlp exited with 1: ERROR: [youtube] {VIDEO_ID}: HTTP Error 429: Too Many Requests",
        "yt-dlp timed out after 30s",
        "yt-dlp is not installed or not on PATH",
    ]
)
def unreachable_error(request):
    return ytdlp_failure_to_error(CommandError(request.param), VIDEO_ID)


@pytest.fixture
def last_refusal_error():
    return ytdlp_failure_to_error(
        CommandError(
            f"yt-dlp exited with 1: WARNING: retrying\nERROR: [youtube] {VIDEO_ID}: Private video\n"
        ),
        VIDEO_ID,
    )


def test_fetch_convertible_video_returns_the_video_info(checked_video):
    assert (checked_video.video_id, checked_video.duration_ms) == (VIDEO_ID, 670_000)


def test_fetch_convertible_video_reads_the_canonical_url(downloader, checked_video):
    downloader.read_video_info.assert_called_once_with(
        f"https://www.youtube.com/watch?v={VIDEO_ID}"
    )


def test_fetch_convertible_video_accepts_a_video_that_is_not_live(accepted_video):
    assert accepted_video.video_id == VIDEO_ID


def test_fetch_convertible_video_rejects_live_and_upcoming_videos(live_video_error):
    assert isinstance(live_video_error, InvalidYoutubeJobError)
    assert str(live_video_error) == "Live or upcoming videos are not supported"


def test_fetch_convertible_video_rejects_a_video_over_the_limit(too_long_error):
    assert str(too_long_error) == "Video is 11:10 long; the limit is 5 min"


def test_fetch_convertible_video_accepts_a_video_exactly_at_the_limit(video_at_the_limit):
    assert video_at_the_limit.duration_ms == 300_000


def test_fetch_convertible_video_checks_the_link_before_calling_youtube(bad_link_error, downloader):
    assert str(bad_link_error) == "Not a YouTube video link"
    downloader.read_video_info.assert_not_called()


def test_fetch_convertible_video_reports_the_youtube_refusal(refused_video_error):
    assert isinstance(refused_video_error, InvalidYoutubeJobError)
    assert str(refused_video_error) == "YouTube refused the video: This video is unavailable"


def test_ytdlp_failure_to_error_treats_network_trouble_as_unreachable(unreachable_error):
    assert isinstance(unreachable_error, YoutubeUnreachableError)
    assert str(unreachable_error).startswith("Could not reach YouTube: ")


def test_ytdlp_failure_to_error_uses_the_last_refusal_line(last_refusal_error):
    assert str(last_refusal_error) == "YouTube refused the video: Private video"
