from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.prompt_presets.errors import (
    InvalidPresetError,
    PresetConflictError,
    PresetFileTooLargeError,
    PresetVersionNotFoundError,
    PromptPresetNotFoundError,
)

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    PromptPresetNotFoundError: status.HTTP_404_NOT_FOUND,
    PresetVersionNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidPresetError: status.HTTP_400_BAD_REQUEST,
    PresetConflictError: status.HTTP_409_CONFLICT,
    PresetFileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
}


def register_prompt_preset_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_prompt_preset_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_prompt_preset_error
