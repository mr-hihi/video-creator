from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response, UploadFile, status

from app.modules.prompt_presets.preset_files import PresetDraft
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS, describe_app_added_parts
from app.modules.prompt_presets.schemas import (
    CreatePromptPresetRequest,
    PromptDefaultsResponse,
    PromptPresetDetailResponse,
    PromptPresetResponse,
    PromptPresetVersionDetailResponse,
    PromptPresetVersionResponse,
    PromptsBody,
    SavePromptPresetRequest,
)
from app.modules.prompt_presets.service import PresetUpload, PromptPresetService

JSON_MEDIA_TYPE = "application/json"

router = APIRouter(prefix="/prompt-presets", tags=["prompt-presets"])


def get_prompt_preset_service(request: Request) -> PromptPresetService:
    return request.app.state.container.prompt_preset_service


PromptPresetServiceDependency = Annotated[PromptPresetService, Depends(get_prompt_preset_service)]


@router.get("")
def list_prompt_presets(service: PromptPresetServiceDependency) -> list[PromptPresetResponse]:
    return [PromptPresetResponse.model_validate(preset) for preset in service.list_presets()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_prompt_preset(
    body: CreatePromptPresetRequest, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    return PromptPresetDetailResponse.from_detail(service.create_preset(body.name))


@router.get("/defaults")
def get_prompt_defaults() -> PromptDefaultsResponse:
    return PromptDefaultsResponse(
        prompts=PromptsBody.model_validate(DEFAULT_PRESET_PROMPTS),
        app_added_parts=PromptsBody.model_validate(describe_app_added_parts()),
    )


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_prompt_preset(
    file: UploadFile, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    upload = PresetUpload(filename=file.filename or "", stream=file.file)
    return PromptPresetDetailResponse.from_detail(service.import_preset(upload))


@router.get("/{preset_id}")
def get_prompt_preset(
    preset_id: str, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    return PromptPresetDetailResponse.from_detail(service.get_preset_detail(preset_id))


@router.put("/{preset_id}")
def save_prompt_preset(
    preset_id: str, body: SavePromptPresetRequest, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    draft = PresetDraft(name=body.name, prompts=body.prompts.to_preset_prompts())
    return PromptPresetDetailResponse.from_detail(service.save_preset(preset_id, draft))


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_prompt_preset(preset_id: str, service: PromptPresetServiceDependency) -> None:
    service.delete_preset(preset_id)


@router.post("/{preset_id}/default")
def mark_default_prompt_preset(
    preset_id: str, service: PromptPresetServiceDependency
) -> PromptPresetResponse:
    return PromptPresetResponse.model_validate(service.mark_default_preset(preset_id))


@router.post("/{preset_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_prompt_preset(
    preset_id: str, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    return PromptPresetDetailResponse.from_detail(service.duplicate_preset(preset_id))


@router.get("/{preset_id}/versions")
def list_prompt_preset_versions(
    preset_id: str, service: PromptPresetServiceDependency
) -> list[PromptPresetVersionResponse]:
    return [
        PromptPresetVersionResponse.model_validate(version)
        for version in service.list_versions(preset_id)
    ]


@router.get("/{preset_id}/versions/{version}")
def get_prompt_preset_version(
    preset_id: str, version: int, service: PromptPresetServiceDependency
) -> PromptPresetVersionDetailResponse:
    return PromptPresetVersionDetailResponse.from_version(service.get_version(preset_id, version))


@router.post("/{preset_id}/versions/{version}/restore")
def restore_prompt_preset_version(
    preset_id: str, version: int, service: PromptPresetServiceDependency
) -> PromptPresetDetailResponse:
    return PromptPresetDetailResponse.from_detail(service.restore_version(preset_id, version))


@router.get("/{preset_id}/export")
def export_prompt_preset(preset_id: str, service: PromptPresetServiceDependency) -> Response:
    exported = service.export_preset(preset_id)
    return Response(
        content=exported.content,
        media_type=JSON_MEDIA_TYPE,
        headers={"Content-Disposition": build_attachment_disposition(exported.filename)},
    )


def build_attachment_disposition(filename: str) -> str:
    quoted_filename = quote(filename)
    if quoted_filename == filename:
        return f'attachment; filename="{filename}"'
    return f"attachment; filename*=utf-8''{quoted_filename}"
