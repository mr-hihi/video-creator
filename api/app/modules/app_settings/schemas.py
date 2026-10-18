from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.app_settings.ai_model_service import AiModelSettingsUpdate, AiModelSettingsView
from app.modules.providers.schemas import ProviderSettingsResponse


class UpdateAiModelSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    routes: dict[str, str] | None = None
    models: dict[str, dict[str, str]] | None = None

    def to_update(self) -> AiModelSettingsUpdate:
        return AiModelSettingsUpdate(
            setting_values=dict(self.model_extra or {}),
            provider_ids_by_route=self.routes or {},
            model_ids_by_provider=self.models or {},
        )


class AiModelSettingsResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    settings: dict[str, Any]
    providers: ProviderSettingsResponse

    @classmethod
    def from_view(cls, view: AiModelSettingsView) -> "AiModelSettingsResponse":
        return cls(
            settings=view.settings,
            providers=ProviderSettingsResponse.from_view(view.providers),
        )
