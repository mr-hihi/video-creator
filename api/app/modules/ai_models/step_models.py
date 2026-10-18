from collections.abc import Callable, Iterable

from app.modules.ai_models.ai_calls import AiModelChoice, AiProviderNotSetUpError, AiStepGroup
from app.modules.ai_models.model_choices import to_provider_name
from app.modules.app_settings.service import AppSettingService
from app.modules.providers.provider_catalog import ProviderId


class AiStepModels:
    def __init__(
        self,
        settings_service: AppSettingService,
        is_provider_set_up: Callable[[ProviderId], bool],
    ):
        self._settings_service = settings_service
        self._is_provider_set_up = is_provider_set_up

    def find_model(self, group: AiStepGroup) -> AiModelChoice:
        step_model = self._settings_service.get_ai_step_models()[group]
        return step_model or self._settings_service.get_ai_model()

    def ensure_set_up(self, groups: Iterable[AiStepGroup]) -> None:
        for group in groups:
            provider = self.find_model(group).provider
            if not self._is_provider_set_up(provider):
                raise AiProviderNotSetUpError(to_provider_name(provider))
