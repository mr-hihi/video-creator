import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.common.sequences import spread_evenly
from app.modules.jobs.video_to_markdown.moments import (
    FRAME_END_MARGIN_MS,
    MIN_MOMENT_GAP_MS,
    KeyMoment,
)

SCENE_CHANGE_TITLE = "Scene change"
PTS_TIME_PATTERN = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
MS_PER_SECOND = 1000


class FrameKind(StrEnum):
    DIALOGUE = "dialogue"
    SOUND = "sound"
    SCENE = "scene"


@dataclass(frozen=True)
class FilmFrame:
    moment: KeyMoment
    kind: FrameKind


@dataclass(frozen=True)
class FrameCandidates:
    dialogue_moments: list[KeyMoment]
    cut_times_ms: list[int]
    duration_ms: int
    sound_moments: list[KeyMoment] = field(default_factory=list)


@dataclass(frozen=True)
class MergedFrames:
    frames: list[FilmFrame]
    dialogue_count: int
    sound_count: int
    scene_count: int


def ffmpeg_metadata_to_cut_times_ms(metadata_output: str) -> list[int]:
    return [
        round(float(seconds) * MS_PER_SECOND)
        for seconds in PTS_TIME_PATTERN.findall(metadata_output)
    ]


def merge_film_frames(candidates: FrameCandidates, max_frames: int) -> MergedFrames:
    dialogue_moments = candidates.dialogue_moments
    dialogue_times_ms = [moment.at_ms for moment in dialogue_moments]
    sound_slot_count = max(max_frames - len(dialogue_moments), 0)
    sound_moments = spread_evenly(
        [
            moment
            for moment in candidates.sound_moments
            if not is_near_any(moment.at_ms, dialogue_times_ms)
        ],
        sound_slot_count,
    )
    scene_slot_count = max(sound_slot_count - len(sound_moments), 0)
    kept_cut_times_ms = spread_evenly(
        _drop_crowded_cuts(
            candidates, [*dialogue_times_ms, *(moment.at_ms for moment in sound_moments)]
        ),
        scene_slot_count,
    )
    frames = [
        *(FilmFrame(moment, FrameKind.DIALOGUE) for moment in dialogue_moments),
        *(FilmFrame(moment, FrameKind.SOUND) for moment in sound_moments),
        *(
            FilmFrame(KeyMoment(at_ms=cut_ms, title=SCENE_CHANGE_TITLE), FrameKind.SCENE)
            for cut_ms in kept_cut_times_ms
        ),
    ]
    return MergedFrames(
        frames=sorted(frames, key=lambda frame: frame.moment.at_ms),
        dialogue_count=len(dialogue_moments),
        sound_count=len(sound_moments),
        scene_count=len(kept_cut_times_ms),
    )


def is_near_any(at_ms: int, frame_times_ms: list[int]) -> bool:
    return any(abs(at_ms - frame_ms) < MIN_MOMENT_GAP_MS for frame_ms in frame_times_ms)


def _drop_crowded_cuts(candidates: FrameCandidates, frame_times_ms: list[int]) -> list[int]:
    last_capturable_ms = candidates.duration_ms - FRAME_END_MARGIN_MS
    kept_cut_times_ms: list[int] = []
    for cut_ms in sorted(candidates.cut_times_ms):
        is_after_last_frame = cut_ms > last_capturable_ms
        is_near_previous_cut = bool(kept_cut_times_ms) and (
            cut_ms - kept_cut_times_ms[-1] < MIN_MOMENT_GAP_MS
        )
        if is_after_last_frame or is_near_any(cut_ms, frame_times_ms) or is_near_previous_cut:
            continue
        kept_cut_times_ms.append(cut_ms)
    return kept_cut_times_ms
