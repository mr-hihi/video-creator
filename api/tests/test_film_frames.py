import pytest

from app.modules.jobs.film_analysis.frames import (
    FilmFrame,
    FrameCandidates,
    FrameKind,
    ffmpeg_metadata_to_cut_times_ms,
    merge_film_frames,
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
SOUND_MOMENTS = [
    KeyMoment(at_ms=5_000, title="Ambient: a dog barks"),
    KeyMoment(at_ms=11_000, title="Action: a door slams"),
    KeyMoment(at_ms=20_000, title="Silence: the room goes quiet"),
    KeyMoment(at_ms=40_000, title="Music: drums start"),
]
SOUND_CANDIDATES = FrameCandidates(
    dialogue_moments=DIALOGUE_MOMENTS,
    cut_times_ms=[15_000, 21_000, 30_000, 45_000, 70_000],
    duration_ms=600_000,
    sound_moments=SOUND_MOMENTS,
)
FFMPEG_METADATA = (
    "frame:0    pts:50176   pts_time:3.266667\n"
    "lavfi.scene_score=0.655697\n"
    "frame:1    pts:81408   pts_time:5.3\n"
    "lavfi.scene_score=0.623946\n"
)


def frame_times_ms(max_frames: int, candidates: FrameCandidates = CANDIDATES) -> list[int]:
    merged = merge_film_frames(candidates, max_frames)
    return [frame.moment.at_ms for frame in merged.frames]


@pytest.fixture
def merged_with_room_for_every_cut():
    return merge_film_frames(CANDIDATES, 8)


@pytest.fixture
def times_with_three_slots():
    return frame_times_ms(6)


@pytest.fixture
def times_without_slots():
    return frame_times_ms(3)


@pytest.fixture
def merged_without_cuts():
    return merge_film_frames(
        FrameCandidates(dialogue_moments=DIALOGUE_MOMENTS, cut_times_ms=[], duration_ms=600_000),
        40,
    )


@pytest.fixture
def scene_titles(merged_with_room_for_every_cut):
    return {
        frame.moment.title
        for frame in merged_with_room_for_every_cut.frames
        if frame.kind is FrameKind.SCENE
    }


@pytest.fixture
def merged_with_room_for_sounds_and_cuts():
    return merge_film_frames(SOUND_CANDIDATES, 9)


@pytest.fixture
def merged_with_two_sound_slots():
    return merge_film_frames(SOUND_CANDIDATES, 5)


def test_merge_drops_crowded_cuts_and_keeps_the_rest(merged_with_room_for_every_cut):
    assert [frame.moment.at_ms for frame in merged_with_room_for_every_cut.frames] == [
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
    assert merged_without_cuts.frames == [
        FilmFrame(moment, FrameKind.DIALOGUE) for moment in DIALOGUE_MOMENTS
    ]
    assert (merged_without_cuts.sound_count, merged_without_cuts.scene_count) == (0, 0)


def test_merge_titles_scene_frames_as_scene_change(scene_titles):
    assert scene_titles == {"Scene change"}


def test_merge_adds_sounds_away_from_dialogue_and_cuts_away_from_both(
    merged_with_room_for_sounds_and_cuts,
):
    assert [
        (frame.moment.at_ms, frame.kind) for frame in merged_with_room_for_sounds_and_cuts.frames
    ] == [
        (0, FrameKind.DIALOGUE),
        (5_000, FrameKind.SOUND),
        (10_000, FrameKind.DIALOGUE),
        (15_000, FrameKind.SCENE),
        (20_000, FrameKind.SOUND),
        (30_000, FrameKind.SCENE),
        (40_000, FrameKind.SOUND),
        (45_000, FrameKind.SCENE),
        (60_000, FrameKind.DIALOGUE),
    ]
    assert (
        merged_with_room_for_sounds_and_cuts.dialogue_count,
        merged_with_room_for_sounds_and_cuts.sound_count,
        merged_with_room_for_sounds_and_cuts.scene_count,
    ) == (3, 3, 3)


def test_merge_titles_sound_frames_with_their_kind_label(merged_with_room_for_sounds_and_cuts):
    assert [
        frame.moment.title
        for frame in merged_with_room_for_sounds_and_cuts.frames
        if frame.kind is FrameKind.SOUND
    ] == ["Ambient: a dog barks", "Silence: the room goes quiet", "Music: drums start"]


def test_merge_spreads_sounds_over_the_free_slots_before_any_cut(merged_with_two_sound_slots):
    assert [(frame.moment.at_ms, frame.kind) for frame in merged_with_two_sound_slots.frames] == [
        (0, FrameKind.DIALOGUE),
        (5_000, FrameKind.SOUND),
        (10_000, FrameKind.DIALOGUE),
        (20_000, FrameKind.SOUND),
        (60_000, FrameKind.DIALOGUE),
    ]
    assert (
        merged_with_two_sound_slots.dialogue_count,
        merged_with_two_sound_slots.sound_count,
        merged_with_two_sound_slots.scene_count,
    ) == (3, 2, 0)


def test_ffmpeg_metadata_to_cut_times_ms_reads_every_pts_time():
    assert ffmpeg_metadata_to_cut_times_ms(FFMPEG_METADATA) == [3267, 5300]


def test_ffmpeg_metadata_to_cut_times_ms_returns_nothing_for_empty_output():
    assert ffmpeg_metadata_to_cut_times_ms("") == []
