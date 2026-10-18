from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.films.errors import (
    FilmConflictError,
    FilmFileTooLargeError,
    FilmNotFoundError,
    InvalidFilmRequestError,
)

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    FilmNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidFilmRequestError: status.HTTP_400_BAD_REQUEST,
    FilmConflictError: status.HTTP_409_CONFLICT,
    FilmFileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
}


def register_film_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_film_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_film_error
