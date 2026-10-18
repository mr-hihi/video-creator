import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.common.process import CommandError
from app.modules.films.assembly_plan import SceneCut
from app.modules.films.models import Orientation, SubtitleStyle


@dataclass(frozen=True)
class FrameSize:
    width_px: int
    height_px: int


@dataclass(frozen=True)
class SubtitleLook:
    font_name: str
    primary_colour: str
    outline_colour: str
    back_colour: str
    outline_px: float
    shadow_px: float
    margin_side_px: int
    margin_bottom_px: int


FRAME_SIZES_BY_ORIENTATION = {
    Orientation.LANDSCAPE: FrameSize(width_px=1920, height_px=1080),
    Orientation.PORTRAIT: FrameSize(width_px=1080, height_px=1920),
}
FRAME_RATE_FPS = 24
VIDEO_CRF = 18
PIXEL_FORMAT = "yuv420p"
AUDIO_BITRATE = "192k"
AUDIO_SAMPLE_RATE_HZ = 48000
AUDIO_CHANNEL_COUNT = 2
CLIP_SOUND_VOLUME = 0.3
NARRATION_VOLUME = 1.5
MUSIC_FADE_OUT_MS = 2000
MS_PER_SECOND = 1000
AUDIO_CODEC_TYPE = "audio"
PROBE_NO_DURATION_MESSAGE = "ffprobe returned no duration"
SILENCE_SOURCE = f"anullsrc=channel_layout=stereo:sample_rate={AUDIO_SAMPLE_RATE_HZ}"
VIDEO_CODEC_ARGS = ("-c:v", "libx264", "-crf", str(VIDEO_CRF), "-pix_fmt", PIXEL_FORMAT)
AUDIO_CODEC_ARGS = (
    "-c:a",
    "aac",
    "-b:a",
    AUDIO_BITRATE,
    "-ar",
    str(AUDIO_SAMPLE_RATE_HZ),
    "-ac",
    str(AUDIO_CHANNEL_COUNT),
)
FAST_START_ARGS = ("-movflags", "+faststart")
PROBE_ARGS = ("-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json")
OUTLINE_BORDER_STYLE = 1
FONT_SIZES_BY_ORIENTATION = {Orientation.LANDSCAPE: 20, Orientation.PORTRAIT: 12}
SUBTITLE_LOOKS_BY_STYLE = {
    SubtitleStyle.CLEAN_WHITE: SubtitleLook(
        font_name="Arial",
        primary_colour="&H00FFFFFF",
        outline_colour="&H00202020",
        back_colour="&H80000000",
        outline_px=1.0,
        shadow_px=1.5,
        margin_side_px=20,
        margin_bottom_px=24,
    ),
    SubtitleStyle.CINEMATIC_GOLD: SubtitleLook(
        font_name="Georgia",
        primary_colour="&H005CA6C9",
        outline_colour="&H00101010",
        back_colour="&H99000000",
        outline_px=2.0,
        shadow_px=1.0,
        margin_side_px=60,
        margin_bottom_px=36,
    ),
    SubtitleStyle.CYBER_AMBER: SubtitleLook(
        font_name="Arial",
        primary_colour="&H0000BFFF",
        outline_colour="&H00000000",
        back_colour="&H6000BFFF",
        outline_px=2.5,
        shadow_px=2.0,
        margin_side_px=20,
        margin_bottom_px=28,
    ),
    SubtitleStyle.EMERALD_HUD: SubtitleLook(
        font_name="Courier New",
        primary_colour="&H00C0FFC0",
        outline_colour="&H00103010",
        back_colour="&H80002000",
        outline_px=1.2,
        shadow_px=0.5,
        margin_side_px=20,
        margin_bottom_px=28,
    ),
}


@dataclass(frozen=True)
class SceneEncoding:
    cut: SceneCut
    orientation: Orientation
    output_path: Path


@dataclass(frozen=True)
class MusicMix:
    music_path: Path
    volume: float
    film_ms: int


@dataclass(frozen=True)
class BurnedSubtitles:
    file_name: str
    style: SubtitleStyle
    orientation: Orientation


@dataclass(frozen=True)
class FilmFinish:
    joined_path: Path
    output_path: Path
    music: MusicMix | None
    subtitles: BurnedSubtitles | None


@dataclass(frozen=True)
class MediaFacts:
    duration_ms: int
    has_sound: bool


def to_seconds_text(duration_ms: int) -> str:
    return f"{duration_ms / MS_PER_SECOND:.3f}"


def build_fit_filter(frame_size: FrameSize) -> str:
    width_px, height_px = frame_size.width_px, frame_size.height_px
    return (
        f"scale={width_px}:{height_px}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"pad={width_px}:{height_px}:(ow-iw)/2:(oh-ih)/2,"
        f"setsar=1,fps={FRAME_RATE_FPS},format={PIXEL_FORMAT}"
    )


