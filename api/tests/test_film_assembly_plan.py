from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.modules.films.assembly_plan import (
    NarrationTake,
    SceneCut,
    SceneSource,
    SubtitleCue,
    build_assembly_plan,
    ensure_every_clip_done,
    ensure_every_part_has_scenes,
    format_srt_time,
    is_music_used,
    is_narration_used,
    measure_kept_ms,
    measure_scene_ms,
    to_srt_text,
)
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import Episode, EpisodePart, FilmProject, MediaStatus, Scene

CLIP_8_PATH = Path("/films/clip-8.mp4")
NAR_3 = NarrationTake(path=Path("/films/nar-3.wav"), duration_ms=3200, text="The fog rolls in.")
NAR_8 = NarrationTake(
    path=Path("/films/nar-8.wav"), duration_ms=8000, text="The bell rings under the water."
)


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_scene(position: int, **values) -> Scene:
    defaults = {
        "id": f"s{position + 1}",
        "position": position,
        "clip_status": MediaStatus.DONE,
        "clip_path": f"projects/p1/episodes/e1/scenes/s{position + 1}/clip.mp4",
        "narration_status": MediaStatus.NONE,
        "narration_path": None,
    }
    return Scene(**{**defaults, **values})


def build_source(**values) -> SceneSource:
    defaults = {
        "clip_path": CLIP_8_PATH,
        "clip_duration_ms": 8000,
        "has_clip_sound": True,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
        "narration": None,
    }
    return SceneSource(**{**defaults, **values})


def raised_message(scenes: list[Scene]) -> str:
    with pytest.raises(EpisodeStepFailedError) as error_info:
        ensure_every_clip_done(scenes)
    return str(error_info.value)


@pytest.fixture
def no_scenes_message():
    return raised_message([])


@pytest.fixture
def reset_clip_message():
    return raised_message(
        [build_scene(0), build_scene(1), build_scene(2, clip_status=MediaStatus.NONE)]
    )


@pytest.fixture
def pathless_clip_message():
    return raised_message([build_scene(0, clip_path=None)])


@pytest.fixture
def every_clip_done_result():
    return ensure_every_clip_done([build_scene(0), build_scene(1)])


@pytest.fixture
def second_part_clip_message():
    return raised_message(
        [
            build_scene(0, part_id="pt1"),
            build_scene(1, part_id="pt1"),
            build_scene(0, id="s9", part_id="pt2", clip_status=MediaStatus.FAILED),
        ]
    )


def parts_check_message(parts: list[EpisodePart], scenes: list[Scene]) -> str | None:
    try:
        ensure_every_part_has_scenes(parts, scenes)
    except EpisodeStepFailedError as error:
        return str(error)
    return None


@pytest.fixture
def empty_part_message():
    return parts_check_message(
        [EpisodePart(id="pt1", position=0), EpisodePart(id="pt2", position=1)],
        [build_scene(0, part_id="pt1")],
    )


@pytest.fixture
def filled_parts_message():
    return parts_check_message(
        [EpisodePart(id="pt1", position=0), EpisodePart(id="pt2", position=1)],
        [build_scene(0, part_id="pt1"), build_scene(0, id="s9", part_id="pt2")],
    )


@pytest.fixture(
    params=[
        ({"allow_narration": False}, {"narration_status": MediaStatus.DONE}, False),
        ({"allow_narration": True}, {"narration_status": MediaStatus.FAILED}, False),
        ({"allow_narration": True}, {"narration_status": MediaStatus.DONE}, False),
        (
            {"allow_narration": True},
            {"narration_status": MediaStatus.DONE, "narration_path": "n.wav"},
            True,
        ),
    ]
)
def narration_use(request):
    project_values, scene_values, expected = request.param
    project = FilmProject(**project_values)
    scene = build_scene(0, **{"narration_path": None, **scene_values})
    return Outcome(is_narration_used(project, scene), expected)


@pytest.fixture(
    params=[
        ({"allow_music": False}, {"music_status": MediaStatus.DONE, "music_path": "m.mp3"}, False),
        ({"allow_music": True}, {"music_status": MediaStatus.FAILED, "music_path": None}, False),
        ({"allow_music": True}, {"music_status": MediaStatus.DONE, "music_path": None}, False),
        ({"allow_music": True}, {"music_status": MediaStatus.DONE, "music_path": "m.mp3"}, True),
    ]
)
def music_use(request):
    project_values, episode_values, expected = request.param
    return Outcome(
        is_music_used(FilmProject(**project_values), Episode(**episode_values)), expected
    )


@pytest.fixture(
    params=[
        ({"trim_start_ms": 1000, "trim_end_ms": None}, 7000),
        ({"trim_start_ms": 500, "trim_end_ms": 6500}, 6000),
        ({"trim_start_ms": 1000, "trim_end_ms": 9000}, 7000),
        ({"trim_start_ms": 9000, "trim_end_ms": None}, 0),
    ]
)
def kept_length(request):
    values, expected = request.param
    return Outcome(measure_kept_ms(build_source(**values)), expected)


