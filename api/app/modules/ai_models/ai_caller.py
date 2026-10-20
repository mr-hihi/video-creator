from collections.abc import Mapping
from typing import Any, Protocol

from app.modules.ai_models.ai_calls import AiAsk, AiLimits, AiModelChoice, AiStepGroup
from app.modules.ai_models.step_models import AiStepModels
from app.modules.providers.provider_catalog import ProviderId


class AiClient(Protocol):
    def ask_for_json(self, model: str, ask: AiAsk, limits: AiLimits) -> dict[str, Any]: ...

    def ask_for_text(self, model: str, ask: AiAsk, limits: AiLimits) -> str: ...


class AiCaller:
    def __init__(
        self, clients_by_provider: Mapping[ProviderId, AiClient], step_models: AiStepModels
    ):
        self._clients_by_provider = clients_by_provider
        self._step_models = step_models

    def find_model(self, group: AiStepGroup) -> AiModelChoice:
        return self._step_models.find_model(group)

    def find_google_model(self, group: AiStepGroup) -> AiModelChoice:
        return self._step_models.find_google_model(group)

    def ask_for_json(self, choice: AiModelChoice, ask: AiAsk, limits: AiLimits) -> dict[str, Any]:
        return self._clients_by_provider[choice.provider].ask_for_json(choice.model, ask, limits)

    def ask_for_text(self, choice: AiModelChoice, ask: AiAsk, limits: AiLimits) -> str:
        return self._clients_by_provider[choice.provider].ask_for_text(choice.model, ask, limits)
