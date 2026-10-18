from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.common.captcha import require_captcha
from app.modules.jobs.film_analysis_service import FilmAnalysisJobService
from app.modules.jobs.models import JobType
from app.modules.jobs.schemas import (
    CreateFilmAnalysisRerunJobRequest,
    CreateYoutubeFilmAnalysisJobRequest,
    CreateYoutubeToMarkdownJobRequest,
    JobDetailResponse,
    JobResponse,
)
from app.modules.jobs.service import JobService, VideoUpload, YoutubeJobRequest, YoutubeJobService

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
ZIP_MEDIA_TYPE = "application/zip"

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_job_service(request: Request) -> JobService:
    return request.app.state.container.job_service


def get_youtube_job_service(request: Request) -> YoutubeJobService:
    return request.app.state.container.youtube_job_service


def get_film_analysis_job_service(request: Request) -> FilmAnalysisJobService:
    return request.app.state.container.film_analysis_job_service


JobServiceDependency = Annotated[JobService, Depends(get_job_service)]
YoutubeJobServiceDependency = Annotated[YoutubeJobService, Depends(get_youtube_job_service)]
FilmAnalysisJobServiceDependency = Annotated[
    FilmAnalysisJobService, Depends(get_film_analysis_job_service)
]
LanguageForm = Annotated[str, Form()]
PresetIdForm = Annotated[str | None, Form(alias="presetId")]


@router.post(
    "/video-to-markdown",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_video_to_markdown_job(
    file: UploadFile,
    service: JobServiceDependency,
    language: LanguageForm = "auto",
    preset_id: PresetIdForm = None,
) -> JobResponse:
    upload = VideoUpload(
        filename=file.filename or "", stream=file.file, language=language, preset_id=preset_id
    )
    return JobResponse.model_validate(service.create_video_to_markdown_job(upload))


@router.post(
    "/youtube-to-markdown",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_youtube_to_markdown_job(
    body: CreateYoutubeToMarkdownJobRequest, service: YoutubeJobServiceDependency
) -> JobResponse:
    request = YoutubeJobRequest(link=body.url, language=body.language, preset_id=body.preset_id)
    return JobResponse.model_validate(service.create_youtube_to_markdown_job(request))


@router.post(
    "/film-analysis",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_film_analysis_job(
    file: UploadFile,
    service: FilmAnalysisJobServiceDependency,
    language: LanguageForm = "auto",
    preset_id: PresetIdForm = None,
    max_frames: Annotated[int | None, Form(alias="maxFrames")] = None,
) -> JobResponse:
    upload = VideoUpload(
        filename=file.filename or "", stream=file.file, language=language, preset_id=preset_id
    )
    return JobResponse.model_validate(service.create_film_analysis_job(upload, max_frames))


@router.post(
    "/youtube-film-analysis",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_youtube_film_analysis_job(
    body: CreateYoutubeFilmAnalysisJobRequest, service: YoutubeJobServiceDependency
) -> JobResponse:
    request = YoutubeJobRequest(link=body.url, language=body.language, preset_id=body.preset_id)
    return JobResponse.model_validate(
        service.create_youtube_film_analysis_job(request, body.max_frames)
    )


@router.post(
    "/{job_id}/film-analysis-rerun",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_captcha)],
)
def create_film_analysis_rerun_job(
    job_id: str,
    body: CreateFilmAnalysisRerunJobRequest,
    service: FilmAnalysisJobServiceDependency,
) -> JobResponse:
    return JobResponse.model_validate(service.create_rerun_job(job_id, body.preset_id))


@router.get("")
def list_jobs(
    service: JobServiceDependency,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
    types: Annotated[list[JobType] | None, Query(alias="type")] = None,
) -> list[JobResponse]:
    jobs = service.list_recent_jobs(limit, types or ())
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}")
def get_job(job_id: str, service: JobServiceDependency) -> JobDetailResponse:
    return JobDetailResponse.from_detail(service.get_job_detail(job_id))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, service: FilmAnalysisJobServiceDependency) -> None:
    service.delete_film_analysis_job(job_id)


@router.get("/{job_id}/files/{relative_path:path}")
def get_result_file(job_id: str, relative_path: str, service: JobServiceDependency) -> FileResponse:
    return FileResponse(service.resolve_result_file(job_id, relative_path))


@router.get("/{job_id}/download")
def download_result(job_id: str, service: JobServiceDependency) -> FileResponse:
    archive = service.get_result_archive(job_id)
    return FileResponse(archive.path, media_type=ZIP_MEDIA_TYPE, filename=archive.download_name)
