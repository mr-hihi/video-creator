from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.film_clones.errors import (
    CloneAssetNotFoundError,
    CloneConflictError,
    CloneFileNotFoundError,
    CloneSceneNotFoundError,
    FilmCloneNotFoundError,
    InvalidCloneRequestError,
)

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    FilmCloneNotFoundError: status.HTTP_404_NOT_FOUND,
    CloneAssetNotFoundError: status.HTTP_404_NOT_FOUND,
    CloneSceneNotFoundError: status.HTTP_404_NOT_FOUND,
    CloneFileNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidCloneRequestError: status.HTTP_400_BAD_REQUEST,
    CloneConflictError: status.HTTP_409_CONFLICT,
}


def register_film_clone_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_film_clone_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_film_clone_error
