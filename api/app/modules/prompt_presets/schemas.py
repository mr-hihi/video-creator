from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.prompt_presets.models import PresetChange, PromptPresetVersion
from app.modules.prompt_presets.prompt_texts import PresetPrompts
from app.modules.prompt_presets.service import PromptPresetDetail

CAMEL_CASE_CONFIG = ConfigDict(
    from_attributes=True, alias_generator=to_camel, populate_by_name=True
)


class PromptsBody(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    video_to_markdown: str
    speakers_and_sounds: str
    character_image: str
    character_voice: str
    scene: str
    film_outline: str
    film_script: str
    story_bible: str
    clone_assets: str
    clone_shots: str
    clone_localization: str
    clone_script: str

    def to_preset_prompts(self) -> PresetPrompts:
        return PresetPrompts(**self.model_dump())


class CreatePromptPresetRequest(BaseModel):
    name: str


class SavePromptPresetRequest(BaseModel):
    name: str
    prompts: PromptsBody


class PromptPresetResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    id: str
    name: str
    is_system: bool
    is_default: bool
    current_version: int
    created_at: datetime
    updated_at: datetime


class PromptPresetDetailResponse(PromptPresetResponse):
    prompts: PromptsBody

    @classmethod
    def from_detail(cls, detail: PromptPresetDetail) -> "PromptPresetDetailResponse":
        preset_fields = PromptPresetResponse.model_validate(detail.preset).model_dump()
        return cls(**preset_fields, prompts=PromptsBody.model_validate(detail.prompts))


class PromptPresetVersionResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    version: int
    change: PresetChange
    change_source: str | None
    created_at: datetime


class PromptPresetVersionDetailResponse(PromptPresetVersionResponse):
    prompts: PromptsBody

    @classmethod
    def from_version(cls, version: PromptPresetVersion) -> "PromptPresetVersionDetailResponse":
        version_fields = PromptPresetVersionResponse.model_validate(version).model_dump()
        return cls(
            **version_fields, prompts=PromptsBody.model_validate(version.to_preset_prompts())
        )


class PromptDefaultsResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    prompts: PromptsBody
    app_added_parts: PromptsBody
