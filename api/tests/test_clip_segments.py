import pytest

from app.modules.media_generation.clip_segments import (
    ClipPlan,
    build_segment_prompt,
    calculate_segment_window,
    plan_clip_segments,
)

FIVE_SEGMENTS = ClipPlan(clip_length_s=30, segment_lengths_s=(8, 8, 8, 8, 8))


@pytest.mark.parametrize(
    ("clip_length_s", "model_lengths_s", "segment_lengths_s"),
    [
        (30, (8,), (8, 8, 8, 8, 8)),
        (30, (4, 6, 8), (8, 8, 8, 8, 4)),
        (30, (4, 5, 6, 7, 8, 9, 10), (10, 10, 10, 4)),
        (10, (4, 6, 8), (8, 4)),
        (9, (6, 10), (10,)),
        (22, (8,), (8, 8, 8)),
        (15, (8,), (8, 8)),
        (22, (4, 5, 6, 7, 8, 9, 10), (10, 10, 4)),
        (6, (8,), (8,)),
        (6, (4, 5, 6, 7, 8, 9, 10), (6,)),
    ],
)
def test_the_plan_joins_the_fewest_clips_that_cover_the_scene(
    clip_length_s, model_lengths_s, segment_lengths_s
):
    assert plan_clip_segments(clip_length_s, model_lengths_s).segment_lengths_s == (
        segment_lengths_s
    )


@pytest.mark.parametrize("model_lengths_s", [(), (1,)])
def test_a_model_without_usable_clip_lengths_asks_for_the_scene_length(model_lengths_s):
    assert plan_clip_segments(12, model_lengths_s).segment_lengths_s == (12,)


@pytest.mark.parametrize(
    ("plan", "is_cut_or_joined"),
    [
        (ClipPlan(clip_length_s=8, segment_lengths_s=(8,)), False),
        (ClipPlan(clip_length_s=6, segment_lengths_s=(8,)), True),
        (ClipPlan(clip_length_s=15, segment_lengths_s=(8, 8)), True),
    ],
)
def test_only_a_clip_made_at_the_scene_length_needs_no_editing(plan, is_cut_or_joined):
    assert plan.is_cut_or_joined is is_cut_or_joined


def test_each_segment_shows_its_window_of_the_scene():
    assert [calculate_segment_window(FIVE_SEGMENTS, number) for number in range(1, 6)] == [
        (0, 8),
        (8, 15),
        (15, 22),
        (22, 29),
        (29, 30),
    ]


def test_the_first_segment_prompt_names_its_part_and_window():
    assert build_segment_prompt(FIVE_SEGMENTS, 1, "A pier at dawn") == (
        "Part 1 of 5. Show 0-8s of this shot.\nA pier at dawn"
    )


def test_a_later_segment_prompt_continues_from_the_start_image():
    assert build_segment_prompt(FIVE_SEGMENTS, 3, "A pier at dawn") == (
        "Part 3 of 5. Show 15-22s of this shot. Continue from the start image.\nA pier at dawn"
    )
