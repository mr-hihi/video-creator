from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandError, CommandRunner
from app.modules.jobs.film_analysis.frames import ffmpeg_metadata_to_cut_times_ms


class SceneDetectionError(Exception):
    pass


@dataclass(frozen=True)
class SceneDetectorConfig:
    ffmpeg_bin: str
    threshold: float
    timeout_sec: float


class FfmpegSceneDetector:
    def __init__(self, config: SceneDetectorConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def detect_cut_times_ms(self, video_path: Path) -> list[int]:
        try:
            stdout = self._runner.run(
                Command(
                    args=[
                        self._config.ffmpeg_bin,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(video_path),
                        "-an",
                        "-vf",
                        f"select='gt(scene,{self._config.threshold})',metadata=print:file=-",
                        "-f",
                        "null",
                        "-",
                    ],
                    timeout_sec=self._config.timeout_sec,
                )
            )
        except CommandError as error:
            raise SceneDetectionError(f"Scene detection failed: {error}") from error
        return ffmpeg_metadata_to_cut_times_ms(stdout)
