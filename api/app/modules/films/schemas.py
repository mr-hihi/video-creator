from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.modules.ai_models.schemas import AiUsedResponse
from app.modules.films.models import (
    EntityType,
    EpisodeSource,
    EpisodeStatus,
    EpisodeStep,
    FilmLanguage,
    MediaStatus,
    Orientation,
    ProjectStatus,
    ReferenceSource,
    SceneImageSource,
    SubtitleStyle,
)
from app.modules.films.views import (
    CharacterDetail,
    CharacterSummary,
    EpisodeDetail,
    EpisodeSummary,
    ProjectDetail,
    ProjectSummary,
)
from app.modules.media_generation.models import GenerationStatus
from app.modules.media_generation.schemas import GenerationRequestResponse

CAMEL_CASE_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)
ORM_CAMEL_CASE_CONFIG = ConfigDict(
    from_attributes=True, alias_generator=to_camel, populate_by_name=True
)
DEFAULT_CLIP_DURATION_S = 8
DEFAULT_TARGET_DURATION_S = 60


class StopPoints(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    after_script: bool = False
    after_references: bool = False
    after_scene_images: bool = True


class CreateProjectRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str
    description: str | None = None
    language: FilmLanguage
    orientation: Orientation
    style_id: str
    clip_duration_s: int = DEFAULT_CLIP_DURATION_S
    allow_dialogue: bool = True
    allow_narration: bool = True
    narrator_voice_id: str | None = None
    allow_music: bool = False
    character_ids: list[str] = Field(default_factory=list)


class UpdateProjectRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str | None = None
    description: str | None = None
    language: FilmLanguage | None = None
    orientation: Orientation | None = None
    style_id: str | None = None
    clip_duration_s: int | None = None
    allow_dialogue: bool | None = None
    allow_narration: bool | None = None
    narrator_voice_id: str | None = None
    allow_music: bool | None = None


class CreateCharacterRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str
    entity_type: EntityType
    description: str
    image_prompt: str | None = None
    voice_description: str | None = None
    style_id: str


class UpdateCharacterRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str | None = None
    entity_type: EntityType | None = None
    description: str | None = None
    image_prompt: str | None = None
    voice_description: str | None = None
    style_id: str | None = None


class EditPromptRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    prompt: str


class CreateStyleRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str
    style_instruction: str
    negative_prompt: str | None = None
    scene_prefix: str | None = None
    lighting: str | None = None


class UpdateStyleRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str | None = None
    style_instruction: str | None = None
    negative_prompt: str | None = None
    scene_prefix: str | None = None
    lighting: str | None = None


class UpdateVoiceRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    name: str | None = None
    sample_text: str | None = None
    description: str | None = None


class CreateEpisodeRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    source: EpisodeSource
    idea: str | None = None
    source_job_id: str | None = None
    source_clone_id: str | None = None
    target_duration_s: int = DEFAULT_TARGET_DURATION_S
    stop_points: StopPoints = Field(default_factory=StopPoints)
    burn_subtitles: bool = False
    subtitle_style: SubtitleStyle = SubtitleStyle.CLEAN_WHITE
    preset_id: str | None = None


class UpdateEpisodeRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    title: str | None = None
    idea: str | None = None
    target_duration_s: int | None = None
    stop_points: StopPoints | None = None
    burn_subtitles: bool | None = None
    subtitle_style: SubtitleStyle | None = None
    music_prompt: str | None = None
    thumbnail_prompt: str | None = None


class ChooseThumbnailRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    candidate: int


class CreateSceneRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    after_position: int | None = None
    image_prompt: str
    video_prompt: str
    narrator_text: str | None = None
    character_ids: list[str] = Field(default_factory=list)
    clip_duration_s: int | None = None


class UpdateSceneRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    image_prompt: str | None = None
    video_prompt: str | None = None
    narrator_text: str | None = None
    character_ids: list[str] | None = None
    clip_duration_s: int | None = None
    position: int | None = None
    trim_start_ms: int | None = None
    trim_end_ms: int | None = None


class StyleResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    name: str
    is_builtin: bool
    style_instruction: str
    negative_prompt: str | None
    scene_prefix: str | None
    lighting: str


class VoiceResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    name: str
    description: str | None
    sample_path: str
    sample_text: str
    sample_duration_ms: int
    consent_path: str | None
    provider_voices: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CharacterResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    name: str
    entity_type: EntityType
    description: str
    image_prompt: str
    voice_description: str | None
    style_id: str
    style_name: str
    reference_status: MediaStatus
    reference_source: ReferenceSource | None
    reference_path: str | None
    reference_error: str | None
    provider_media: dict[str, Any] | None
    origin_job_id: str | None
    origin_clone_id: str | None
    project_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, summary: CharacterSummary) -> "CharacterResponse":
        return cls.model_validate(
            {
                **_orm_fields(summary.character, cls, {"style_name", "project_count"}),
                "style_name": summary.style_name,
                "project_count": summary.project_count,
            }
        )


class ProjectLinkResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    name: str


