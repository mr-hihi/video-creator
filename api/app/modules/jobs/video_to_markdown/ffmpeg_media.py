from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandError, CommandRunner

MS_PER_SECOND = 1000
WHISPER_SAMPLE_RATE_HZ = 16000
MAX_FRAME_WIDTH_PX = 1280
JPEG_QUALITY = 3
SAMPLES_PER_SECOND = 1
AUDIO_PART_PATTERN = "part-%02d.m4a"
VIDEO_PART_PATTERN = "part-%02d.mp4"
MEDIA_PART_AUDIO_BITRATE = "64k"
COMPRESSED_VIDEO_CRF = "28"


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


@dataclass(frozen=True)
class AudioSplit:
    video_path: Path
    output_dir: Path
    part_sec: int


@dataclass(frozen=True)
class VideoCompression:
    video_path: Path
    output_dir: Path
    part_sec: int
    max_side_px: int
    max_fps: int


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

    def split_audio(self, split: AudioSplit) -> None:
        self._run_ffmpeg(
            [
                "-i",
                str(split.video_path),
                "-vn",
                "-ac",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                MEDIA_PART_AUDIO_BITRATE,
                *to_segment_arguments(split.part_sec),
                str(split.output_dir / AUDIO_PART_PATTERN),
            ]
        )

    def compress_video(self, compression: VideoCompression) -> None:
        self._run_ffmpeg(
            [
                "-i",
                str(compression.video_path),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                to_long_side_scale_filter(compression.max_side_px),
                "-fpsmax",
                str(compression.max_fps),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                COMPRESSED_VIDEO_CRF,
                "-pix_fmt",
                "yuv420p",
                "-force_key_frames",
                f"expr:gte(t,n_forced*{compression.part_sec})",
                "-c:a",
                "aac",
                "-ac",
                "1",
                "-b:a",
                MEDIA_PART_AUDIO_BITRATE,
                *to_segment_arguments(compression.part_sec),
                str(compression.output_dir / VIDEO_PART_PATTERN),
            ]
        )

    def _run_ffmpeg(self, arguments: list[str]) -> None:
        self._runner.run(
            Command(
                args=[self._config.ffmpeg_bin, "-y", "-loglevel", "error", *arguments],
                timeout_sec=self._config.timeout_sec,
            )
        )


def to_segment_arguments(part_sec: int) -> list[str]:
    return [
        "-f",
        "segment",
        "-segment_time",
        str(part_sec),
        "-reset_timestamps",
        "1",
        "-segment_start_number",
        "1",
    ]


def to_long_side_scale_filter(max_side_px: int) -> str:
    capped_width = f"trunc(min({max_side_px},iw)/2)*2"
    capped_height = f"trunc(min({max_side_px},ih)/2)*2"
    return f"scale='if(gte(iw,ih),{capped_width},-2)':'if(gte(iw,ih),-2,{capped_height})'"
