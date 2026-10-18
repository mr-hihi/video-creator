from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.common.process import CommandError
from app.modules.films.assembly_commands import (
    BurnedSubtitles,
    FilmFinish,
    MediaFacts,
    MusicMix,
    SceneEncoding,
    build_concat_args,
    build_concat_list_text,
    build_finish_args,
    build_force_style,
    build_probe_args,
    build_scene_encode_args,
    ffprobe_json_to_media_facts,
)
from app.modules.films.assembly_plan import NarrationTake, SceneCut
from app.modules.films.models import Orientation, SubtitleStyle

CLIP_PATH = Path("/films/s1/clip.mp4")
NARRATION_PATH = Path("/films/s1/narration.wav")
WORK_DIR = Path("/tmp/film-assembly-1")
LANDSCAPE_PICTURE = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p[v]"
)
PORTRAIT_PICTURE = (
    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24,format=yuv420p[v]"
)
SCENE_OUTPUT_ARGS = [
    "-c:v",
    "libx264",
    "-crf",
    "18",
    "-pix_fmt",
    "yuv420p",
    "-c:a",
    "aac",
    "-b:a",
    "192k",
    "-ar",
    "48000",
    "-ac",
    "2",
    "/tmp/film-assembly-1/scene-001.mp4",
]
SILENCE = "anullsrc=channel_layout=stereo:sample_rate=48000"
CLEAN_WHITE_LANDSCAPE = (
    "FontName=Arial,FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00202020,"
    "BackColour=&H80000000,BorderStyle=1,Outline=1.0,Shadow=1.5,MarginL=20,MarginR=20,MarginV=24"
)
CINEMATIC_GOLD_PORTRAIT = (
    "FontName=Georgia,FontSize=12,PrimaryColour=&H005CA6C9,OutlineColour=&H00101010,"
    "BackColour=&H99000000,BorderStyle=1,Outline=2.0,Shadow=1.0,MarginL=60,MarginR=60,MarginV=36"
)
CYBER_AMBER_LANDSCAPE = (
    "FontName=Arial,FontSize=20,PrimaryColour=&H0000BFFF,OutlineColour=&H00000000,"
    "BackColour=&H6000BFFF,BorderStyle=1,Outline=2.5,Shadow=2.0,MarginL=20,MarginR=20,MarginV=28"
)
EMERALD_HUD_LANDSCAPE = (
    "FontName=Courier New,FontSize=20,PrimaryColour=&H00C0FFC0,OutlineColour=&H00103010,"
    "BackColour=&H80002000,BorderStyle=1,Outline=1.2,Shadow=0.5,MarginL=20,MarginR=20,MarginV=28"
)


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def encode_args(cut: SceneCut, orientation: Orientation = Orientation.LANDSCAPE) -> list[str]:
    return build_scene_encode_args(
        SceneEncoding(cut=cut, orientation=orientation, output_path=WORK_DIR / "scene-001.mp4")
    )


def finish_args(music: MusicMix | None, subtitles: BurnedSubtitles | None) -> list[str]:
    return build_finish_args(
        FilmFinish(
            joined_path=WORK_DIR / "joined.mp4",
            output_path=WORK_DIR / "film.mp4",
            music=music,
            subtitles=subtitles,
        )
    )


@pytest.fixture
def narrated_scene_args():
    narration = NarrationTake(path=NARRATION_PATH, duration_ms=3200, text="The fog rolls in.")
    return encode_args(SceneCut(CLIP_PATH, True, 1000, 3700, narration))


@pytest.fixture
def silent_narrated_scene_args():
    narration = NarrationTake(path=NARRATION_PATH, duration_ms=3200, text="The fog rolls in.")
    return encode_args(SceneCut(CLIP_PATH, False, 1000, 3700, narration), Orientation.PORTRAIT)


@pytest.fixture
def plain_scene_args():
    return encode_args(SceneCut(CLIP_PATH, True, 1250, 7000, None))


@pytest.fixture
def silent_plain_scene_args():
    return encode_args(SceneCut(CLIP_PATH, False, 0, 6000, None))


@pytest.fixture
def concat_list_text():
    return build_concat_list_text(["scene-001.mp4", "scene-002.mp4"])


