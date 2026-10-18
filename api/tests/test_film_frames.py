import pytest

from app.modules.jobs.film_analysis.frames import (
    FrameCandidates,
    ffmpeg_metadata_to_cut_times_ms,
    merge_dialogue_and_scene_frames,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment

DIALOGUE_MOMENTS = [
    KeyMoment(at_ms=0, title="Mở đầu"),
    KeyMoment(at_ms=10_000, title="Gặp gỡ"),
    KeyMoment(at_ms=60_000, title="Chia tay"),
]
CUT_TIMES_MS = [2_000, 11_000, 15_000, 16_000, 30_000, 45_000, 50_000, 70_000, 599_800]
CANDIDATES = FrameCandidates(
    dialogue_moments=DIALOGUE_MOMENTS, cut_times_ms=CUT_TIMES_MS, duration_ms=600_000
)
FFMPEG_METADATA = (
    "frame:0    pts:50176   pts_time:3.266667\n"
    "lavfi.scene_score=0.655697\n"
    "frame:1    pts:81408   pts_time:5.3\n"
    "lavfi.scene_score=0.623946\n"
)


def frame_times_ms(max_frames: int, candidates: FrameCandidates = CANDIDATES) -> list[int]:
    merged = merge_dialogue_and_scene_frames(candidates, max_frames)
    return [moment.at_ms for moment in merged.moments]


@pytest.fixture
def merged_with_room_for_every_cut():
    return merge_dialogue_and_scene_frames(CANDIDATES, 8)


@pytest.fixture
def times_with_three_slots():
    return frame_times_ms(6)


@pytest.fixture
def times_without_slots():
    return frame_times_ms(3)


@pytest.fixture
def merged_without_cuts():
    return merge_dialogue_and_scene_frames(
        FrameCandidates(dialogue_moments=DIALOGUE_MOMENTS, cut_times_ms=[], duration_ms=600_000),
        40,
    )


@pytest.fixture
def scene_titles(merged_with_room_for_every_cut):
    return {
        moment.title
        for moment in merged_with_room_for_every_cut.moments
        if moment not in DIALOGUE_MOMENTS
    }


def test_merge_drops_crowded_cuts_and_keeps_the_rest(merged_with_room_for_every_cut):
    assert [moment.at_ms for moment in merged_with_room_for_every_cut.moments] == [
        0,
        10_000,
        15_000,
        30_000,
        45_000,
        50_000,
        60_000,
        70_000,
    ]
    assert (
        merged_with_room_for_every_cut.dialogue_count,
        merged_with_room_for_every_cut.scene_count,
    ) == (3, 5)


def test_merge_spreads_cuts_evenly_over_the_free_slots(times_with_three_slots):
    assert times_with_three_slots == [0, 10_000, 15_000, 30_000, 50_000, 60_000]


def test_merge_keeps_only_dialogue_when_no_slot_is_left(times_without_slots):
    assert times_without_slots == [0, 10_000, 60_000]


def test_merge_keeps_dialogue_when_no_cut_is_found(merged_without_cuts):
    assert merged_without_cuts.moments == DIALOGUE_MOMENTS
    assert merged_without_cuts.scene_count == 0


def test_merge_titles_scene_frames_as_scene_change(scene_titles):
    assert scene_titles == {"Scene change"}


def test_ffmpeg_metadata_to_cut_times_ms_reads_every_pts_time():
    assert ffmpeg_metadata_to_cut_times_ms(FFMPEG_METADATA) == [3267, 5300]


def test_ffmpeg_metadata_to_cut_times_ms_returns_nothing_for_empty_output():
    assert ffmpeg_metadata_to_cut_times_ms("") == []
