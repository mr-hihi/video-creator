import math
from collections.abc import Mapping
from typing import Any


def to_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def to_entries(reply: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    entries = reply.get(key)
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, Mapping)]


def to_seconds_within(value: Any, seconds_range: tuple[int, int], default_s: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return default_s
    lowest_s, highest_s = seconds_range
    return min(max(round(value), lowest_s), highest_s)
