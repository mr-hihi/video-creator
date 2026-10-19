from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.films.errors import InvalidFilmRequestError
from app.modules.films.field_rules import to_bounded_text, to_optional_text

SCENE_PROMPT_LIMIT = 4000
NARRATION_LIMIT = 1000
MIN_KEPT_CLIP_MS = 1000
MIN_SCENE_CLIP_DURATION_S = 4
MAX_SCENE_CLIP_DURATION_S = 30
FIRST_POSITION = 0
IMAGE_PROMPT_MESSAGE = f"Image prompt must be 1-{SCENE_PROMPT_LIMIT} characters"
VIDEO_PROMPT_MESSAGE = f"Video prompt must be 1-{SCENE_PROMPT_LIMIT} characters"
NARRATION_MESSAGE = f"Narration must be at most {NARRATION_LIMIT} characters"
SCENE_CLIP_DURATION_MESSAGE = (
    f"Clip length must be {MIN_SCENE_CLIP_DURATION_S}-{MAX_SCENE_CLIP_DURATION_S} seconds"
)
POSITION_MESSAGE = "Position must be between 0 and {last}"
TRIM_MESSAGE = "Trim must keep at least 1 s inside the clip"
CHARACTER_NOT_LINKED_MESSAGE = "Character {character_id} is not in this project"


@dataclass(frozen=True)
class TrimRange:
    start_ms: int
    end_ms: int | None
    clip_duration_ms: int


def to_valid_image_prompt(image_prompt: str | None) -> str:
    return to_bounded_text(image_prompt or "", SCENE_PROMPT_LIMIT, IMAGE_PROMPT_MESSAGE)


def to_valid_video_prompt(video_prompt: str | None) -> str:
    return to_bounded_text(video_prompt or "", SCENE_PROMPT_LIMIT, VIDEO_PROMPT_MESSAGE)


def to_valid_narration(narrator_text: str | None) -> str | None:
    return to_optional_text(narrator_text, NARRATION_LIMIT, NARRATION_MESSAGE)


def to_valid_scene_clip_duration(clip_duration_s: int | None) -> int:
    if clip_duration_s is None or not (
        MIN_SCENE_CLIP_DURATION_S <= clip_duration_s <= MAX_SCENE_CLIP_DURATION_S
    ):
        raise InvalidFilmRequestError(SCENE_CLIP_DURATION_MESSAGE)
    return clip_duration_s


def to_valid_character_ids(
    character_ids: Sequence[str], linked_character_ids: Sequence[str]
) -> list[str]:
    unknown_ids = [cid for cid in character_ids if cid not in linked_character_ids]
    if unknown_ids:
        raise InvalidFilmRequestError(
            CHARACTER_NOT_LINKED_MESSAGE.format(character_id=unknown_ids[0])
        )
    return list(dict.fromkeys(character_ids))


def to_insert_position(after_position: int | None, scene_count: int) -> int:
    if after_position is None:
        return scene_count
    return min(max(after_position + 1, FIRST_POSITION), scene_count)


def to_valid_position(position: int, scene_count: int) -> int:
    last_position = scene_count - 1
    if not FIRST_POSITION <= position <= last_position:
        raise InvalidFilmRequestError(POSITION_MESSAGE.format(last=last_position))
    return position


def ensure_valid_trim(trim: TrimRange) -> None:
    end_ms = trim.clip_duration_ms if trim.end_ms is None else trim.end_ms
    is_inside_clip = 0 <= trim.start_ms < end_ms <= trim.clip_duration_ms
    if not is_inside_clip or end_ms - trim.start_ms < MIN_KEPT_CLIP_MS:
        raise InvalidFilmRequestError(TRIM_MESSAGE)
