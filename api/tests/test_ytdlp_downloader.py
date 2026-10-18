import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError, CommandRunner
from app.modules.jobs.youtube_to_markdown.captions import CaptionKind, CaptionTrack
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpConfig, YtDlpDownloader

VIDEO_URL = "https://www.youtube.com/watch?v=vfjegxHDOwI"
CAPTIONS_JSON = {"events": [{"tStartMs": 0, "segs": [{"utf8": "Xin chào"}]}]}
COMMON_ARGS = ["yt-dlp", "--js-runtimes", "node", "--no-playlist"]


def write_file_named(file_name: str, content: str):
    def write(command) -> str:
        output_template = Path(command.args[command.args.index("-o") + 1])
        (output_template.parent / file_name).write_text(content, encoding="utf-8")
        return ""

    return write


def capture_command_error(action) -> CommandError:
    with pytest.raises(CommandError) as caught:
        action()
    return caught.value


@pytest.fixture
def runner():
    return MagicMock(spec=CommandRunner)


@pytest.fixture
def downloader(runner):
    return YtDlpDownloader(YtDlpConfig("yt-dlp", 45, 720), runner)


@pytest.fixture
def video_info(runner, downloader):
    runner.run.return_value = json.dumps({"id": "vfjegxHDOwI"})
    return downloader.read_video_info(VIDEO_URL)


@pytest.fixture
def info_command(runner, video_info):
    return runner.run.call_args.args[0]


@pytest.fixture
def non_json_info_error(runner, downloader):
    runner.run.return_value = "WARNING: something\n"
    return capture_command_error(lambda: downloader.read_video_info(VIDEO_URL))


@pytest.fixture
def auto_captions(runner, downloader, tmp_path):
    runner.run.side_effect = write_file_named("captions.vi-orig.json3", json.dumps(CAPTIONS_JSON))
    return downloader.download_captions(
        VIDEO_URL, CaptionTrack("vi-orig", CaptionKind.AUTO), tmp_path
    )


@pytest.fixture
def auto_captions_command(runner, auto_captions):
    return runner.run.call_args.args[0]


@pytest.fixture
def manual_captions_command(runner, downloader, tmp_path):
    runner.run.side_effect = write_file_named("captions.en.json3", json.dumps(CAPTIONS_JSON))
    downloader.download_captions(VIDEO_URL, CaptionTrack("en", CaptionKind.MANUAL), tmp_path)
    return runner.run.call_args.args[0]


@pytest.fixture
def missing_captions_error(runner, downloader, tmp_path):
    runner.run.return_value = ""
    track = CaptionTrack("ja", CaptionKind.MANUAL)
    return capture_command_error(lambda: downloader.download_captions(VIDEO_URL, track, tmp_path))


@pytest.fixture
def non_json_captions_error(runner, downloader, tmp_path):
    runner.run.side_effect = write_file_named("captions.ja.json3", "<xml/>")
    track = CaptionTrack("ja", CaptionKind.MANUAL)
    return capture_command_error(lambda: downloader.download_captions(VIDEO_URL, track, tmp_path))


@pytest.fixture
def downloaded_video_path(runner, downloader, tmp_path):
    runner.run.side_effect = write_file_named("source.mp4", "video")
    return downloader.download_video(VIDEO_URL, tmp_path / "source.mp4")


@pytest.fixture
def video_command(runner, downloaded_video_path):
    return runner.run.call_args.args[0]


@pytest.fixture
def missing_video_error(runner, downloader, tmp_path):
    runner.run.return_value = ""
    return capture_command_error(
        lambda: downloader.download_video(VIDEO_URL, tmp_path / "source.mp4")
    )


def test_read_video_info_parses_the_single_json(video_info):
    assert video_info == {"id": "vfjegxHDOwI"}


def test_read_video_info_skips_the_download(info_command):
    assert info_command.args == [*COMMON_ARGS, "--skip-download", "--dump-single-json", VIDEO_URL]
    assert info_command.timeout_sec == 45


def test_read_video_info_rejects_output_that_is_not_json(non_json_info_error):
    assert str(non_json_info_error) == "yt-dlp returned video info that is not JSON"


def test_download_captions_returns_the_parsed_track(auto_captions):
    assert auto_captions == CAPTIONS_JSON


def test_download_captions_asks_for_auto_captions_of_one_track(auto_captions_command, tmp_path):
    assert auto_captions_command.args == [
        *COMMON_ARGS,
        "--skip-download",
        "--write-auto-subs",
        "--sub-langs",
        "vi-orig",
        "--sub-format",
        "json3",
        "-o",
        str(tmp_path / "captions.%(ext)s"),
        VIDEO_URL,
    ]


def test_download_captions_asks_for_uploaded_subtitles_of_a_manual_track(
    manual_captions_command,
):
    assert "--write-subs" in manual_captions_command.args
    assert "--write-auto-subs" not in manual_captions_command.args


def test_download_captions_raises_when_no_file_is_written(missing_captions_error):
    assert str(missing_captions_error) == "yt-dlp wrote no 'ja' captions"


def test_download_captions_rejects_a_file_that_is_not_json(non_json_captions_error):
    assert str(non_json_captions_error) == "yt-dlp returned captions that is not JSON"


def test_download_video_returns_the_requested_path(downloaded_video_path, tmp_path):
    assert downloaded_video_path == tmp_path / "source.mp4"


def test_download_video_fetches_the_video_stream_as_mp4(video_command, tmp_path):
    assert video_command.args == [
        *COMMON_ARGS,
        "-f",
        "bv/b",
        "-S",
        "res:720,vcodec:h264",
        "--remux-video",
        "mp4",
        "--no-progress",
        "-o",
        str(tmp_path / "source.%(ext)s"),
        VIDEO_URL,
    ]


def test_download_video_raises_when_no_file_is_written(missing_video_error):
    assert str(missing_video_error) == "yt-dlp wrote no video file at source.mp4"
