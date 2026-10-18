from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.modules.providers.schemas import (
    ConnectionTestResponse,
    ProviderResponse,
    ProviderSettingsResponse,
    UpdateProviderRequest,
)
from app.modules.providers.service import ProviderSettingService

router = APIRouter(prefix="/settings/providers", tags=["providers"])


def get_provider_setting_service(request: Request) -> ProviderSettingService:
    return request.app.state.container.provider_setting_service


ProviderSettingServiceDependency = Annotated[
    ProviderSettingService, Depends(get_provider_setting_service)
]


@router.get("")
def get_provider_settings(service: ProviderSettingServiceDependency) -> ProviderSettingsResponse:
    return ProviderSettingsResponse.from_view(service.get_settings_view())


@router.post("/google_flow/resume")
def resume_google_flow(service: ProviderSettingServiceDependency) -> ProviderResponse:
    return ProviderResponse.from_view(service.resume_google_flow())


@router.post("/google_flow/open-tab", status_code=status.HTTP_204_NO_CONTENT)
def open_flow_tab(service: ProviderSettingServiceDependency) -> None:
    service.open_flow_tab()


@router.patch("/{provider_id}")
def update_provider(
    provider_id: str, body: UpdateProviderRequest, service: ProviderSettingServiceDependency
) -> ProviderResponse:
    return ProviderResponse.from_view(service.update_provider(provider_id, body.to_update()))


@router.post("/{provider_id}/test")
def test_provider_connection(
    provider_id: str, service: ProviderSettingServiceDependency
) -> ConnectionTestResponse:
    return ConnectionTestResponse.from_result(service.test_connection(provider_id))
