from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.providers.errors import (
    ExtensionNotConnectedError,
    InvalidProviderSettingError,
    ProviderNotFoundError,
    SecretKeyMissingError,
)

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    ProviderNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidProviderSettingError: status.HTTP_400_BAD_REQUEST,
    SecretKeyMissingError: status.HTTP_409_CONFLICT,
    ExtensionNotConnectedError: status.HTTP_409_CONFLICT,
}


def register_provider_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_provider_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_provider_error
