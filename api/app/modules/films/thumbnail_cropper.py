from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandRunner

THUMBNAIL_WIDTH_PX = 1280
THUMBNAIL_HEIGHT_PX = 720
JPEG_QUALITY = 2
FILL_FILTER = (
    f"scale={THUMBNAIL_WIDTH_PX}:{THUMBNAIL_HEIGHT_PX}:force_original_aspect_ratio=increase,"
    f"crop={THUMBNAIL_WIDTH_PX}:{THUMBNAIL_HEIGHT_PX}"
)


@dataclass(frozen=True)
class CropperConfig:
    ffmpeg_bin: str
    timeout_sec: float


class FfmpegThumbnailCropper:
    def __init__(self, config: CropperConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def crop_to_fill(self, source_path: Path, target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        self._runner.run(
            Command(
                args=[
                    self._config.ffmpeg_bin,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    str(source_path),
                    "-vf",
                    FILL_FILTER,
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    "-q:v",
                    str(JPEG_QUALITY),
                    str(target_path),
                ],
                timeout_sec=self._config.timeout_sec,
            )
        )