@pytest.fixture
def concat_args():
    return build_concat_args(WORK_DIR / "scenes.txt", WORK_DIR / "joined.mp4")


@pytest.fixture
def copy_finish_args():
    return finish_args(None, None)


@pytest.fixture
def music_finish_args():
    return finish_args(MusicMix(Path("/films/music.mp3"), 0.2, 21_000), None)


@pytest.fixture
def short_film_music_finish_args():
    return finish_args(MusicMix(Path("/films/music.mp3"), 0.25, 1500), None)


@pytest.fixture
def burned_finish_args():
    subtitles = BurnedSubtitles("subtitles.srt", SubtitleStyle.CLEAN_WHITE, Orientation.LANDSCAPE)
    return finish_args(None, subtitles)


@pytest.fixture
def music_and_burned_finish_args():
    subtitles = BurnedSubtitles("subtitles.srt", SubtitleStyle.CYBER_AMBER, Orientation.LANDSCAPE)
    return finish_args(MusicMix(Path("/films/music.mp3"), 0.2, 21_000), subtitles)


@pytest.fixture(
    params=[
        (SubtitleStyle.CLEAN_WHITE, Orientation.LANDSCAPE, CLEAN_WHITE_LANDSCAPE),
        (SubtitleStyle.CINEMATIC_GOLD, Orientation.PORTRAIT, CINEMATIC_GOLD_PORTRAIT),
        (SubtitleStyle.CYBER_AMBER, Orientation.LANDSCAPE, CYBER_AMBER_LANDSCAPE),
        (SubtitleStyle.EMERALD_HUD, Orientation.LANDSCAPE, EMERALD_HUD_LANDSCAPE),
    ]
)
def force_style(request):
    style, orientation, expected = request.param
    return Outcome(build_force_style(style, orientation), expected)


@pytest.fixture
def probe_args():
    return build_probe_args(CLIP_PATH)


@pytest.fixture(
    params=[
        (
            '{"streams":[{"codec_type":"video"},{"codec_type":"audio"}],'
            '"format":{"duration":"8.000000"}}',
            MediaFacts(duration_ms=8000, has_sound=True),
        ),
        (
            '{"streams":[{"codec_type":"video"}],"format":{"duration":"4.349999"}}',
            MediaFacts(duration_ms=4350, has_sound=False),
        ),
        ('{"format":{"duration":"3.2"}}', MediaFacts(duration_ms=3200, has_sound=False)),
    ]
)
def probed_facts(request):
    stdout, expected = request.param
    return Outcome(ffprobe_json_to_media_facts(stdout), expected)


@pytest.fixture(params=["", "not json", '{"streams":[]}', '{"format":{"duration":"N/A"}}', "[]"])
def probe_error(request):
    with pytest.raises(CommandError) as error_info:
        ffprobe_json_to_media_facts(request.param)
    return str(error_info.value)


def test_scene_args_mix_clip_sound_under_narration(narrated_scene_args):
    assert narrated_scene_args == [
        "-ss",
        "1.000",
        "-i",
        "/films/s1/clip.mp4",
        "-i",
        "/films/s1/narration.wav",
        "-filter_complex",
        f"{LANDSCAPE_PICTURE};[0:a]volume=0.3[clip_sound];[1:a]volume=1.5[narration];"
        "[clip_sound][narration]amix=inputs=2:duration=longest:normalize=0,apad[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "3.700",
        *SCENE_OUTPUT_ARGS,
    ]


def test_scene_args_mix_silence_under_narration_for_a_silent_clip(silent_narrated_scene_args):
    assert silent_narrated_scene_args == [
        "-ss",
        "1.000",
        "-i",
        "/films/s1/clip.mp4",
        "-f",
        "lavfi",
        "-i",
        SILENCE,
        "-i",
        "/films/s1/narration.wav",
        "-filter_complex",
        f"{PORTRAIT_PICTURE};[1:a]volume=0.3[clip_sound];[2:a]volume=1.5[narration];"
        "[clip_sound][narration]amix=inputs=2:duration=longest:normalize=0,apad[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "3.700",
        *SCENE_OUTPUT_ARGS,
    ]


