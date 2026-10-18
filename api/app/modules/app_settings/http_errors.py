from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.app_settings.errors import InvalidSettingError

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    InvalidSettingError: status.HTTP_400_BAD_REQUEST,
}


def register_app_setting_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_app_setting_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_app_setting_error
