from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, UploadFile, status

from app.common.captcha import require_captcha
from app.modules.films.episode_service import EpisodeDraft, EpisodeService
from app.modules.films.film_access import FilmAccess
from app.modules.films.models import Episode
from app.modules.films.request_values import to_patch_values
from app.modules.films.scene_service import SceneDraft, SceneService
from app.modules.films.schemas import (
    CreateEpisodeRequest,
    CreateSceneRequest,
    EditPromptRequest,
    EpisodeDetailResponse,
    EpisodeResponse,
    SceneResponse,
    UpdateEpisodeRequest,
    UpdateSceneRequest,
)
from app.modules.films.stage_runner import EpisodeStageRunner
from app.modules.films.upload_rules import FileUpload
from app.modules.films.views import EpisodeSummary
from app.modules.media_generation.schemas import GenerationRequestResponse

NO_CLEARED_TEXT_FIELDS: tuple[str, ...] = ()

router = APIRouter(prefix="/films", tags=["films"])


@dataclass(frozen=True)
class EpisodeRouteServices:
    episodes: EpisodeService
    scenes: SceneService
    stage_runner: EpisodeStageRunner
    access: FilmAccess


def get_episode_route_services(request: Request) -> EpisodeRouteServices:
    container = request.app.state.container
    return EpisodeRouteServices(
        episodes=container.film_episode_service,
        scenes=container.film_scene_service,
        stage_runner=container.film_stage_runner,
        access=container.film_access,
    )


ServicesDependency = Annotated[EpisodeRouteServices, Depends(get_episode_route_services)]


def to_episode_changes(body: UpdateEpisodeRequest) -> dict[str, Any]:
    changes = to_patch_values(body, NO_CLEARED_TEXT_FIELDS)
    if body.stop_points is not None:
        changes["stop_points"] = body.stop_points.model_dump(by_alias=True)
    return changes


def to_episode_response(episode: Episode) -> EpisodeResponse:
    return EpisodeResponse.from_summary(EpisodeSummary(episode))


@router.post(
    "/projects/{project_id}/episodes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_episode(
    project_id: str, body: CreateEpisodeRequest, services: ServicesDependency
) -> EpisodeResponse:
    draft = EpisodeDraft(
        source=body.source,
        idea=body.idea,
        source_job_id=body.source_job_id,
        source_clone_id=body.source_clone_id,
        target_duration_s=body.target_duration_s,
        stop_points=body.stop_points.model_dump(by_alias=True),
        burn_subtitles=body.burn_subtitles,
        subtitle_style=body.subtitle_style,
        preset_id=body.preset_id,
    )
    return EpisodeResponse.from_summary(services.episodes.create_episode(project_id, draft))


@router.get("/episodes/{episode_id}")
def get_episode(episode_id: str, services: ServicesDependency) -> EpisodeDetailResponse:
    return EpisodeDetailResponse.from_detail(services.episodes.get_episode_detail(episode_id))


@router.patch("/episodes/{episode_id}")
def update_episode(
    episode_id: str, body: UpdateEpisodeRequest, services: ServicesDependency
) -> EpisodeResponse:
    summary = services.episodes.update_episode(episode_id, to_episode_changes(body))
    return EpisodeResponse.from_summary(summary)


@router.delete("/episodes/{episode_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_episode(episode_id: str, services: ServicesDependency) -> None:
    services.episodes.delete_episode(episode_id)


@router.post("/episodes/{episode_id}/start")
def start_episode(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.start(context))


@router.post("/episodes/{episode_id}/continue")
def continue_episode(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.continue_episode(context))


@router.post("/episodes/{episode_id}/stop")
def stop_episode(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.stop(context))


@router.post("/episodes/{episode_id}/resume")
def resume_episode(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.resume(context))


@router.post("/episodes/{episode_id}/assemble")
def assemble_episode(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.assemble(context))


@router.post("/episodes/{episode_id}/rewrite-script")
def rewrite_episode_script(episode_id: str, services: ServicesDependency) -> EpisodeResponse:
    context = services.access.get_episode(episode_id)
    return to_episode_response(services.stage_runner.rewrite_script(context))


@router.post("/episodes/{episode_id}/scenes", status_code=status.HTTP_201_CREATED)
def add_scene(
    episode_id: str, body: CreateSceneRequest, services: ServicesDependency
) -> SceneResponse:
    draft = SceneDraft(
        after_position=body.after_position,
        image_prompt=body.image_prompt,
        video_prompt=body.video_prompt,
        narrator_text=body.narrator_text,
        character_ids=body.character_ids,
        clip_duration_s=body.clip_duration_s,
    )
    return SceneResponse.model_validate(services.scenes.add_scene(episode_id, draft))


@router.patch("/scenes/{scene_id}")
def update_scene(
    scene_id: str, body: UpdateSceneRequest, services: ServicesDependency
) -> SceneResponse:
    scene = services.scenes.update_scene(scene_id, to_patch_values(body, NO_CLEARED_TEXT_FIELDS))
    return SceneResponse.model_validate(scene)


@router.delete("/scenes/{scene_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scene(scene_id: str, services: ServicesDependency) -> None:
    services.scenes.delete_scene(scene_id)


@router.post("/scenes/{scene_id}/image")
def upload_scene_image(
    scene_id: str, file: UploadFile, services: ServicesDependency
) -> SceneResponse:
    upload = FileUpload(filename=file.filename or "", stream=file.file)
    return SceneResponse.model_validate(services.scenes.upload_image(scene_id, upload))


@router.post("/scenes/{scene_id}/generate-image", status_code=status.HTTP_202_ACCEPTED)
def generate_scene_image(scene_id: str, services: ServicesDependency) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.scenes.generate_image(scene_id))


@router.post("/scenes/{scene_id}/generate-clip", status_code=status.HTTP_202_ACCEPTED)
def generate_scene_clip(scene_id: str, services: ServicesDependency) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.scenes.generate_clip(scene_id))


@router.post("/scenes/{scene_id}/generate-narration", status_code=status.HTTP_202_ACCEPTED)
def generate_scene_narration(
    scene_id: str, services: ServicesDependency
) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.scenes.generate_narration(scene_id))


@router.post("/scenes/{scene_id}/edit-image", status_code=status.HTTP_202_ACCEPTED)
def edit_scene_image(
    scene_id: str, body: EditPromptRequest, services: ServicesDependency
) -> GenerationRequestResponse:
    request = services.scenes.edit_image(scene_id, body.prompt)
    return GenerationRequestResponse.model_validate(request)
