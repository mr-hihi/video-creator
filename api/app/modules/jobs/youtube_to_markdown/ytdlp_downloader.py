import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.common.process import Command, CommandError, CommandRunner
from app.modules.jobs.youtube_to_markdown.captions import CaptionKind, CaptionTrack

JS_RUNTIME = "node"
CAPTIONS_BASENAME = "captions"
CAPTIONS_FORMAT = "json3"
VIDEO_CONTAINER = "mp4"
OUTPUT_EXTENSION_PLACEHOLDER = ".%(ext)s"
VIDEO_ONLY_FORMAT = "bv/b"
VIDEO_WITH_AUDIO_FORMAT = "bv*+ba/b"
PREFERRED_VIDEO_CODEC = "h264"
PREFERRED_AUDIO_CODEC = "aac"
SUBTITLE_FLAGS_BY_KIND = {
    CaptionKind.MANUAL: "--write-subs",
    CaptionKind.AUTO: "--write-auto-subs",
}


@dataclass(frozen=True)
class YtDlpConfig:
    ytdlp_bin: str
    timeout_sec: float
    max_video_height: int


class YtDlpDownloader:
    def __init__(self, config: YtDlpConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def read_video_info(self, video_url: str) -> dict[str, Any]:
        stdout = self._run(["--skip-download", "--dump-single-json", video_url])
        return _parse_json(stdout, "video info")

    def download_captions(
        self, video_url: str, track: CaptionTrack, output_dir: Path
    ) -> dict[str, Any]:
        self._run(
            [
                "--skip-download",
                SUBTITLE_FLAGS_BY_KIND[track.kind],
                "--sub-langs",
                track.code,
                "--sub-format",
                CAPTIONS_FORMAT,
                "-o",
                str(output_dir / f"{CAPTIONS_BASENAME}{OUTPUT_EXTENSION_PLACEHOLDER}"),
                video_url,
            ]
        )
        captions_path = output_dir / f"{CAPTIONS_BASENAME}.{track.code}.{CAPTIONS_FORMAT}"
        if not captions_path.is_file():
            raise CommandError(f"yt-dlp wrote no '{track.code}' captions")
        return _parse_json(captions_path.read_text(encoding="utf-8"), "captions")

    def download_video(self, video_url: str, output_path: Path) -> Path:
        return self._download(
            [
                "-f",
                VIDEO_ONLY_FORMAT,
                "-S",
                f"res:{self._config.max_video_height},vcodec:{PREFERRED_VIDEO_CODEC}",
                "--remux-video",
                VIDEO_CONTAINER,
            ],
            video_url,
            output_path,
        )

    def download_video_with_audio(self, video_url: str, output_path: Path) -> Path:
        return self._download(
            [
                "-f",
                VIDEO_WITH_AUDIO_FORMAT,
                "-S",
                (
                    f"res:{self._config.max_video_height},vcodec:{PREFERRED_VIDEO_CODEC},"
                    f"acodec:{PREFERRED_AUDIO_CODEC}"
                ),
                "--merge-output-format",
                VIDEO_CONTAINER,
                "--remux-video",
                VIDEO_CONTAINER,
            ],
            video_url,
            output_path,
        )

    def _download(self, format_arguments: list[str], video_url: str, output_path: Path) -> Path:
        self._run(
            [
                *format_arguments,
                "--no-progress",
                "-o",
                str(output_path.with_suffix(OUTPUT_EXTENSION_PLACEHOLDER)),
                video_url,
            ]
        )
        if not output_path.is_file():
            raise CommandError(f"yt-dlp wrote no video file at {output_path.name}")
        return output_path

    def _run(self, arguments: list[str]) -> str:
        return self._runner.run(
            Command(
                args=[
                    self._config.ytdlp_bin,
                    "--js-runtimes",
                    JS_RUNTIME,
                    "--no-playlist",
                    *arguments,
                ],
                timeout_sec=self._config.timeout_sec,
            )
        )


def _parse_json(text: str, content_name: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise CommandError(f"yt-dlp returned {content_name} that is not JSON") from error
