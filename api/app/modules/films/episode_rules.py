from app.modules.films.errors import InvalidFilmRequestError
from app.modules.films.field_rules import to_bounded_text, to_optional_text
from app.modules.films.models import EpisodeSource

IDEA_LIMIT = 5000
TITLE_LIMIT = 150
MIN_TARGET_DURATION_S = 8
DEFAULT_TITLE_TEMPLATE = "Episode {number}"
IDEA_MESSAGE = f"Idea must be 1-{IDEA_LIMIT} characters"
TITLE_MESSAGE = f"Title must be 1-{TITLE_LIMIT} characters"
TARGET_DURATION_MESSAGE = f"Target duration must be at least {MIN_TARGET_DURATION_S} seconds"


def build_default_title(number: int) -> str:
    return DEFAULT_TITLE_TEMPLATE.format(number=number)


def to_valid_idea(idea: str | None, source: EpisodeSource) -> str | None:
    if source is EpisodeSource.IDEA:
        return to_bounded_text(idea or "", IDEA_LIMIT, IDEA_MESSAGE)
    return to_optional_text(idea, IDEA_LIMIT, IDEA_MESSAGE)


def to_valid_title(title: str | None) -> str:
    return to_bounded_text(title or "", TITLE_LIMIT, TITLE_MESSAGE)


def to_valid_target_duration(target_duration_s: int | None) -> int:
    if target_duration_s is None or target_duration_s < MIN_TARGET_DURATION_S:
        raise InvalidFilmRequestError(TARGET_DURATION_MESSAGE)
    return target_duration_s
