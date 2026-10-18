from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandError, CommandRunner

MS_PER_SECOND = 1000
WHISPER_SAMPLE_RATE_HZ = 16000
MAX_FRAME_WIDTH_PX = 1280
JPEG_QUALITY = 3
SAMPLES_PER_SECOND = 1


@dataclass(frozen=True)
class FfmpegConfig:
    ffmpeg_bin: str
    ffprobe_bin: str
    timeout_sec: float


@dataclass(frozen=True)
class FrameSampling:
    video_path: Path
    output_pattern: Path
    frame_count: int
    max_width_px: int


class FfmpegMediaProcessor:
    def __init__(self, config: FfmpegConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def probe_duration_ms(self, video_path: Path) -> int:
        stdout = self._runner.run(
            Command(
                args=[
                    self._config.ffprobe_bin,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                timeout_sec=self._config.timeout_sec,
            )
        )
        try:
            return int(float(stdout.strip()) * MS_PER_SECOND)
        except ValueError as error:
            raise CommandError(f"ffprobe returned no duration for {video_path.name}") from error

    def extract_audio(self, video_path: Path, audio_path: Path) -> Path:
        self._run_ffmpeg(
            [
                "-i",
                str(video_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(WHISPER_SAMPLE_RATE_HZ),
                "-c:a",
                "pcm_s16le",
                str(audio_path),
            ]
        )
        return audio_path

    def capture_frame(self, video_path: Path, at_ms: int, image_path: Path) -> Path:
        self._run_ffmpeg(
            [
                "-ss",
                f"{at_ms / MS_PER_SECOND:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale='min({MAX_FRAME_WIDTH_PX},iw)':-2",
                "-q:v",
                str(JPEG_QUALITY),
                str(image_path),
            ]
        )
        return image_path

    def sample_frames(self, sampling: FrameSampling) -> None:
        self._run_ffmpeg(
            [
                "-i",
                str(sampling.video_path),
                "-vf",
                f"fps={SAMPLES_PER_SECOND},scale='min({sampling.max_width_px},iw)':-2",
                "-frames:v",
                str(sampling.frame_count),
                "-q:v",
                str(JPEG_QUALITY),
                "-start_number",
                "0",
                str(sampling.output_pattern),
            ]
        )

    def _run_ffmpeg(self, arguments: list[str]) -> None:
        self._runner.run(
            Command(
                args=[self._config.ffmpeg_bin, "-y", "-loglevel", "error", *arguments],
                timeout_sec=self._config.timeout_sec,
            )
        )
