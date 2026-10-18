from collections.abc import Mapping
from typing import Any

from app.modules.ai_models.ai_calls import AiModelChoice, AiStepGroup, InputMode
from app.modules.ai_models.model_choices import (
    DEFAULT_AI_MODEL,
    to_model_choice,
    to_step_model_choices,
)
from app.modules.app_settings.repository import AppSettingRepository
from app.modules.app_settings.setting_rules import (
    AI_MODEL_KEY,
    AI_STEP_MODELS_KEY,
    DEFAULT_VALUES_BY_KEY,
    FILM_CLONE_INPUT_MODE_KEY,
    FILM_STUDIO_CLIP_PROVIDER_KEY,
    IMAGE_PROVIDER_KEY_BY_FEATURE,
    INPUT_MODE_KEY,
    SCRIPT_LANGUAGE_KEY,
    ScriptLanguage,
    to_setting_value,
    to_stored_setting_values,
)
from app.modules.providers.provider_catalog import MediaFeature, ProviderId


class AppSettingService:
    def __init__(self, repository: AppSettingRepository):
        self._repository = repository

    def get_settings(self) -> dict[str, Any]:
        stored_values = self._repository.find_values()
        return {key: to_setting_value(key, stored_values.get(key)) for key in DEFAULT_VALUES_BY_KEY}

    def update_settings(self, values: Mapping[str, Any]) -> dict[str, Any]:
        self._repository.save_values(to_stored_setting_values(values))
        return self.get_settings()

    def get_script_language(self) -> ScriptLanguage:
        return ScriptLanguage(self.get_settings()[SCRIPT_LANGUAGE_KEY])

    def get_ai_model(self) -> AiModelChoice:
        return to_model_choice(self.get_settings()[AI_MODEL_KEY]) or DEFAULT_AI_MODEL

    def get_ai_step_models(self) -> dict[AiStepGroup, AiModelChoice | None]:
        return to_step_model_choices(self.get_settings()[AI_STEP_MODELS_KEY]) or {
            group: None for group in AiStepGroup
        }

    def get_input_mode(self) -> InputMode:
        return InputMode(self.get_settings()[INPUT_MODE_KEY])

    def get_film_clone_input_mode(self) -> InputMode:
        return InputMode(self.get_settings()[FILM_CLONE_INPUT_MODE_KEY])

    def get_chosen_image_provider(self, feature: MediaFeature) -> ProviderId | None:
        return self._find_chosen_provider(IMAGE_PROVIDER_KEY_BY_FEATURE[feature])

    def get_chosen_clip_provider(self) -> ProviderId | None:
        return self._find_chosen_provider(FILM_STUDIO_CLIP_PROVIDER_KEY)

    def _find_chosen_provider(self, key: str) -> ProviderId | None:
        provider_id = self.get_settings()[key]
        return None if provider_id is None else ProviderId(provider_id)
