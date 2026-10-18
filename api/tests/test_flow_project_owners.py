from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.adapters.flow_project_owners import (
    FlowProjectOwner,
    FlowProjectOwnerKind,
    FlowProjectOwnerRepositories,
    RepositoryFlowProjectOwners,
)
from app.modules.media_generation.repository import GenerationRequestRepository

PROJECT_ID = "project-1"
CLONE_ID = "abcdef12-3456-7890-abcd-ef1234567890"
FLOW_PROJECT_ID = "594758cc-0000-4000-8000-000000000000"


def build_owners(request, project=None, clone=None) -> SimpleNamespace:
    repositories = FlowProjectOwnerRepositories(
        requests=MagicMock(spec=GenerationRequestRepository),
        films=MagicMock(spec=FilmRepository),
        clones=MagicMock(spec=FilmCloneRepository),
    )
    repositories.requests.find_by_id.return_value = request
    repositories.films.find_project.return_value = project
    repositories.clones.find_by_id.return_value = clone
    return SimpleNamespace(
        owners=RepositoryFlowProjectOwners(repositories), repositories=repositories
    )


def build_request(project_id=None, clone_id=None) -> SimpleNamespace:
    return SimpleNamespace(id="request-1", project_id=project_id, clone_id=clone_id)


def build_clone(script_title) -> SimpleNamespace:
    return SimpleNamespace(id=CLONE_ID, script_title=script_title, flow_project_id=None)


@pytest.fixture
def project_owner():
    project = SimpleNamespace(id=PROJECT_ID, name="Harbor", flow_project_id=FLOW_PROJECT_ID)
    rig = build_owners(build_request(project_id=PROJECT_ID), project=project)
    return rig.owners.find_owner("request-1")


@pytest.fixture(
    params=[
        ("  Night Market  ", "Night Market"),
        ("   ", "Film clone abcdef12"),
        (None, "Film clone abcdef12"),
    ]
)
def clone_owner_name(request):
    script_title, expected_name = request.param
    rig = build_owners(build_request(clone_id=CLONE_ID), clone=build_clone(script_title))
    return SimpleNamespace(owner=rig.owners.find_owner("request-1"), expected_name=expected_name)


@pytest.fixture(
    params=[
        build_owners(None),
        build_owners(build_request(project_id=PROJECT_ID)),
        build_owners(build_request(clone_id=CLONE_ID)),
        build_owners(build_request()),
    ],
    ids=["no request", "project gone", "clone gone", "neither project nor clone"],
)
def missing_owner(request):
    return request.param.owners.find_owner("request-1")


@pytest.fixture
def saved_for_project():
    rig = build_owners(None)
    owner = FlowProjectOwner(FlowProjectOwnerKind.FILM_PROJECT, PROJECT_ID, "Harbor", None)
    rig.owners.save_flow_project_id(owner, FLOW_PROJECT_ID)
    return rig.repositories


@pytest.fixture
def saved_for_clone():
    rig = build_owners(None)
    owner = FlowProjectOwner(FlowProjectOwnerKind.FILM_CLONE, CLONE_ID, "Night Market", None)
    rig.owners.save_flow_project_id(owner, FLOW_PROJECT_ID)
    return rig.repositories


def test_a_film_project_owns_its_requests(project_owner):
    assert project_owner == FlowProjectOwner(
        FlowProjectOwnerKind.FILM_PROJECT, PROJECT_ID, "Harbor", FLOW_PROJECT_ID
    )


def test_a_film_clone_is_named_after_its_script_title(clone_owner_name):
    assert clone_owner_name.owner == FlowProjectOwner(
        FlowProjectOwnerKind.FILM_CLONE, CLONE_ID, clone_owner_name.expected_name, None
    )


def test_no_owner_without_a_project_or_clone_row(missing_owner):
    assert missing_owner is None


def test_saving_for_a_project_updates_the_project(saved_for_project):
    assert saved_for_project.films.update_project.call_args.args == (
        PROJECT_ID,
        {"flow_project_id": FLOW_PROJECT_ID},
    )
    assert saved_for_project.clones.update_clone.call_count == 0


def test_saving_for_a_clone_updates_the_clone(saved_for_clone):
    assert saved_for_clone.clones.update_clone.call_args.args == (
        CLONE_ID,
        {"flow_project_id": FLOW_PROJECT_ID},
    )
    assert saved_for_clone.films.update_project.call_count == 0
