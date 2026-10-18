from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.modules.ai_models.model_choices import to_model_label
from app.modules.ai_models.schemas import AiUsedResponse
from app.modules.film_clones.clone_activity import AiActivity
from app.modules.film_clones.models import (
    AssetKind,
    CameraAngle,
    CloneAspect,
    CloneImageStatus,
    CloneStatus,
    CloneStep,
    FrameKind,
    ShotSize,
)
from app.modules.film_clones.service import CloneDetail, CloneSummary
from app.modules.jobs.models import JobStep, JobType
from app.modules.jobs.schemas import JobResponse
from app.modules.media_generation.schemas import GenerationRequestResponse
from app.modules.providers.provider_catalog import ProviderId

CAMEL_CASE_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)
ORM_CAMEL_CASE_CONFIG = ConfigDict(
    from_attributes=True, alias_generator=to_camel, populate_by_name=True
)
SOURCE_KIND_BY_JOB_TYPE = {JobType.FILM_CLONE: "upload", JobType.YOUTUBE_FILM_CLONE: "youtube"}


class CreateYoutubeFilmCloneRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    url: str
    language: str = "auto"
    preset_id: str | None = None
    max_frames: int | None = None
    should_run_automatically: bool = False
    target_country: str | None = None
    target_setting: str | None = None
    change_appearance: bool = False
    change_costume: bool = False
    change_setting: bool = False


class LocalizeRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    target_country: str | None = None
    target_setting: str | None = None
    change_appearance: bool = False
    change_costume: bool = False
    change_setting: bool = False


class AssetPatchRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str | None = None
    kind: AssetKind | None = None
    description: str | None = None
    culture: str | None = None
    period: str | None = None
    changed: bool | None = None
    localized_name: str | None = None
    localized_description: str | None = None


class ScenePatchRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    description: str | None = None
    dialogue: str | None = None
    image_prompt: str | None = None


class FilmCloneResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    job_id: str
    status: CloneStatus
    step: CloneStep
    error_message: str | None
    target_country: str | None
    target_setting: str | None
    change_appearance: bool
    change_costume: bool
    change_setting: bool
    should_run_automatically: bool
    script_language: str | None
    aspect: CloneAspect | None
    script_title: str | None
    logline: str | None
    preset: dict[str, Any]
    prompts: dict[str, Any]
    ai_used: AiUsedResponse
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    source_filename: str
    source_kind: str
    job_step: JobStep | None
    has_open_requests: bool

    @classmethod
    def from_summary(cls, summary: CloneSummary) -> "FilmCloneResponse":
        clone_fields = {
            name: getattr(summary.clone, name)
            for name in cls.model_fields
            if hasattr(summary.clone, name)
        }
        job = summary.job
        return cls(
            **clone_fields,
            source_filename=job.source_filename if job else "",
            source_kind=SOURCE_KIND_BY_JOB_TYPE.get(job.type, "upload") if job else "upload",
            job_step=job.step if job else None,
            has_open_requests=summary.has_open_requests,
        )


class CloneAssetResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    clone_id: str
    position: int
    kind: AssetKind
    name: str
    description: str
    culture: str
    period: str
    frames: list[str]
    reference_frame: str | None
    changed: bool
    localized_name: str | None
    localized_description: str | None
    localization_note: str | None
    reference_status: CloneImageStatus
    reference_path: str | None
    reference_error: str | None


class CloneShotResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    position: int
    at_ms: int
    frame: str
    frame_kind: FrameKind
    shot_size: ShotSize | None
    camera_angle: CameraAngle | None
    emotion: str | None
    action: str | None
    asset_ids: list[str]


class CloneSceneResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    clone_id: str
    shot_id: str
    position: int
    description: str
    dialogue: str | None
    image_prompt: str
    asset_ids: list[str]
    image_status: CloneImageStatus
    image_path: str | None
    image_error: str | None


class AiActivityResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    provider: ProviderId
    model: str
    label: str
    started_at: datetime
    last_output_at: datetime | None

    @classmethod
    def from_activity(cls, activity: AiActivity) -> "AiActivityResponse":
        return cls(
            provider=activity.choice.provider,
            model=activity.choice.model,
            label=to_model_label(activity.choice),
            started_at=activity.started_at,
            last_output_at=activity.last_output_at,
        )


class FilmCloneDetailResponse(FilmCloneResponse):
    job: JobResponse | None
    video_notes: str | None
    assets: list[CloneAssetResponse]
    shots: list[CloneShotResponse]
    scenes: list[CloneSceneResponse]
    generation_requests: list[GenerationRequestResponse]
    ai_activity: AiActivityResponse | None

    @classmethod
    def from_detail(cls, detail: CloneDetail) -> "FilmCloneDetailResponse":
        summary_fields = FilmCloneResponse.from_summary(detail.summary).model_dump()
        job = detail.summary.job
        return cls(
            **summary_fields,
            job=JobResponse.model_validate(job) if job else None,
            video_notes=detail.video_notes,
            assets=[CloneAssetResponse.model_validate(asset) for asset in detail.assets],
            shots=[CloneShotResponse.model_validate(shot) for shot in detail.shots],
            scenes=[CloneSceneResponse.model_validate(scene) for scene in detail.scenes],
            generation_requests=[
                GenerationRequestResponse.model_validate(request)
                for request in detail.open_requests
            ],
            ai_activity=(
                AiActivityResponse.from_activity(detail.ai_activity) if detail.ai_activity else None
            ),
        )
