from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.common.captcha import require_captcha
from app.modules.film_clones.clone_actions import CloneActionService
from app.modules.film_clones.editing import (
    CloneEditingService,
    LocalizedAssetChanges,
    OriginalAssetChanges,
    SceneChanges,
)
from app.modules.film_clones.localization_rules import LocalizationChoices
from app.modules.film_clones.schemas import (
    AssetPatchRequest,
    CloneAssetResponse,
    CloneSceneResponse,
    CreateYoutubeFilmCloneRequest,
    FilmCloneDetailResponse,
    FilmCloneResponse,
    LocalizeRequest,
    ScenePatchRequest,
)
from app.modules.film_clones.service import CloneOptions, FilmCloneService
from app.modules.jobs.service import VideoUpload, YoutubeJobRequest
from app.modules.media_generation.schemas import GenerationRequestResponse

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
LOCALIZED_ASSET_FIELDS = frozenset({"changed", "localized_name", "localized_description"})

router = APIRouter(prefix="/film-clones", tags=["film-clones"])


@dataclass(frozen=True)
class FilmCloneServices:
    clones: FilmCloneService
    actions: CloneActionService
    editing: CloneEditingService


def get_film_clone_services(request: Request) -> FilmCloneServices:
    container = request.app.state.container
    return FilmCloneServices(
        clones=container.film_clone_service,
        actions=container.clone_action_service,
        editing=container.clone_editing_service,
    )


ServicesDependency = Annotated[FilmCloneServices, Depends(get_film_clone_services)]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_captcha)])
def create_film_clone(
    file: UploadFile,
    services: ServicesDependency,
    language: Annotated[str, Form()] = "auto",
    preset_id: Annotated[str | None, Form(alias="presetId")] = None,
    max_frames: Annotated[int | None, Form(alias="maxFrames")] = None,
    should_run_automatically: Annotated[bool, Form(alias="shouldRunAutomatically")] = False,
    target_country: Annotated[str | None, Form(alias="targetCountry")] = None,
    target_setting: Annotated[str | None, Form(alias="targetSetting")] = None,
    change_appearance: Annotated[bool, Form(alias="changeAppearance")] = False,
    change_costume: Annotated[bool, Form(alias="changeCostume")] = False,
    change_setting: Annotated[bool, Form(alias="changeSetting")] = False,
) -> FilmCloneResponse:
    upload = VideoUpload(
        filename=file.filename or "", stream=file.file, language=language, preset_id=preset_id
    )
    options = CloneOptions(
        max_frames=max_frames,
        should_run_automatically=should_run_automatically,
        choices=LocalizationChoices(
            target_country=target_country,
            target_setting=target_setting,
            change_appearance=change_appearance,
            change_costume=change_costume,
            change_setting=change_setting,
        ),
    )
    return FilmCloneResponse.from_summary(services.clones.create_from_upload(upload, options))


@router.post(
    "/youtube", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_captcha)]
)
def create_youtube_film_clone(
    body: CreateYoutubeFilmCloneRequest, services: ServicesDependency
) -> FilmCloneResponse:
    request = YoutubeJobRequest(link=body.url, language=body.language, preset_id=body.preset_id)
    options = CloneOptions(
        max_frames=body.max_frames,
        should_run_automatically=body.should_run_automatically,
        choices=to_localization_choices(body),
    )
    return FilmCloneResponse.from_summary(services.clones.create_from_youtube(request, options))


@router.get("")
def list_film_clones(
    services: ServicesDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
) -> list[FilmCloneResponse]:
    return [
        FilmCloneResponse.from_summary(summary) for summary in services.clones.list_recent(limit)
    ]


@router.get("/files/{relative_path:path}")
def get_clone_file(relative_path: str, services: ServicesDependency) -> FileResponse:
    return FileResponse(services.clones.resolve_file(relative_path))


@router.patch("/assets/{asset_id}")
def update_asset(
    asset_id: str, body: AssetPatchRequest, services: ServicesDependency
) -> CloneAssetResponse:
    if body.model_fields_set & LOCALIZED_ASSET_FIELDS:
        asset = services.editing.update_localized_asset(
            asset_id,
            LocalizedAssetChanges(
                changed=body.changed,
                localized_name=body.localized_name,
                localized_description=body.localized_description,
            ),
        )
    else:
        asset = services.editing.update_original_asset(
            asset_id,
            OriginalAssetChanges(
                name=body.name,
                kind=body.kind,
                description=body.description,
                culture=body.culture,
                period=body.period,
            ),
        )
    return CloneAssetResponse.model_validate(asset)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: str, services: ServicesDependency) -> None:
    services.editing.delete_asset(asset_id)


@router.post("/assets/{asset_id}/generate-reference", status_code=status.HTTP_202_ACCEPTED)
def generate_reference(asset_id: str, services: ServicesDependency) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.editing.generate_reference(asset_id))


@router.patch("/scenes/{scene_id}")
def update_scene(
    scene_id: str, body: ScenePatchRequest, services: ServicesDependency
) -> CloneSceneResponse:
    dialogue = body.dialogue
    if "dialogue" in body.model_fields_set and dialogue is None:
        dialogue = ""
    scene = services.editing.update_scene(
        scene_id,
        SceneChanges(
            description=body.description, dialogue=dialogue, image_prompt=body.image_prompt
        ),
    )
    return CloneSceneResponse.model_validate(scene)


@router.post("/scenes/{scene_id}/generate-image", status_code=status.HTTP_202_ACCEPTED)
def generate_scene_image(scene_id: str, services: ServicesDependency) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.editing.generate_scene_image(scene_id))


@router.get("/{clone_id}")
def get_film_clone(clone_id: str, services: ServicesDependency) -> FilmCloneDetailResponse:
    return FilmCloneDetailResponse.from_detail(services.clones.get_detail(clone_id))


@router.delete("/{clone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_film_clone(clone_id: str, services: ServicesDependency) -> None:
    services.clones.delete(clone_id)


@router.post("/{clone_id}/localization")
def localize(
    clone_id: str, body: LocalizeRequest, services: ServicesDependency
) -> FilmCloneResponse:
    services.actions.localize(clone_id, to_localization_choices(body))
    return FilmCloneResponse.from_summary(services.clones.get_summary(clone_id))


@router.post("/{clone_id}/write-script")
def write_script(clone_id: str, services: ServicesDependency) -> FilmCloneResponse:
    services.actions.write_script(clone_id)
    return FilmCloneResponse.from_summary(services.clones.get_summary(clone_id))


@router.post("/{clone_id}/resume")
def resume(clone_id: str, services: ServicesDependency) -> FilmCloneResponse:
    services.actions.resume(clone_id)
    return FilmCloneResponse.from_summary(services.clones.get_summary(clone_id))


@router.post("/{clone_id}/relocalize")
def relocalize(clone_id: str, services: ServicesDependency) -> FilmCloneResponse:
    services.actions.relocalize(clone_id)
    return FilmCloneResponse.from_summary(services.clones.get_summary(clone_id))


def to_localization_choices(
    body: LocalizeRequest | CreateYoutubeFilmCloneRequest,
) -> LocalizationChoices:
    return LocalizationChoices(
        target_country=body.target_country,
        target_setting=body.target_setting,
        change_appearance=body.change_appearance,
        change_costume=body.change_costume,
        change_setting=body.change_setting,
    )
