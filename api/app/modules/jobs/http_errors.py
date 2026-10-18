from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.modules.jobs.errors import (
    InvalidFilmAnalysisJobError,
    InvalidUploadError,
    InvalidYoutubeJobError,
    JobNotDeletableError,
    JobNotFoundError,
    JobPresetNotFoundError,
    JobStillRunningError,
    NotFilmAnalysisJobError,
    NoVideoNotesError,
    NoZipDownloadError,
    ResultFileNotFoundError,
    ResultNotReadyError,
    YoutubeUnreachableError,
)
from app.modules.jobs.storage import UploadTooLargeError

STATUS_CODES_BY_ERROR: dict[type[Exception], int] = {
    JobNotFoundError: status.HTTP_404_NOT_FOUND,
    ResultFileNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidUploadError: status.HTTP_400_BAD_REQUEST,
    UploadTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    ResultNotReadyError: status.HTTP_409_CONFLICT,
    InvalidYoutubeJobError: status.HTTP_400_BAD_REQUEST,
    YoutubeUnreachableError: status.HTTP_502_BAD_GATEWAY,
    JobPresetNotFoundError: status.HTTP_400_BAD_REQUEST,
    InvalidFilmAnalysisJobError: status.HTTP_400_BAD_REQUEST,
    JobNotDeletableError: status.HTTP_409_CONFLICT,
    JobStillRunningError: status.HTTP_409_CONFLICT,
    NotFilmAnalysisJobError: status.HTTP_409_CONFLICT,
    NoVideoNotesError: status.HTTP_409_CONFLICT,
    NoZipDownloadError: status.HTTP_409_CONFLICT,
}


def register_job_error_handlers(app: FastAPI) -> None:
    for error_class, status_code in STATUS_CODES_BY_ERROR.items():
        app.add_exception_handler(error_class, _respond_with(status_code))


def _respond_with(status_code: int):
    async def handle_job_error(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(error)})

    return handle_job_error
