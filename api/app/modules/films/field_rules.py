from collections.abc import Callable, Mapping
from typing import Any

from app.modules.films.errors import InvalidFilmRequestError

CLEARED_TEXT = ""

type FieldRules = Mapping[str, Callable[[Any], Any]]


def to_bounded_text(value: str, limit: int, message: str) -> str:
    text = value.strip()
    if not 1 <= len(text) <= limit:
        raise InvalidFilmRequestError(message)
    return text


def to_optional_text(value: str | None, limit: int, message: str) -> str | None:
    text = (value or CLEARED_TEXT).strip()
    if len(text) > limit:
        raise InvalidFilmRequestError(message)
    return text or None


def keep_value(value: Any) -> Any:
    return value


def to_valid_values(source: object, rules: FieldRules) -> dict[str, Any]:
    return {field: rule(getattr(source, field)) for field, rule in rules.items()}


def to_valid_changes(changes: object, rules: FieldRules) -> dict[str, Any]:
    return {
        field: rule(value)
        for field, rule in rules.items()
        if (value := getattr(changes, field)) is not None
    }
