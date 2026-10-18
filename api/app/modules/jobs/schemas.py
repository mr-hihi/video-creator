from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.ai_models.schemas import AiUsedResponse
from app.modules.jobs.models import JobOutputKind, JobStatus, JobStep, JobType
from app.modules.jobs.service import JobDetail

CAMEL_CASE_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateYoutubeToMarkdownJobRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    url: str
    language: str = "auto"
    preset_id: str | None = None


class CreateYoutubeFilmAnalysisJobRequest(CreateYoutubeToMarkdownJobRequest):
    max_frames: int | None = None


class CreateFilmAnalysisRerunJobRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    preset_id: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: str
    type: JobType
    status: JobStatus
    step: JobStep | None
    source_filename: str
    options: dict[str, Any]
    ai_used: AiUsedResponse
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobOutputsResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    video_notes: str | None
    character_image_prompts: str | None
    character_voice_prompts: str | None
    scene_prompts: str | None

    @classmethod
    def from_outputs(cls, outputs: dict[JobOutputKind, str]) -> "JobOutputsResponse":
        return cls(
            video_notes=outputs.get(JobOutputKind.VIDEO_NOTES),
            character_image_prompts=outputs.get(JobOutputKind.CHARACTER_IMAGE_PROMPTS),
            character_voice_prompts=outputs.get(JobOutputKind.CHARACTER_VOICE_PROMPTS),
            scene_prompts=outputs.get(JobOutputKind.SCENE_PROMPTS),
        )


class JobDetailResponse(JobResponse):
    markdown: str | None
    outputs: JobOutputsResponse | None

    @classmethod
    def from_detail(cls, detail: JobDetail) -> "JobDetailResponse":
        job_fields = JobResponse.model_validate(detail.job).model_dump()
        outputs = (
            None if detail.outputs is None else JobOutputsResponse.from_outputs(detail.outputs)
        )
        return cls(**job_fields, markdown=detail.markdown, outputs=outputs)