class CharacterDetailResponse(CharacterResponse):
    projects: list[ProjectLinkResponse]

    @classmethod
    def from_detail(cls, detail: CharacterDetail) -> "CharacterDetailResponse":
        summary_fields = CharacterResponse.from_summary(detail.summary).model_dump()
        return cls.model_validate(
            {
                **summary_fields,
                "projects": [ProjectLinkResponse.model_validate(link) for link in detail.projects],
            }
        )


class FilmProjectResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    name: str
    description: str | None
    language: FilmLanguage
    orientation: Orientation
    style_id: str
    style_name: str
    clip_duration_s: int
    allow_dialogue: bool
    allow_narration: bool
    narrator_voice_id: str | None
    allow_music: bool
    status: ProjectStatus
    last_episode_number: int
    flow_project_id: str | None
    episode_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_summary(cls, summary: ProjectSummary) -> "FilmProjectResponse":
        return cls.model_validate(
            {
                **_orm_fields(summary.project, cls, {"style_name", "episode_count"}),
                "style_name": summary.style_name,
                "episode_count": summary.episode_count,
            }
        )


class EpisodeResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    project_id: str
    number: int
    title: str
    logline: str | None
    source: EpisodeSource
    idea: str | None
    source_job_id: str | None
    source_clone_id: str | None
    target_duration_s: int
    stop_points: StopPoints
    paused_stop_point: EpisodeStep | None
    burn_subtitles: bool
    subtitle_style: SubtitleStyle
    music_prompt: str | None
    thumbnail_prompt: str | None
    music_status: MediaStatus
    music_path: str | None
    music_error: str | None
    preset: dict[str, Any]
    ai_used: AiUsedResponse
    status: EpisodeStatus
    step: EpisodeStep | None
    error_message: str | None
    needs_assembly: bool
    video_path: str | None
    subtitles_path: str | None
    thumbnail_path: str | None
    duration_ms: int | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_summary(cls, summary: EpisodeSummary) -> "EpisodeResponse":
        return cls.model_validate(_orm_fields(summary.episode, cls, set()))


class FilmProjectDetailResponse(FilmProjectResponse):
    characters: list[CharacterResponse]
    episodes: list[EpisodeResponse]
    is_look_fixed: bool
    open_requests: list[GenerationRequestResponse]

    @classmethod
    def from_detail(cls, detail: ProjectDetail) -> "FilmProjectDetailResponse":
        project_fields = FilmProjectResponse.from_summary(detail.summary).model_dump()
        return cls.model_validate(
            {
                **project_fields,
                "characters": [
                    CharacterResponse.from_summary(summary) for summary in detail.characters
                ],
                "episodes": [EpisodeResponse.from_summary(summary) for summary in detail.episodes],
                "is_look_fixed": detail.is_look_fixed,
                "open_requests": [
                    GenerationRequestResponse.model_validate(request)
                    for request in detail.open_requests
                ],
            }
        )


class SceneResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    id: str
    episode_id: str
    position: int
    image_prompt: str
    video_prompt: str
    narrator_text: str | None
    character_ids: list[str]
    clip_duration_s: int
    image_status: MediaStatus
    clip_status: MediaStatus
    narration_status: MediaStatus
    image_source: SceneImageSource | None
    image_path: str | None
    clip_path: str | None
    narration_path: str | None
    image_error: str | None
    clip_error: str | None
    narration_error: str | None
    clip_duration_ms: int | None
    narration_duration_ms: int | None
    trim_start_ms: int
    trim_end_ms: int | None
    created_at: datetime
    updated_at: datetime


class ThumbnailCandidateResponse(BaseModel):
    model_config = ORM_CAMEL_CASE_CONFIG

    candidate: int
    status: GenerationStatus
    path: str | None
    error_message: str | None


class EpisodeDetailResponse(EpisodeResponse):
    film_script_prompt: str
    project_name: str
    is_source_deleted: bool
    scenes: list[SceneResponse]
    open_requests: list[GenerationRequestResponse]
    thumbnail_candidates: list[ThumbnailCandidateResponse]

    @classmethod
    def from_detail(cls, detail: EpisodeDetail) -> "EpisodeDetailResponse":
        episode_fields = EpisodeResponse.from_summary(detail.summary).model_dump()
        return cls.model_validate(
            {
                **episode_fields,
                "film_script_prompt": detail.summary.episode.film_script_prompt,
                "project_name": detail.project.name,
                "is_source_deleted": detail.is_source_deleted,
                "scenes": [SceneResponse.model_validate(scene) for scene in detail.scenes],
                "open_requests": [
                    GenerationRequestResponse.model_validate(request)
                    for request in detail.open_requests
                ],
                "thumbnail_candidates": [
                    ThumbnailCandidateResponse.model_validate(candidate)
                    for candidate in detail.thumbnail_candidates
                ],
            }
        )


def _orm_fields(
    orm_object: object, response_class: type[BaseModel], skipped_fields: set[str]
) -> dict[str, Any]:
    return {
        name: getattr(orm_object, name)
        for name in response_class.model_fields
        if name not in skipped_fields and hasattr(orm_object, name)
    }
