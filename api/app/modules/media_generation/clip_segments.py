from collections.abc import Sequence
from dataclasses import dataclass

CLIP_SEGMENTS_DIR_NAME = "clip-segments"
JOIN_CUT_HEAD_S = 1
SEGMENT_HEADER = "Part {number} of {count}. Show {start_s}-{end_s}s of this shot."
CONTINUE_LINE = "Continue from the start image."


@dataclass(frozen=True)
class ClipPlan:
    clip_length_s: int
    segment_lengths_s: tuple[int, ...]

    @property
    def segment_count(self) -> int:
        return len(self.segment_lengths_s)

    @property
    def is_cut_or_joined(self) -> bool:
        return self.segment_count > 1 or self.segment_lengths_s[0] != self.clip_length_s


def plan_clip_segments(clip_length_s: int, model_lengths_s: Sequence[int]) -> ClipPlan:
    lengths_s = sorted(model_lengths_s)
    if not lengths_s or lengths_s[-1] <= JOIN_CUT_HEAD_S:
        return ClipPlan(clip_length_s, (clip_length_s,))
    fitting_lengths_s = [length_s for length_s in lengths_s if length_s >= clip_length_s]
    if fitting_lengths_s:
        return ClipPlan(clip_length_s, (fitting_lengths_s[0],))
    segment_lengths_s = [lengths_s[-1]]
    joined_s = lengths_s[-1]
    while joined_s < clip_length_s:
        next_length_s = next(
            (
                length_s
                for length_s in lengths_s
                if joined_s + length_s - JOIN_CUT_HEAD_S >= clip_length_s
            ),
            lengths_s[-1],
        )
        segment_lengths_s.append(next_length_s)
        joined_s += next_length_s - JOIN_CUT_HEAD_S
    return ClipPlan(clip_length_s, tuple(segment_lengths_s))


def calculate_segment_window(plan: ClipPlan, number: int) -> tuple[int, int]:
    start_s = sum(_to_added_length_s(plan, earlier_number) for earlier_number in range(1, number))
    end_s = min(start_s + _to_added_length_s(plan, number), plan.clip_length_s)
    return start_s, end_s


def build_segment_prompt(plan: ClipPlan, number: int, clip_prompt: str) -> str:
    start_s, end_s = calculate_segment_window(plan, number)
    header = SEGMENT_HEADER.format(
        number=number, count=plan.segment_count, start_s=start_s, end_s=end_s
    )
    if number > 1:
        header = f"{header} {CONTINUE_LINE}"
    return f"{header}\n{clip_prompt}"


def _to_added_length_s(plan: ClipPlan, number: int) -> int:
    length_s = plan.segment_lengths_s[number - 1]
    return length_s if number == 1 else length_s - JOIN_CUT_HEAD_S
