from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import Command, CommandRunner
from app.modules.films.thumbnail_cropper import CropperConfig, FfmpegThumbnailCropper


@pytest.fixture
def cropped(tmp_path):
    runner = MagicMock(spec=CommandRunner)
    source_path = tmp_path / "output" / "thumbnail-candidate-1.png"
    target_path = tmp_path / "fresh" / "Show - E01 - Pilot-thumbnail.jpg"
    FfmpegThumbnailCropper(CropperConfig("ffmpeg-test", 120), runner).crop_to_fill(
        source_path, target_path
    )
    return SimpleNamespace(
        command=runner.run.call_args.args[0],
        source_path=source_path,
        target_path=target_path,
    )


def test_crop_to_fill_scales_up_and_crops_to_1280x720(cropped):
    assert cropped.command == Command(
        args=[
            "ffmpeg-test",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(cropped.source_path),
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
            "-frames:v",
            "1",
            "-update",
            "1",
            "-q:v",
            "2",
            str(cropped.target_path),
        ],
        timeout_sec=120,
    )


def test_crop_to_fill_creates_the_target_folder(cropped):
    assert cropped.target_path.parent.is_dir() is True