def test_scene_args_keep_clip_sound_as_is_without_narration(plain_scene_args):
    assert plain_scene_args == [
        "-ss",
        "1.250",
        "-i",
        "/films/s1/clip.mp4",
        "-filter_complex",
        f"{LANDSCAPE_PICTURE};[0:a]apad[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "7.000",
        *SCENE_OUTPUT_ARGS,
    ]


def test_scene_args_use_silence_for_a_silent_clip_without_narration(silent_plain_scene_args):
    assert silent_plain_scene_args == [
        "-ss",
        "0.000",
        "-i",
        "/films/s1/clip.mp4",
        "-f",
        "lavfi",
        "-i",
        SILENCE,
        "-filter_complex",
        f"{LANDSCAPE_PICTURE};[1:a]apad[a]",
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "6.000",
        *SCENE_OUTPUT_ARGS,
    ]


def test_concat_list_names_the_scene_files_in_order(concat_list_text):
    assert concat_list_text == "file 'scene-001.mp4'\nfile 'scene-002.mp4'\n"


def test_concat_args_copy_the_streams(concat_args):
    assert concat_args == [
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "/tmp/film-assembly-1/scenes.txt",
        "-c",
        "copy",
        "/tmp/film-assembly-1/joined.mp4",
    ]


def test_finish_args_copy_the_joined_film_without_music_or_burned_subtitles(copy_finish_args):
    assert copy_finish_args == [
        "-i",
        "/tmp/film-assembly-1/joined.mp4",
        "-map",
        "0:v",
        "-c:v",
        "copy",
        "-map",
        "0:a",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "/tmp/film-assembly-1/film.mp4",
    ]


def test_finish_args_mix_music_under_the_film_with_a_fade_out(music_finish_args):
    assert music_finish_args == [
        "-i",
        "/tmp/film-assembly-1/joined.mp4",
        "-i",
        "/films/music.mp3",
        "-filter_complex",
        "[1:a]volume=0.2,afade=t=out:st=19.000:d=2.000[music];"
        "[0:a][music]amix=inputs=2:duration=first:normalize=0[a]",
        "-map",
        "0:v",
        "-c:v",
        "copy",
        "-map",
        "[a]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        "/tmp/film-assembly-1/film.mp4",
    ]


def test_finish_args_start_the_fade_at_zero_for_a_film_shorter_than_the_fade(
    short_film_music_finish_args,
):
    assert short_film_music_finish_args[5] == (
        "[1:a]volume=0.25,afade=t=out:st=0.000:d=2.000[music];"
        "[0:a][music]amix=inputs=2:duration=first:normalize=0[a]"
    )


def test_finish_args_burn_the_subtitles_in_their_style(burned_finish_args):
    assert burned_finish_args == [
        "-i",
        "/tmp/film-assembly-1/joined.mp4",
        "-filter_complex",
        f"[0:v]subtitles=filename=subtitles.srt:force_style='{CLEAN_WHITE_LANDSCAPE}'[v]",
        "-map",
        "[v]",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-map",
        "0:a",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "/tmp/film-assembly-1/film.mp4",
    ]


def test_finish_args_burn_subtitles_and_mix_music_in_one_graph(music_and_burned_finish_args):
    assert music_and_burned_finish_args[:6] == [
        "-i",
        "/tmp/film-assembly-1/joined.mp4",
        "-i",
        "/films/music.mp3",
        "-filter_complex",
        f"[0:v]subtitles=filename=subtitles.srt:force_style='{CYBER_AMBER_LANDSCAPE}'[v];"
        "[1:a]volume=0.2,afade=t=out:st=19.000:d=2.000[music];"
        "[0:a][music]amix=inputs=2:duration=first:normalize=0[a]",
    ]


def test_force_style_gives_each_style_its_look(force_style):
    assert force_style.actual == force_style.expected


def test_probe_args_ask_for_duration_and_stream_types(probe_args):
    assert probe_args == [
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type",
        "-of",
        "json",
        "/films/s1/clip.mp4",
    ]


def test_ffprobe_json_to_media_facts_reads_duration_and_sound(probed_facts):
    assert probed_facts.actual == probed_facts.expected


def test_ffprobe_json_to_media_facts_rejects_a_report_without_duration(probe_error):
    assert probe_error == "ffprobe returned no duration"
