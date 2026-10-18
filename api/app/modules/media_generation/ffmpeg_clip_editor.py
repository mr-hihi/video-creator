from dataclasses import dataclass
from pathlib import Path

from app.common.process import Command, CommandRunner
from app.modules.media_generation.clip_editor import SegmentJoin
from app.modules.media_generation.clip_segments import JOIN_CUT_HEAD_S

FFMPEG_QUIET_ARGS = ("-y", "-loglevel", "error")
LAST_FRAME_WINDOW_SEC = 0.5
VIDEO_CODEC_ARGS = ("-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p")
AUDIO_CODEC_ARGS = ("-c:a", "aac", "-b:a", "192k")
FAST_START_ARGS = ("-movflags", "+faststart")


@dataclass(frozen=True)
class ClipEditorConfig:
    ffmpeg_bin: str
    timeout_sec: int


class FfmpegClipEditor:
    def __init__(self, config: ClipEditorConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def save_last_frame(self, clip_path: Path, frame_path: Path) -> None:
        self._run(build_last_frame_args(clip_path, frame_path))

    def join_segments(self, join: SegmentJoin) -> None:
        self._run(build_join_args(join))

    def _run(self, ffmpeg_args: list[str]) -> None:
        self._runner.run(
            Command(
                [self._config.ffmpeg_bin, *FFMPEG_QUIET_ARGS, *ffmpeg_args],
                self._config.timeout_sec,
            )
        )


def build_last_frame_args(clip_path: Path, frame_path: Path) -> list[str]:
    return [
        "-sseof",
        f"-{LAST_FRAME_WINDOW_SEC:g}",
        "-i",
        str(clip_path),
        "-update",
        "1",
        str(frame_path),
    ]


def build_join_args(join: SegmentJoin) -> list[str]:
    input_args = [arg for path in join.segment_paths for arg in ("-i", str(path))]
    map_args = ["-map", "[v]", *(["-map", "[a]"] if join.has_sound else [])]
    audio_args = list(AUDIO_CODEC_ARGS) if join.has_sound else ["-an"]
    return [
        *input_args,
        "-filter_complex",
        build_join_filter_graph(len(join.segment_paths), join.has_sound),
        *map_args,
        "-t",
        str(join.clip_length_s),
        *VIDEO_CODEC_ARGS,
        *audio_args,
        *FAST_START_ARGS,
        str(join.output_path),
    ]


def build_join_filter_graph(segment_count: int, has_sound: bool) -> str:
    chains = []
    joined_streams = ""
    for index in range(segment_count):
        video_head = "" if index == 0 else f"trim=start={JOIN_CUT_HEAD_S},"
        chains.append(f"[{index}:v]{video_head}setpts=PTS-STARTPTS,setsar=1[v{index}]")
        joined_streams += f"[v{index}]"
        if has_sound:
            audio_head = "" if index == 0 else f"atrim=start={JOIN_CUT_HEAD_S},"
            chains.append(f"[{index}:a]{audio_head}asetpts=PTS-STARTPTS[a{index}]")
            joined_streams += f"[a{index}]"
    audio_flag = 1 if has_sound else 0
    joined_outputs = "[v][a]" if has_sound else "[v]"
    chains.append(f"{joined_streams}concat=n={segment_count}:v=1:a={audio_flag}{joined_outputs}")
    return ";".join(chains)
