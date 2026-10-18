from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.media_generation.models import GenerationKind, GenerationStatus
from app.modules.providers.provider_catalog import MediaKind


class GenerationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: str
    kind: GenerationKind
    media_kind: MediaKind
    project_id: str | None
    clone_id: str | None
    episode_id: str | None
    scene_id: str | None
    character_id: str | None
    clone_asset_id: str | None
    clone_scene_id: str | None
    provider: str
    status: GenerationStatus
    params: dict[str, Any]
    attempts: int
    next_attempt_at: datetime | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
