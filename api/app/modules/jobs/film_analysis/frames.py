import re
from dataclasses import dataclass

from app.common.sequences import spread_evenly
from app.modules.jobs.video_to_markdown.moments import (
    FRAME_END_MARGIN_MS,
    MIN_MOMENT_GAP_MS,
    KeyMoment,
)

SCENE_CHANGE_TITLE = "Scene change"
PTS_TIME_PATTERN = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
MS_PER_SECOND = 1000


@dataclass(frozen=True)
class FrameCandidates:
    dialogue_moments: list[KeyMoment]
    cut_times_ms: list[int]
    duration_ms: int


@dataclass(frozen=True)
class MergedFrames:
    moments: list[KeyMoment]
    dialogue_count: int
    scene_count: int


def ffmpeg_metadata_to_cut_times_ms(metadata_output: str) -> list[int]:
    return [
        round(float(seconds) * MS_PER_SECOND)
        for seconds in PTS_TIME_PATTERN.findall(metadata_output)
    ]


def merge_dialogue_and_scene_frames(candidates: FrameCandidates, max_frames: int) -> MergedFrames:
    dialogue_moments = candidates.dialogue_moments
    slot_count = max(max_frames - len(dialogue_moments), 0)
    kept_cut_times_ms = spread_evenly(_drop_crowded_cuts(candidates), slot_count)
    scene_moments = [
        KeyMoment(at_ms=cut_ms, title=SCENE_CHANGE_TITLE) for cut_ms in kept_cut_times_ms
    ]
    return MergedFrames(
        moments=sorted([*dialogue_moments, *scene_moments], key=lambda moment: moment.at_ms),
        dialogue_count=len(dialogue_moments),
        scene_count=len(scene_moments),
    )


def _drop_crowded_cuts(candidates: FrameCandidates) -> list[int]:
    last_capturable_ms = candidates.duration_ms - FRAME_END_MARGIN_MS
    dialogue_times_ms = [moment.at_ms for moment in candidates.dialogue_moments]
    kept_cut_times_ms: list[int] = []
    for cut_ms in sorted(candidates.cut_times_ms):
        is_after_last_frame = cut_ms > last_capturable_ms
        is_near_dialogue = any(
            abs(cut_ms - at_ms) < MIN_MOMENT_GAP_MS for at_ms in dialogue_times_ms
        )
        is_near_previous_cut = bool(kept_cut_times_ms) and (
            cut_ms - kept_cut_times_ms[-1] < MIN_MOMENT_GAP_MS
        )
        if is_after_last_frame or is_near_dialogue or is_near_previous_cut:
            continue
        kept_cut_times_ms.append(cut_ms)
    return kept_cut_times_ms
