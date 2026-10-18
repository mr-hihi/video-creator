import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment

MS_PER_SECOND = 1000


@dataclass(frozen=True)
class SampleFrame:
    at_ms: int
    path: Path


@dataclass(frozen=True)
class WindowPlan:
    segments: Sequence[TranscriptSegment]
    samples: Sequence[SampleFrame]
    duration_ms: int
    max_moments: int
    max_images: int


@dataclass(frozen=True)
class MomentWindow:
    start_ms: int
    end_ms: int
    max_moments: int
    segments: list[TranscriptSegment]
    samples: list[SampleFrame]


def split_into_windows(plan: WindowPlan) -> list[MomentWindow]:
    window_count = max(1, math.ceil(len(plan.samples) / plan.max_images))
    window_ms = plan.max_images * MS_PER_SECOND
    segments_by_window: list[list[TranscriptSegment]] = [[] for _ in range(window_count)]
    samples_by_window: list[list[SampleFrame]] = [[] for _ in range(window_count)]
    for segment in plan.segments:
        segments_by_window[min(segment.start_ms // window_ms, window_count - 1)].append(segment)
    for sample in plan.samples:
        samples_by_window[min(sample.at_ms // window_ms, window_count - 1)].append(sample)
    windows = []
    for index in range(window_count):
        start_ms = index * window_ms
        end_ms = min(start_ms + window_ms, plan.duration_ms)
        windows.append(
            MomentWindow(
                start_ms=start_ms,
                end_ms=end_ms,
                max_moments=to_window_max_moments(plan, end_ms - start_ms),
                segments=segments_by_window[index],
                samples=samples_by_window[index],
            )
        )
    return windows


def to_window_max_moments(plan: WindowPlan, window_duration_ms: int) -> int:
    share = plan.max_moments * window_duration_ms / max(plan.duration_ms, 1)
    return max(1, math.ceil(share))
