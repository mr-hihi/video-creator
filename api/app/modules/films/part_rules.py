from app.modules.films.errors import InvalidFilmRequestError
from app.modules.films.field_rules import to_bounded_text

PART_TITLE_LIMIT = 150
PART_PLAN_LIMIT = 5000
RECAP_LIMIT = 5000
MIN_PART_DURATION_S = 8
MAX_PART_DURATION_S = 600
MAX_PART_SCENES = 80
PART_TITLE_MESSAGE = f"Part title must be 1-{PART_TITLE_LIMIT} characters"
PART_PLAN_MESSAGE = f"Part plan must be 1-{PART_PLAN_LIMIT} characters"
PART_DURATION_MESSAGE = (
    f"Part length must be between {MIN_PART_DURATION_S} and {MAX_PART_DURATION_S} seconds"
)
TOO_MANY_PART_SCENES_MESSAGE = f"A part holds at most {MAX_PART_SCENES} scenes"


def to_part_number(position: int) -> int:
    return position + 1


def to_valid_part_title(title: str | None) -> str:
    return to_bounded_text(title or "", PART_TITLE_LIMIT, PART_TITLE_MESSAGE)


def to_valid_part_plan(plan: str | None) -> str:
    return to_bounded_text(plan or "", PART_PLAN_LIMIT, PART_PLAN_MESSAGE)


def to_valid_part_duration(target_duration_s: int | None) -> int:
    if target_duration_s is None or not (
        MIN_PART_DURATION_S <= target_duration_s <= MAX_PART_DURATION_S
    ):
        raise InvalidFilmRequestError(PART_DURATION_MESSAGE)
    return target_duration_s
