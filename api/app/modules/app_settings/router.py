from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Request

from app.modules.app_settings.ai_model_service import AiModelSettingService
from app.modules.app_settings.schemas import AiModelSettingsResponse, UpdateAiModelSettingsRequest
from app.modules.app_settings.service import AppSettingService

router = APIRouter(prefix="/settings", tags=["settings"])


def get_app_setting_service(request: Request) -> AppSettingService:
    return request.app.state.container.app_setting_service


def get_ai_model_setting_service(request: Request) -> AiModelSettingService:
    return request.app.state.container.ai_model_setting_service


AppSettingServiceDependency = Annotated[AppSettingService, Depends(get_app_setting_service)]
AiModelSettingServiceDependency = Annotated[
    AiModelSettingService, Depends(get_ai_model_setting_service)
]


@router.get("")
def get_settings(service: AppSettingServiceDependency) -> dict[str, Any]:
    return service.get_settings()


@router.patch("")
def update_settings(
    values: Annotated[dict[str, Any], Body()], service: AppSettingServiceDependency
) -> dict[str, Any]:
    return service.update_settings(values)


@router.patch("/ai-models")
def update_ai_model_settings(
    body: UpdateAiModelSettingsRequest, service: AiModelSettingServiceDependency
) -> AiModelSettingsResponse:
    return AiModelSettingsResponse.from_view(service.update_ai_model_settings(body.to_update()))
