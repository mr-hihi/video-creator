from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, BeforeValidator

from app.modules.ai_models.ai_calls import AiModelChoice
from app.modules.ai_models.model_choices import MODEL_KEY, PROVIDER_KEY, to_model_label
from app.modules.providers.provider_catalog import ProviderId

LABEL_KEY = "label"


class AiUsedEntryResponse(BaseModel):
    provider: ProviderId
    model: str
    label: str


def to_labelled_ai_used(
    stored_ai_used: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, dict[str, str]]:
    if stored_ai_used is None:
        return {}
    return {
        step: {
            PROVIDER_KEY: entry[PROVIDER_KEY],
            MODEL_KEY: entry[MODEL_KEY],
            LABEL_KEY: to_model_label(
                AiModelChoice(ProviderId(entry[PROVIDER_KEY]), entry[MODEL_KEY])
            ),
        }
        for step, entry in stored_ai_used.items()
    }


AiUsedResponse = Annotated[dict[str, AiUsedEntryResponse], BeforeValidator(to_labelled_ai_used)]