def build_scene_filter_graph(encoding: SceneEncoding) -> str:
    cut = encoding.cut
    picture_chain = f"[0:v]{build_fit_filter(FRAME_SIZES_BY_ORIENTATION[encoding.orientation])}[v]"
    sound_input = 0 if cut.has_clip_sound else 1
    if cut.narration is None:
        return f"{picture_chain};[{sound_input}:a]apad[a]"
    return (
        f"{picture_chain};"
        f"[{sound_input}:a]volume={CLIP_SOUND_VOLUME:g}[clip_sound];"
        f"[{sound_input + 1}:a]volume={NARRATION_VOLUME:g}[narration];"
        "[clip_sound][narration]amix=inputs=2:duration=longest:normalize=0,apad[a]"
    )


def build_scene_encode_args(encoding: SceneEncoding) -> list[str]:
    cut = encoding.cut
    return [
        *_to_scene_input_args(cut),
        "-filter_complex",
        build_scene_filter_graph(encoding),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        to_seconds_text(cut.length_ms),
        *VIDEO_CODEC_ARGS,
        *AUDIO_CODEC_ARGS,
        str(encoding.output_path),
    ]


def _to_scene_input_args(cut: SceneCut) -> list[str]:
    input_args = ["-ss", to_seconds_text(cut.clip_start_ms), "-i", str(cut.clip_path)]
    if not cut.has_clip_sound:
        input_args += ["-f", "lavfi", "-i", SILENCE_SOURCE]
    if cut.narration is not None:
        input_args += ["-i", str(cut.narration.path)]
    return input_args


def build_concat_list_text(scene_file_names: Sequence[str]) -> str:
    return "".join(f"file '{file_name}'\n" for file_name in scene_file_names)


def build_concat_args(list_path: Path, output_path: Path) -> list[str]:
    return ["-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(output_path)]


def build_finish_args(finish: FilmFinish) -> list[str]:
    return [
        *_to_finish_input_args(finish),
        *_to_finish_filter_args(finish),
        *_to_finish_video_args(finish.subtitles),
        *_to_finish_audio_args(finish.music),
        *FAST_START_ARGS,
        str(finish.output_path),
    ]


def _to_finish_input_args(finish: FilmFinish) -> list[str]:
    input_args = ["-i", str(finish.joined_path)]
    if finish.music is not None:
        input_args += ["-i", str(finish.music.music_path)]
    return input_args


def _to_finish_filter_args(finish: FilmFinish) -> list[str]:
    filter_chains = [
        chain
        for chain in (build_burn_chain(finish.subtitles), build_music_chain(finish.music))
        if chain
    ]
    if not filter_chains:
        return []
    return ["-filter_complex", ";".join(filter_chains)]


def _to_finish_video_args(subtitles: BurnedSubtitles | None) -> list[str]:
    if subtitles is None:
        return ["-map", "0:v", "-c:v", "copy"]
    return ["-map", "[v]", *VIDEO_CODEC_ARGS]


def _to_finish_audio_args(music: MusicMix | None) -> list[str]:
    if music is None:
        return ["-map", "0:a", "-c:a", "copy"]
    return ["-map", "[a]", *AUDIO_CODEC_ARGS]


def build_burn_chain(subtitles: BurnedSubtitles | None) -> str:
    if subtitles is None:
        return ""
    force_style = build_force_style(subtitles.style, subtitles.orientation)
    return f"[0:v]subtitles=filename={subtitles.file_name}:force_style='{force_style}'[v]"


def build_music_chain(music: MusicMix | None) -> str:
    if music is None:
        return ""
    fade_start_ms = max(music.film_ms - MUSIC_FADE_OUT_MS, 0)
    return (
        f"[1:a]volume={music.volume:g},"
        f"afade=t=out:st={to_seconds_text(fade_start_ms)}:d={to_seconds_text(MUSIC_FADE_OUT_MS)}"
        "[music];[0:a][music]amix=inputs=2:duration=first:normalize=0[a]"
    )


def build_force_style(style: SubtitleStyle, orientation: Orientation) -> str:
    look = SUBTITLE_LOOKS_BY_STYLE[style]
    fields = {
        "FontName": look.font_name,
        "FontSize": FONT_SIZES_BY_ORIENTATION[orientation],
        "PrimaryColour": look.primary_colour,
        "OutlineColour": look.outline_colour,
        "BackColour": look.back_colour,
        "BorderStyle": OUTLINE_BORDER_STYLE,
        "Outline": look.outline_px,
        "Shadow": look.shadow_px,
        "MarginL": look.margin_side_px,
        "MarginR": look.margin_side_px,
        "MarginV": look.margin_bottom_px,
    }
    return ",".join(f"{name}={value}" for name, value in fields.items())


def build_probe_args(media_path: Path) -> list[str]:
    return [*PROBE_ARGS, str(media_path)]


def ffprobe_json_to_media_facts(stdout: str) -> MediaFacts:
    try:
        report = json.loads(stdout)
        duration_ms = round(float(report["format"]["duration"]) * MS_PER_SECOND)
    except (ValueError, KeyError, TypeError) as error:
        raise CommandError(PROBE_NO_DURATION_MESSAGE) from error
    streams = report.get("streams", [])
    return MediaFacts(
        duration_ms=duration_ms,
        has_sound=any(stream.get("codec_type") == AUDIO_CODEC_TYPE for stream in streams),
    )
