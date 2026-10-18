from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import FileResponse

from app.modules.films.film_outputs import FilmOutput
from app.modules.films.request_service import FilmRequestService
from app.modules.films.result_files import FilmResultFiles
from app.modules.films.schemas import ChooseThumbnailRequest, EpisodeResponse
from app.modules.films.thumbnail_service import FilmThumbnailService
from app.modules.media_generation.schemas import GenerationRequestResponse

router = APIRouter(prefix="/films", tags=["films"])


@dataclass(frozen=True)
class FilmResultServices:
    thumbnails: FilmThumbnailService
    result_files: FilmResultFiles
    requests: FilmRequestService


def get_film_result_services(request: Request) -> FilmResultServices:
    container = request.app.state.container
    return FilmResultServices(
        thumbnails=container.film_thumbnail_service,
        result_files=container.film_result_files,
        requests=container.film_request_service,
    )


ServicesDependency = Annotated[FilmResultServices, Depends(get_film_result_services)]


@router.post("/episodes/{episode_id}/thumbnails", status_code=status.HTTP_202_ACCEPTED)
def generate_thumbnails(
    episode_id: str, services: ServicesDependency
) -> list[GenerationRequestResponse]:
    return [
        GenerationRequestResponse.model_validate(request)
        for request in services.thumbnails.generate_candidates(episode_id)
    ]


@router.post("/episodes/{episode_id}/thumbnail")
def choose_thumbnail(
    episode_id: str, body: ChooseThumbnailRequest, services: ServicesDependency
) -> EpisodeResponse:
    summary = services.thumbnails.choose_candidate(episode_id, body.candidate)
    return EpisodeResponse.from_summary(summary)


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: str, services: ServicesDependency) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(services.requests.cancel(request_id))


@router.get("/episodes/{episode_id}/download")
def download_episode_file(
    episode_id: str, file: Annotated[FilmOutput, Query()], services: ServicesDependency
) -> FileResponse:
    download = services.result_files.get_download(episode_id, file)
    return FileResponse(download.path, filename=download.file_name)


@router.get("/files/{relative_path:path}")
def get_film_file(relative_path: str, services: ServicesDependency) -> FileResponse:
    return FileResponse(services.result_files.resolve_preview(relative_path))
