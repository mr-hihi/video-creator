from collections.abc import Collection
from typing import Any

from pydantic import BaseModel

from app.modules.films.field_rules import CLEARED_TEXT


def to_patch_values(body: BaseModel, clearable_fields: Collection[str]) -> dict[str, Any]:
    sent_values = {field: getattr(body, field) for field in body.model_fields_set}
    return {
        field: CLEARED_TEXT if value is None and field in clearable_fields else value
        for field, value in sent_values.items()
    }
