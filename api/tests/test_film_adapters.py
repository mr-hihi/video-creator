from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError, CommandRunner
from app.modules.ai_models.ai_calls import AttachedImage
from app.modules.jobs.film_analysis.prompt_passes import to_frame_images
from app.modules.jobs.film_analysis.scene_detector import (
    FfmpegSceneDetector,
    SceneDetectionError,
    SceneDetectorConfig,
)

VIDEO_PATH = Path("storage/job-1/source.mp4")
SCENE_CONFIG = SceneDetectorConfig(ffmpeg_bin="ffmpeg", threshold=0.4, timeout_sec=3600)


@pytest.fixture
def scene_runner():
    runner = MagicMock(spec=CommandRunner)
    runner.run.return_value = "frame:0 pts:1 pts_time:12.5\nlavfi.scene_score=0.7\n"
    return runner


@pytest.fixture
def detected_cut_times_ms(scene_runner):
    return FfmpegSceneDetector(SCENE_CONFIG, scene_runner).detect_cut_times_ms(VIDEO_PATH)


@pytest.fixture
def scene_command(scene_runner, detected_cut_times_ms):
    return scene_runner.run.call_args.args[0]


@pytest.fixture
def scene_detection_error(scene_runner):
    scene_runner.run.side_effect = CommandError("ffmpeg timed out after 3600s")
    with pytest.raises(SceneDetectionError) as caught:
        FfmpegSceneDetector(SCENE_CONFIG, scene_runner).detect_cut_times_ms(VIDEO_PATH)
    return caught.value


@pytest.fixture
def images_dir(tmp_path):
    directory = tmp_path / "output" / "images"
    directory.mkdir(parents=True)
    (directory / "moment-02-00m20s.jpg").write_bytes(b"second-frame")
    (directory / "moment-01-00m00s.jpg").write_bytes(b"first-frame")
    (directory / "notes.txt").write_bytes(b"not a frame")
    return directory


def test_detect_cut_times_ms_reads_the_metadata_output(detected_cut_times_ms):
    assert detected_cut_times_ms == [12_500]


def test_detect_cut_times_ms_runs_the_scene_filter_without_audio(scene_command):
    assert scene_command.args == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(VIDEO_PATH),
        "-an",
        "-vf",
        "select='gt(scene,0.4)',metadata=print:file=-",
        "-f",
        "null",
        "-",
    ]
    assert scene_command.timeout_sec == 3600


def test_detect_cut_times_ms_wraps_ffmpeg_failures(scene_detection_error):
    assert str(scene_detection_error) == "Scene detection failed: ffmpeg timed out after 3600s"


def test_every_captured_frame_is_attached_in_name_order_after_its_path(images_dir):
    assert to_frame_images(images_dir) == [
        AttachedImage("images/moment-01-00m00s.jpg", images_dir / "moment-01-00m00s.jpg"),
        AttachedImage("images/moment-02-00m20s.jpg", images_dir / "moment-02-00m20s.jpg"),
    ]
