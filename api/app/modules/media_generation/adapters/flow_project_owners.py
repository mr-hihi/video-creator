from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.repository import GenerationRequestRepository

FLOW_PROJECT_ID_FIELD = "flow_project_id"
CLONE_NAME_PREFIX = "Film clone"
CLONE_NAME_ID_LENGTH = 8


class FlowProjectOwnerKind(StrEnum):
    FILM_PROJECT = "film_project"
    FILM_CLONE = "film_clone"


@dataclass(frozen=True)
class FlowProjectOwner:
    kind: FlowProjectOwnerKind
    owner_id: str
    name: str
    flow_project_id: str | None


class FlowProjectOwners(Protocol):
    def find_owner(self, request_id: str) -> FlowProjectOwner | None: ...

    def save_flow_project_id(self, owner: FlowProjectOwner, flow_project_id: str) -> None: ...


@dataclass(frozen=True)
class FlowProjectOwnerRepositories:
    requests: GenerationRequestRepository
    films: FilmRepository
    clones: FilmCloneRepository


class RepositoryFlowProjectOwners:
    def __init__(self, repositories: FlowProjectOwnerRepositories):
        self._repositories = repositories

    def find_owner(self, request_id: str) -> FlowProjectOwner | None:
        request = self._repositories.requests.find_by_id(request_id)
        if request is None:
            return None
        if request.project_id is not None:
            return self._find_project_owner(request.project_id)
        if request.clone_id is not None:
            return self._find_clone_owner(request.clone_id)
        return None

    def save_flow_project_id(self, owner: FlowProjectOwner, flow_project_id: str) -> None:
        values = {FLOW_PROJECT_ID_FIELD: flow_project_id}
        if owner.kind is FlowProjectOwnerKind.FILM_PROJECT:
            self._repositories.films.update_project(owner.owner_id, values)
            return
        self._repositories.clones.update_clone(owner.owner_id, values)

    def _find_project_owner(self, project_id: str) -> FlowProjectOwner | None:
        project = self._repositories.films.find_project(project_id)
        if project is None:
            return None
        return FlowProjectOwner(
            FlowProjectOwnerKind.FILM_PROJECT, project.id, project.name, project.flow_project_id
        )

    def _find_clone_owner(self, clone_id: str) -> FlowProjectOwner | None:
        clone = self._repositories.clones.find_by_id(clone_id)
        if clone is None:
            return None
        return FlowProjectOwner(
            FlowProjectOwnerKind.FILM_CLONE,
            clone.id,
            to_clone_project_name(clone.id, clone.script_title),
            clone.flow_project_id,
        )


def to_clone_project_name(clone_id: str, script_title: str | None) -> str:
    if script_title is not None and script_title.strip():
        return script_title.strip()
    return f"{CLONE_NAME_PREFIX} {clone_id[:CLONE_NAME_ID_LENGTH]}"
