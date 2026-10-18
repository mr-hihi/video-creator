from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import uuid4

from app.modules.films.builtin_styles import (
    BUILTIN_STYLE_RANKS_BY_ID,
    BUILTIN_STYLES,
    DEFAULT_LIGHTING,
    builtin_style_to_row,
)
from app.modules.films.errors import (
    FilmConflictError,
    InvalidFilmRequestError,
    StyleNotFoundError,
)
from app.modules.films.field_rules import (
    to_bounded_text,
    to_optional_text,
    to_valid_changes,
    to_valid_values,
)
from app.modules.films.models import Style
from app.modules.films.repository import FilmRepository

STYLE_NAME_LIMIT = 50
STYLE_INSTRUCTION_LIMIT = 2000
NEGATIVE_PROMPT_LIMIT = 1000
SCENE_PREFIX_LIMIT = 500
LIGHTING_LIMIT = 200
STYLE_NAME_MESSAGE = f"Style name must be 1-{STYLE_NAME_LIMIT} characters"
STYLE_INSTRUCTION_MESSAGE = f"Style instruction must be 1-{STYLE_INSTRUCTION_LIMIT} characters"
NEGATIVE_PROMPT_MESSAGE = f"Negative prompt must be at most {NEGATIVE_PROMPT_LIMIT} characters"
SCENE_PREFIX_MESSAGE = f"Scene prefix must be at most {SCENE_PREFIX_LIMIT} characters"
LIGHTING_MESSAGE = f"Lighting must be at most {LIGHTING_LIMIT} characters"
DUPLICATE_STYLE_MESSAGE = "A style named '{name}' already exists"
BUILTIN_STYLE_MESSAGE = "Built-in styles cannot be changed"
STYLE_IN_USE_MESSAGE = (
    "Style '{name}' is used by {project_count} project(s) and {character_count} character(s)"
)
UNKNOWN_STYLE_MESSAGE = "Style {style_id} not found"
UNRANKED_BUILTIN_RANK = len(BUILTIN_STYLES)


def to_lighting(value: str | None) -> str:
    return to_optional_text(value, LIGHTING_LIMIT, LIGHTING_MESSAGE) or DEFAULT_LIGHTING


STYLE_TEXT_RULES = {
    "style_instruction": partial(
        to_bounded_text, limit=STYLE_INSTRUCTION_LIMIT, message=STYLE_INSTRUCTION_MESSAGE
    ),
    "negative_prompt": partial(
        to_optional_text, limit=NEGATIVE_PROMPT_LIMIT, message=NEGATIVE_PROMPT_MESSAGE
    ),
    "scene_prefix": partial(
        to_optional_text, limit=SCENE_PREFIX_LIMIT, message=SCENE_PREFIX_MESSAGE
    ),
    "lighting": to_lighting,
}


@dataclass(frozen=True)
class StyleDraft:
    name: str
    style_instruction: str
    negative_prompt: str | None = None
    scene_prefix: str | None = None
    lighting: str | None = None


@dataclass(frozen=True)
class StyleChanges:
    name: str | None = None
    style_instruction: str | None = None
    negative_prompt: str | None = None
    scene_prefix: str | None = None
    lighting: str | None = None


class FilmStyleService:
    def __init__(self, repository: FilmRepository):
        self._repository = repository

    def ensure_builtin_styles(self) -> None:
        self._repository.add_missing_styles(
            [builtin_style_to_row(builtin_style) for builtin_style in BUILTIN_STYLES]
        )

    def list_styles(self) -> list[Style]:
        styles = self._repository.find_styles()
        builtin_styles = sorted((style for style in styles if style.is_builtin), key=_rank_builtin)
        return [*builtin_styles, *(style for style in styles if not style.is_builtin)]

    def create_style(self, draft: StyleDraft) -> Style:
        style_id = str(uuid4())
        name = self._to_free_name(draft.name, style_id)
        values = to_valid_values(draft, STYLE_TEXT_RULES)
        return self._repository.add_style(Style(id=style_id, name=name, is_builtin=False, **values))

    def update_style(self, style_id: str, changes: StyleChanges) -> Style:
        style = self._get_custom_style(style_id)
        values: dict[str, Any] = to_valid_changes(changes, STYLE_TEXT_RULES)
        if changes.name is not None:
            values["name"] = self._to_free_name(changes.name, style.id)
        if values:
            self._repository.update_style(style.id, values)
        return self._get_style(style.id)

    def delete_style(self, style_id: str) -> None:
        style = self._get_custom_style(style_id)
        project_count, character_count = self._repository.count_style_usage(style.id)
        if project_count + character_count > 0:
            raise FilmConflictError(
                STYLE_IN_USE_MESSAGE.format(
                    name=style.name, project_count=project_count, character_count=character_count
                )
            )
        self._repository.delete_style(style.id)

    def _get_style(self, style_id: str) -> Style:
        style = self._repository.find_style(style_id)
        if style is None:
            raise StyleNotFoundError(style_id)
        return style

    def _get_custom_style(self, style_id: str) -> Style:
        style = self._get_style(style_id)
        if style.is_builtin:
            raise FilmConflictError(BUILTIN_STYLE_MESSAGE)
        return style

    def _to_free_name(self, requested_name: str, own_style_id: str) -> str:
        name = to_bounded_text(requested_name, STYLE_NAME_LIMIT, STYLE_NAME_MESSAGE)
        existing = self._repository.find_style_by_name(name)
        if existing is not None and existing.id != own_style_id:
            raise FilmConflictError(DUPLICATE_STYLE_MESSAGE.format(name=name))
        return name


def get_known_style(repository: FilmRepository, style_id: str) -> Style:
    style = repository.find_style(style_id)
    if style is None:
        raise InvalidFilmRequestError(UNKNOWN_STYLE_MESSAGE.format(style_id=style_id))
    return style


def _rank_builtin(style: Style) -> int:
    return BUILTIN_STYLE_RANKS_BY_ID.get(style.id, UNRANKED_BUILTIN_RANK)
