from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from typing import Any

from app.modules.ai_models.ai_calls import AiStepGroup, InputMode
from app.modules.ai_models.model_choices import (
    DEFAULT_AI_MODEL,
    to_model_choice,
    to_model_value,
    to_step_model_choices,
    to_step_models_value,
)
from app.modules.app_settings.errors import InvalidSettingError
from app.modules.providers.provider_catalog import ROUTE_CHOICES, MediaFeature, RouteName


class ScriptLanguage(StrEnum):
    FOLLOW_TARGET_COUNTRY = "follow_target_country"
    VIETNAMESE = "vi"
    JAPANESE = "ja"
    KOREAN = "ko"
    CHINESE = "zh"
    ENGLISH = "en"
    FRENCH = "fr"
    THAI = "th"
    HINDI = "hi"
    INDONESIAN = "id"


SCRIPT_LANGUAGE_KEY = "scriptLanguage"
AI_MODEL_KEY = "aiModel"
AI_STEP_MODELS_KEY = "aiStepModels"
INPUT_MODE_KEY = "inputMode"
FILM_CLONE_INPUT_MODE_KEY = "filmCloneInputMode"
FILM_CLONE_IMAGE_PROVIDER_KEY = "filmCloneImageProvider"
FILM_STUDIO_IMAGE_PROVIDER_KEY = "filmStudioImageProvider"
FILM_STUDIO_CLIP_PROVIDER_KEY = "filmStudioClipProvider"
DEFAULT_VALUES_BY_KEY: dict[str, Any] = {
    SCRIPT_LANGUAGE_KEY: ScriptLanguage.FOLLOW_TARGET_COUNTRY.value,
    AI_MODEL_KEY: to_model_value(DEFAULT_AI_MODEL),
    AI_STEP_MODELS_KEY: {group.value: None for group in AiStepGroup},
    INPUT_MODE_KEY: InputMode.SUBTITLES.value,
    FILM_CLONE_INPUT_MODE_KEY: InputMode.SUBTITLES.value,
    FILM_CLONE_IMAGE_PROVIDER_KEY: None,
    FILM_STUDIO_IMAGE_PROVIDER_KEY: None,
    FILM_STUDIO_CLIP_PROVIDER_KEY: None,
}
NULLABLE_KEYS = frozenset(
    {FILM_CLONE_IMAGE_PROVIDER_KEY, FILM_STUDIO_IMAGE_PROVIDER_KEY, FILM_STUDIO_CLIP_PROVIDER_KEY}
)
IMAGE_PROVIDER_KEY_BY_FEATURE: dict[MediaFeature, str] = {
    MediaFeature.FILM_CLONE: FILM_CLONE_IMAGE_PROVIDER_KEY,
    MediaFeature.FILM_STUDIO: FILM_STUDIO_IMAGE_PROVIDER_KEY,
}
AI_MODEL_SETTING_KEYS = (AI_MODEL_KEY, AI_STEP_MODELS_KEY, INPUT_MODE_KEY)


def to_stored_member(value: Any, members: Iterable[StrEnum]) -> str | None:
    if isinstance(value, str) and value in {member.value for member in members}:
        return value
    return None


def to_stored_ai_model(value: Any) -> dict[str, str] | None:
    choice = to_model_choice(value)
    return None if choice is None else to_model_value(choice)


def to_stored_ai_step_models(value: Any) -> dict[str, dict[str, str] | None] | None:
    choices_by_group = to_step_model_choices(value)
    return None if choices_by_group is None else to_step_models_value(choices_by_group)


def to_stored_image_provider(value: Any) -> str | None:
    return to_stored_member(value, ROUTE_CHOICES[RouteName.IMAGE])


def to_stored_clip_provider(value: Any) -> str | None:
    return to_stored_member(value, ROUTE_CHOICES[RouteName.VIDEO])


STORED_VALUE_RULES_BY_KEY: dict[str, Callable[[Any], Any]] = {
    SCRIPT_LANGUAGE_KEY: lambda value: to_stored_member(value, ScriptLanguage),
    AI_MODEL_KEY: to_stored_ai_model,
    AI_STEP_MODELS_KEY: to_stored_ai_step_models,
    INPUT_MODE_KEY: lambda value: to_stored_member(value, InputMode),
    FILM_CLONE_INPUT_MODE_KEY: lambda value: to_stored_member(value, InputMode),
    FILM_CLONE_IMAGE_PROVIDER_KEY: to_stored_image_provider,
    FILM_STUDIO_IMAGE_PROVIDER_KEY: to_stored_image_provider,
    FILM_STUDIO_CLIP_PROVIDER_KEY: to_stored_clip_provider,
}
AI_MODEL_RULES_BY_KEY = {key: STORED_VALUE_RULES_BY_KEY[key] for key in AI_MODEL_SETTING_KEYS}


def to_stored_setting_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return _to_stored_values(values, STORED_VALUE_RULES_BY_KEY)


def to_stored_ai_model_setting_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return _to_stored_values(values, AI_MODEL_RULES_BY_KEY)


def to_setting_value(key: str, stored_value: Any) -> Any:
    if stored_value is None:
        return DEFAULT_VALUES_BY_KEY[key]
    readable_value = STORED_VALUE_RULES_BY_KEY[key](stored_value)
    return DEFAULT_VALUES_BY_KEY[key] if readable_value is None else readable_value


def _to_stored_values(
    values: Mapping[str, Any], rules_by_key: Mapping[str, Callable[[Any], Any]]
) -> dict[str, Any]:
    return {key: _to_stored_value(key, value, rules_by_key) for key, value in values.items()}


def _to_stored_value(key: str, value: Any, rules_by_key: Mapping[str, Callable[[Any], Any]]) -> Any:
    to_stored_value = rules_by_key.get(key)
    if to_stored_value is None:
        raise InvalidSettingError(f"Unknown setting '{key}'")
    if value is None and key in NULLABLE_KEYS:
        return None
    stored_value = to_stored_value(value)
    if stored_value is None:
        raise InvalidSettingError(f"Invalid value for '{key}'")
    return stored_value
