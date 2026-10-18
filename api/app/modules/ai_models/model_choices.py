from collections.abc import Mapping
from typing import Any

from app.modules.ai_models.ai_calls import AiModelChoice, AiStepGroup
from app.modules.providers.model_catalog import CLAUDE_CLI_DEFAULT_MODEL, find_catalog_models
from app.modules.providers.provider_catalog import PROVIDER_SPECS_BY_ID, MediaKind, ProviderId

PROVIDER_KEY = "provider"
MODEL_KEY = "model"
AI_NAMES_BY_PROVIDER: dict[ProviderId, str] = {
    ProviderId.CLAUDE_CLI: "claude",
    ProviderId.GOOGLE: "gemini",
    ProviderId.OPENAI: "openai",
}
DEFAULT_AI_MODEL = AiModelChoice(ProviderId.CLAUDE_CLI, CLAUDE_CLI_DEFAULT_MODEL)


def to_model_choice(value: Any) -> AiModelChoice | None:
    if not isinstance(value, Mapping) or set(value) != {PROVIDER_KEY, MODEL_KEY}:
        return None
    provider_id, model_id = value[PROVIDER_KEY], value[MODEL_KEY]
    if not isinstance(provider_id, str) or provider_id not in AI_NAMES_BY_PROVIDER:
        return None
    catalog_ids = {
        model.id for model in find_catalog_models(ProviderId(provider_id), MediaKind.ANALYSIS)
    }
    if not isinstance(model_id, str) or model_id not in catalog_ids:
        return None
    return AiModelChoice(ProviderId(provider_id), model_id)


def to_step_model_choices(value: Any) -> dict[AiStepGroup, AiModelChoice | None] | None:
    if not isinstance(value, Mapping) or not set(value) <= set(AiStepGroup):
        return None
    choices_by_group: dict[AiStepGroup, AiModelChoice | None] = {}
    for group in AiStepGroup:
        stored_choice = value.get(group.value)
        choice = None if stored_choice is None else to_model_choice(stored_choice)
        if stored_choice is not None and choice is None:
            return None
        choices_by_group[group] = choice
    return choices_by_group


def to_model_value(choice: AiModelChoice) -> dict[str, str]:
    return {PROVIDER_KEY: choice.provider.value, MODEL_KEY: choice.model}


def to_step_models_value(
    choices_by_group: Mapping[AiStepGroup, AiModelChoice | None],
) -> dict[str, dict[str, str] | None]:
    return {
        group.value: None if choice is None else to_model_value(choice)
        for group, choice in choices_by_group.items()
    }


def to_model_label(choice: AiModelChoice) -> str:
    models = find_catalog_models(choice.provider, MediaKind.ANALYSIS)
    return next((model.label for model in models if model.id == choice.model), choice.model)


def to_ai_name(provider: ProviderId) -> str:
    return AI_NAMES_BY_PROVIDER[provider]


def to_provider_name(provider: ProviderId) -> str:
    return PROVIDER_SPECS_BY_ID[provider].name
