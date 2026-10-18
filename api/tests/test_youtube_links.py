import pytest

from app.modules.jobs.errors import InvalidYoutubeJobError
from app.modules.jobs.youtube_to_markdown.links import (
    parse_youtube_link,
    to_timestamp_url,
    to_watch_url,
)

VIDEO_ID = "dQw4w9WgXcQ"
PLAYLIST_ID = "PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG"


def capture_link_error(link: str) -> InvalidYoutubeJobError:
    with pytest.raises(InvalidYoutubeJobError) as caught:
        parse_youtube_link(link)
    return caught.value


@pytest.fixture(
    params=[
        f"https://www.youtube.com/watch?v={VIDEO_ID}",
        f"  youtube.com/watch?v={VIDEO_ID}&t=42s  ",
        f"https://m.youtube.com/watch?v={VIDEO_ID}&feature=share",
        f"https://www.youtube.com/watch?v={VIDEO_ID}&list={PLAYLIST_ID}&index=3",
        f"https://youtu.be/{VIDEO_ID}",
        f"https://youtu.be/{VIDEO_ID}?si=abc123",
        f"http://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}",
        f"HTTPS://WWW.YouTube.com/watch?v={VIDEO_ID}",
    ]
)
def parsed_video_id(request):
    return parse_youtube_link(request.param)


@pytest.fixture(
    params=[
        "https://vimeo.com/76979871",
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/@somechannel",
        "hello",
        "",
        f"ftp://www.youtube.com/watch?v={VIDEO_ID}",
        "https://youtu.be/",
        f"https://youtu.be/{VIDEO_ID}/extra",
        "https://www.youtube.com/shorts/",
        f"https://www.youtube.com/clip/{VIDEO_ID}",
    ]
)
def not_a_video_error(request):
    return capture_link_error(request.param)


@pytest.fixture(
    params=[
        f"https://www.youtube.com/playlist?list={PLAYLIST_ID}",
        f"youtube.com/watch?list={PLAYLIST_ID}",
    ]
)
def playlist_error(request):
    return capture_link_error(request.param)


@pytest.fixture
def watch_url():
    return to_watch_url(VIDEO_ID)


@pytest.fixture
def timestamp_url():
    return to_timestamp_url(VIDEO_ID, 83_999)


def test_parse_youtube_link_reads_the_id_from_every_accepted_form(parsed_video_id):
    assert parsed_video_id == VIDEO_ID


def test_parse_youtube_link_rejects_anything_that_is_not_a_video_link(not_a_video_error):
    assert str(not_a_video_error) == "Not a YouTube video link"


def test_parse_youtube_link_rejects_a_playlist_without_a_video(playlist_error):
    assert str(playlist_error) == (
        "Playlist links are not supported. Open one video and copy its link"
    )


def test_to_watch_url_builds_the_canonical_link(watch_url):
    assert watch_url == f"https://www.youtube.com/watch?v={VIDEO_ID}"


def test_to_timestamp_url_points_at_the_whole_second(timestamp_url):
    assert timestamp_url == f"https://www.youtube.com/watch?v={VIDEO_ID}&t=83s"
