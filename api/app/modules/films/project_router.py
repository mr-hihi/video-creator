from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.modules.films.models import ProjectStatus
from app.modules.films.project_service import FilmProjectService, ProjectChanges, ProjectDraft
from app.modules.films.request_values import to_patch_values
from app.modules.films.schemas import (
    CreateProjectRequest,
    EditPromptRequest,
    FilmProjectDetailResponse,
    FilmProjectResponse,
    UpdateProjectRequest,
)
from app.modules.media_generation.schemas import GenerationRequestResponse

CLEARABLE_PROJECT_FIELDS = frozenset({"description", "narrator_voice_id"})

router = APIRouter(prefix="/films/projects", tags=["films"])


def get_film_project_service(request: Request) -> FilmProjectService:
    return request.app.state.container.film_project_service


ProjectServiceDependency = Annotated[FilmProjectService, Depends(get_film_project_service)]


@router.get("")
def list_projects(
    service: ProjectServiceDependency,
    project_status: Annotated[ProjectStatus, Query(alias="status")] = ProjectStatus.ACTIVE,
) -> list[FilmProjectResponse]:
    return [
        FilmProjectResponse.from_summary(summary)
        for summary in service.list_projects(project_status)
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest, service: ProjectServiceDependency
) -> FilmProjectDetailResponse:
    detail = service.create_project(ProjectDraft(**body.model_dump()))
    return FilmProjectDetailResponse.from_detail(detail)


@router.get("/{project_id}")
def get_project(project_id: str, service: ProjectServiceDependency) -> FilmProjectDetailResponse:
    return FilmProjectDetailResponse.from_detail(service.get_project(project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: str, body: UpdateProjectRequest, service: ProjectServiceDependency
) -> FilmProjectDetailResponse:
    changes = ProjectChanges(**to_patch_values(body, CLEARABLE_PROJECT_FIELDS))
    return FilmProjectDetailResponse.from_detail(service.update_project(project_id, changes))


@router.post("/{project_id}/archive")
def archive_project(project_id: str, service: ProjectServiceDependency) -> FilmProjectResponse:
    return FilmProjectResponse.from_summary(service.archive_project(project_id))


@router.post("/{project_id}/unarchive")
def unarchive_project(project_id: str, service: ProjectServiceDependency) -> FilmProjectResponse:
    return FilmProjectResponse.from_summary(service.unarchive_project(project_id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, service: ProjectServiceDependency) -> None:
    service.delete_project(project_id)


@router.put("/{project_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def link_character(project_id: str, character_id: str, service: ProjectServiceDependency) -> None:
    service.link_character(project_id, character_id)


@router.delete("/{project_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_character(project_id: str, character_id: str, service: ProjectServiceDependency) -> None:
    service.unlink_character(project_id, character_id)


@router.post("/{project_id}/characters/generate-missing", status_code=status.HTTP_202_ACCEPTED)
def generate_missing_references(
    project_id: str, service: ProjectServiceDependency
) -> list[GenerationRequestResponse]:
    return [
        GenerationRequestResponse.model_validate(generation_request)
        for generation_request in service.generate_missing_references(project_id)
    ]


@router.post(
    "/{project_id}/characters/{character_id}/generate-reference",
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_reference(
    project_id: str, character_id: str, service: ProjectServiceDependency
) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(
        service.generate_reference(project_id, character_id)
    )


@router.post(
    "/{project_id}/characters/{character_id}/edit-reference",
    status_code=status.HTTP_202_ACCEPTED,
)
def edit_reference(
    project_id: str,
    character_id: str,
    body: EditPromptRequest,
    service: ProjectServiceDependency,
) -> GenerationRequestResponse:
    return GenerationRequestResponse.model_validate(
        service.edit_reference(project_id, character_id, body.prompt)
    )
