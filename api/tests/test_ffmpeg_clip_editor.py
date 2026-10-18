from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.common.process import Command, CommandRunner
from app.modules.media_generation.clip_editor import SegmentJoin
from app.modules.media_generation.ffmpeg_clip_editor import ClipEditorConfig, FfmpegClipEditor

CONFIG = ClipEditorConfig(ffmpeg_bin="/usr/bin/ffmpeg", timeout_sec=600)
SEGMENTS = (Path("seg/1.mp4"), Path("seg/2.mp4"), Path("seg/3.mp4"))


def run_editor(edit) -> Command:
    runner = MagicMock(spec=CommandRunner)
    edit(FfmpegClipEditor(CONFIG, runner))
    return runner.run.call_args.args[0]


@pytest.fixture
def last_frame_command():
    return run_editor(
        lambda editor: editor.save_last_frame(Path("seg/1.mp4"), Path("seg/1-last.png"))
    )


@pytest.fixture
def last_frame_args(last_frame_command):
    return last_frame_command.args


@pytest.fixture
def sound_join_args():
    return run_editor(
        lambda editor: editor.join_segments(
            SegmentJoin(SEGMENTS, Path("seg/joined.mp4"), clip_length_s=22, has_sound=True)
        )
    ).args


@pytest.fixture
def silent_join_args():
    return run_editor(
        lambda editor: editor.join_segments(
            SegmentJoin(SEGMENTS[:2], Path("seg/joined.mp4"), clip_length_s=15, has_sound=False)
        )
    ).args


def test_an_edit_runs_ffmpeg_within_the_media_timeout(last_frame_command):
    assert last_frame_command.timeout_sec == 600


def test_the_last_frame_is_read_from_the_clip_end(last_frame_args):
    assert last_frame_args == [
        "/usr/bin/ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-sseof",
        "-0.5",
        "-i",
        "seg/1.mp4",
        "-update",
        "1",
        "seg/1-last.png",
    ]


def test_a_join_drops_the_first_second_of_every_later_segment(sound_join_args):
    graph = sound_join_args[sound_join_args.index("-filter_complex") + 1]
    assert graph == (
        "[0:v]setpts=PTS-STARTPTS,setsar=1[v0];"
        "[0:a]asetpts=PTS-STARTPTS[a0];"
        "[1:v]trim=start=1,setpts=PTS-STARTPTS,setsar=1[v1];"
        "[1:a]atrim=start=1,asetpts=PTS-STARTPTS[a1];"
        "[2:v]trim=start=1,setpts=PTS-STARTPTS,setsar=1[v2];"
        "[2:a]atrim=start=1,asetpts=PTS-STARTPTS[a2];"
        "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]"
    )


def test_a_join_with_sound_maps_both_streams_and_cuts_at_the_scene_length(sound_join_args):
    assert sound_join_args[4:10] == ["-i", "seg/1.mp4", "-i", "seg/2.mp4", "-i", "seg/3.mp4"]
    assert sound_join_args[12:] == [
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-t",
        "22",
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
        "-movflags",
        "+faststart",
        "seg/joined.mp4",
    ]


def test_a_silent_join_joins_only_the_pictures(silent_join_args):
    graph = silent_join_args[silent_join_args.index("-filter_complex") + 1]
    assert graph == (
        "[0:v]setpts=PTS-STARTPTS,setsar=1[v0];"
        "[1:v]trim=start=1,setpts=PTS-STARTPTS,setsar=1[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[v]"
    )
    assert silent_join_args[10:] == [
        "-map",
        "[v]",
        "-t",
        "15",
        "-c:v",
        "libx264",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-an",
        "-movflags",
        "+faststart",
        "seg/joined.mp4",
    ]
