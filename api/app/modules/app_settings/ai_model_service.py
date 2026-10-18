from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.modules.app_settings.repository import AiModelSettingsSave, AppSettingRepository
from app.modules.app_settings.service import AppSettingService
from app.modules.app_settings.setting_rules import to_stored_ai_model_setting_values
from app.modules.providers.provider_rules import validate_routes
from app.modules.providers.service import ProviderSettingService, ProviderSettingsView


@dataclass(frozen=True)
class AiModelSettingsUpdate:
    setting_values: Mapping[str, Any]
    provider_ids_by_route: Mapping[str, str]
    model_ids_by_provider: Mapping[str, Mapping[str, str]]


@dataclass(frozen=True)
class AiModelSettingsView:
    settings: dict[str, Any]
    providers: ProviderSettingsView


@dataclass(frozen=True)
class AiModelSettingTools:
    repository: AppSettingRepository
    setting_service: AppSettingService
    provider_service: ProviderSettingService


class AiModelSettingService:
    def __init__(self, tools: AiModelSettingTools):
        self._tools = tools

    def update_ai_model_settings(self, update: AiModelSettingsUpdate) -> AiModelSettingsView:
        self._tools.repository.save_ai_model_settings(self._to_settings_save(update))
        return AiModelSettingsView(
            settings=self._tools.setting_service.get_settings(),
            providers=self._tools.provider_service.get_settings_view(),
        )

    def _to_settings_save(self, update: AiModelSettingsUpdate) -> AiModelSettingsSave:
        setting_values = to_stored_ai_model_setting_values(update.setting_values)
        validate_routes(update.provider_ids_by_route)
        return AiModelSettingsSave(
            setting_values=setting_values,
            provider_ids_by_route=update.provider_ids_by_route,
            models_by_provider_id=self._tools.provider_service.to_stored_models(
                update.model_ids_by_provider
            ),
        )