@pytest.fixture(
    params=[
        (None, 7000),
        (NAR_3, 3700),
        (NAR_8, 7000),
        (NarrationTake(Path("n.wav"), 6600, "Near the end."), 7000),
    ]
)
def scene_length(request):
    narration, expected = request.param
    return Outcome(measure_scene_ms(build_source(narration=narration)), expected)


@pytest.fixture
def three_scene_plan():
    return build_assembly_plan(
        [
            build_source(narration=NAR_3),
            build_source(narration=NAR_8, has_clip_sound=False),
            build_source(),
        ]
    )


@pytest.fixture
def empty_plan():
    return build_assembly_plan([])


@pytest.fixture
def two_cue_srt():
    return to_srt_text(
        [
            SubtitleCue(start_ms=0, end_ms=3200, text="The fog rolls in."),
            SubtitleCue(start_ms=3700, end_ms=10_700, text="The bell rings under the water."),
        ]
    )


@pytest.fixture
def multi_line_srt():
    return to_srt_text([SubtitleCue(start_ms=0, end_ms=1500, text="  First line\n\n Second \n")])


@pytest.fixture
def empty_srt():
    return to_srt_text([])


@pytest.fixture(params=[(0, "00:00:00,000"), (10_700, "00:00:10,700"), (3_723_456, "01:02:03,456")])
def srt_time(request):
    at_ms, expected = request.param
    return Outcome(format_srt_time(at_ms), expected)


def test_ensure_every_clip_done_rejects_an_episode_without_scenes(no_scenes_message):
    assert no_scenes_message == "Assembly failed: the episode has no scenes"


def test_ensure_every_clip_done_names_the_first_scene_without_a_clip(reset_clip_message):
    assert reset_clip_message == "Scene 3 has no clip"


def test_ensure_every_clip_done_rejects_a_done_clip_without_a_file(pathless_clip_message):
    assert pathless_clip_message == "Scene 1 has no clip"


def test_ensure_every_clip_done_counts_scenes_across_parts(second_part_clip_message):
    assert second_part_clip_message == "Scene 3 has no clip"


def test_ensure_every_part_has_scenes_names_the_empty_part(empty_part_message):
    assert empty_part_message == "Part 2 has no scenes"


def test_ensure_every_part_has_scenes_accepts_parts_with_scenes(filled_parts_message):
    assert filled_parts_message is None


def test_ensure_every_clip_done_accepts_scenes_with_clips(every_clip_done_result):
    assert every_clip_done_result is None


def test_is_narration_used_needs_the_project_switch_and_a_done_file(narration_use):
    assert narration_use.actual is narration_use.expected


def test_is_music_used_needs_the_project_switch_and_a_done_file(music_use):
    assert music_use.actual is music_use.expected


def test_measure_kept_ms_keeps_the_trimmed_part_inside_the_clip(kept_length):
    assert kept_length.actual == kept_length.expected


def test_measure_scene_ms_ends_500_ms_after_the_narration_within_the_kept_part(scene_length):
    assert scene_length.actual == scene_length.expected


def test_build_assembly_plan_times_each_scene(three_scene_plan):
    assert three_scene_plan.cuts == (
        SceneCut(CLIP_8_PATH, True, 1000, 3700, NAR_3),
        SceneCut(CLIP_8_PATH, False, 1000, 7000, NAR_8),
        SceneCut(CLIP_8_PATH, True, 1000, 7000, None),
    )


def test_build_assembly_plan_cues_each_used_narration_capped_at_its_scene(three_scene_plan):
    assert three_scene_plan.cues == (
        SubtitleCue(start_ms=0, end_ms=3200, text="The fog rolls in."),
        SubtitleCue(start_ms=3700, end_ms=10_700, text="The bell rings under the water."),
    )


def test_build_assembly_plan_of_no_scene_is_empty(empty_plan):
    assert (empty_plan.cuts, empty_plan.cues) == ((), ())


def test_to_srt_text_numbers_and_times_each_cue(two_cue_srt):
    assert two_cue_srt == (
        "1\n00:00:00,000 --> 00:00:03,200\nThe fog rolls in.\n"
        "\n"
        "2\n00:00:03,700 --> 00:00:10,700\nThe bell rings under the water.\n"
    )


def test_to_srt_text_drops_blank_lines_inside_a_cue(multi_line_srt):
    assert multi_line_srt == "1\n00:00:00,000 --> 00:00:01,500\nFirst line\nSecond\n"


def test_to_srt_text_without_cues_is_empty(empty_srt):
    assert empty_srt == ""


def test_format_srt_time_writes_hours_minutes_seconds_and_milliseconds(srt_time):
    assert srt_time.actual == srt_time.expected
