from dataclasses import dataclass

MIN_MOMENT_GAP_MS = 3000
FRAME_END_MARGIN_MS = 500


@dataclass(frozen=True)
class KeyMoment:
    at_ms: int
    title: str


@dataclass(frozen=True)
class VideoOutline:
    title: str
    summary: str
    moments: list[KeyMoment]


def normalize_moments(
    moments: list[KeyMoment], duration_ms: int, max_moments: int
) -> list[KeyMoment]:
    last_capturable_ms = max(duration_ms - FRAME_END_MARGIN_MS, 0)
    candidates = sorted(
        (
            KeyMoment(
                at_ms=min(max(moment.at_ms, 0), last_capturable_ms), title=moment.title.strip()
            )
            for moment in moments
            if moment.title.strip()
        ),
        key=lambda moment: moment.at_ms,
    )
    kept_moments: list[KeyMoment] = []
    for candidate in candidates:
        if kept_moments and candidate.at_ms - kept_moments[-1].at_ms < MIN_MOMENT_GAP_MS:
            continue
        kept_moments.append(candidate)
    return kept_moments[:max_moments]
