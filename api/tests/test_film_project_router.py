from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.films.errors import (
    FilmConflictError,
    FilmProjectNotFoundError,
    InvalidFilmRequestError,
)
from app.modules.films.http_errors import register_film_error_handlers
from app.modules.films.models import (
    Character,
    EntityType,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    ProjectStatus,
)
from app.modules.films.project_router import router
from app.modules.films.project_service import FilmProjectService, ProjectChanges, ProjectDraft
from app.modules.films.views import CharacterSummary, ProjectDetail, ProjectSummary
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.providers.provider_catalog import MediaKind

CREATED_AT = datetime.now(UTC)
PROJECT_BODY = {
    "name": "Harbor Mysteries",
    "language": "en",
    "orientation": "landscape",
    "styleId": "anime",
    "characterIds": ["c-1"],
}


def build_project(status: ProjectStatus) -> FilmProject:
    return FilmProject(
        id="p-1",
        name="Harbor Mysteries",
        description=None,
        language=FilmLanguage.ENGLISH,
        orientation=Orientation.LANDSCAPE,
        style_id="anime",
        clip_duration_s=6,
        allow_dialogue=True,
        allow_narration=True,
        narrator_voice_id=None,
        allow_music=True,
        status=status,
        last_episode_number=0,
        flow_project_id=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


MAI = Character(
    id="c-1",
    name="Mai",
    entity_type=EntityType.CHARACTER,
    description="A young fisher",
    image_prompt="Reference image of a young fisher",
    voice_description=None,
    style_id="realistic",
    reference_status=MediaStatus.NONE,
    reference_source=None,
    reference_path=None,
    reference_error=None,
    provider_media=None,
    origin_job_id=None,
    origin_clone_id=None,
    created_at=CREATED_AT,
    updated_at=CREATED_AT,
)
ACTIVE_SUMMARY = ProjectSummary(build_project(ProjectStatus.ACTIVE), "Anime", 2)
ARCHIVED_SUMMARY = ProjectSummary(build_project(ProjectStatus.ARCHIVED), "Anime", 2)
REQUEST = GenerationRequest(
    id="r-1",
    kind=GenerationKind.CHARACTER_IMAGE,
    media_kind=MediaKind.IMAGE,
    project_id="p-1",
    character_id="c-1",
    provider="google_flow",
    status=GenerationStatus.QUEUED,
    params={"aspect": "9:16"},
    attempts=0,
    created_at=CREATED_AT,
)
DETAIL = ProjectDetail(
    summary=ACTIVE_SUMMARY,
    characters=[CharacterSummary(MAI, "Photorealistic", 1)],
    episodes=[],
    is_look_fixed=False,
    open_requests=[REQUEST],
)


@pytest.fixture
def service():
    project_service = MagicMock(spec=FilmProjectService)
    project_service.list_projects.return_value = [ACTIVE_SUMMARY]
    project_service.create_project.return_value = DETAIL
    project_service.get_project.return_value = DETAIL
    project_service.update_project.return_value = DETAIL
    project_service.archive_project.return_value = ARCHIVED_SUMMARY
    project_service.unarchive_project.return_value = ACTIVE_SUMMARY
    project_service.generate_missing_references.return_value = [REQUEST]
    project_service.generate_reference.return_value = REQUEST
    project_service.edit_reference.return_value = REQUEST
    return project_service


@pytest.fixture
def client(service):
    app = FastAPI()
    app.include_router(router)
    register_film_error_handlers(app)
    app.state.container = SimpleNamespace(film_project_service=service)
    return TestClient(app)


def to_outcome(response, service_method):
    return SimpleNamespace(
        status_code=response.status_code,
        body=response.json() if response.content else None,
        call=service_method.call_args,
    )


@pytest.fixture
def listed(client, service):
    return to_outcome(client.get("/films/projects"), service.list_projects)


@pytest.fixture
def archived_listed(client, service):
    return to_outcome(client.get("/films/projects?status=archived"), service.list_projects)


@pytest.fixture
def bad_status_response(client):
    return client.get("/films/projects?status=deleted")


@pytest.fixture
def created(client, service):
    return to_outcome(client.post("/films/projects", json=PROJECT_BODY), service.create_project)


@pytest.fixture(params=[{"orientation": "square"}, {"name": None}, {"language": "fr"}])
def unprocessable_create_response(request, client):
    body = {key: value for key, value in PROJECT_BODY.items() if key != "name"}
    return client.post("/films/projects", json={**body, **request.param})


@pytest.fixture(
    params=[
        (InvalidFilmRequestError("Project name must be 1-100 characters"), 400),
        (FilmConflictError("A project named 'test series' already exists"), 409),
    ]
)
def rejected_create(request, client, service):
    error, expected_status = request.param
    service.create_project.side_effect = error
    response = client.post("/films/projects", json=PROJECT_BODY)
    return SimpleNamespace(
        status_code=response.status_code,
        expected_status=expected_status,
        body=response.json(),
        expected_body={"detail": str(error)},
    )


@pytest.fixture
def fetched(client, service):
    return to_outcome(client.get("/films/projects/p-1"), service.get_project)


@pytest.fixture
def missing_response(client, service):
    service.get_project.side_effect = FilmProjectNotFoundError("p-x")
    return to_outcome(client.get("/films/projects/p-x"), service.get_project)


@pytest.fixture
def patched(client, service):
    return to_outcome(
        client.patch(
            "/films/projects/p-1",
            json={"narratorVoiceId": None, "description": None, "clipDurationS": 10},
        ),
        service.update_project,
    )


@pytest.fixture
def bad_orientation_response(client):
    return client.patch("/films/projects/p-1", json={"orientation": "square"})


@pytest.fixture
def archived(client, service):
    return to_outcome(client.post("/films/projects/p-1/archive"), service.archive_project)


@pytest.fixture
def unarchived(client, service):
    return to_outcome(client.post("/films/projects/p-1/unarchive"), service.unarchive_project)


@pytest.fixture
def deleted(client, service):
    return to_outcome(client.delete("/films/projects/p-1"), service.delete_project)


@pytest.fixture
def linked(client, service):
    return to_outcome(client.put("/films/projects/p-1/characters/c-1"), service.link_character)


@pytest.fixture
def unlinked(client, service):
    return to_outcome(client.delete("/films/projects/p-1/characters/c-1"), service.unlink_character)


@pytest.fixture
def missing_generated(client, service):
    return to_outcome(
        client.post("/films/projects/p-1/characters/generate-missing"),
        service.generate_missing_references,
    )


@pytest.fixture
def reference_generated(client, service):
    return to_outcome(
        client.post("/films/projects/p-1/characters/c-1/generate-reference"),
        service.generate_reference,
    )


@pytest.fixture
def reference_edited(client, service):
    return to_outcome(
        client.post(
            "/films/projects/p-1/characters/c-1/edit-reference", json={"prompt": "Add a hat"}
        ),
        service.edit_reference,
    )


def test_list_defaults_to_active_projects(listed):
    assert listed.status_code == 200
    assert listed.call.args == (ProjectStatus.ACTIVE,)
    assert listed.body[0]["id"] == "p-1"
    assert listed.body[0]["styleName"] == "Anime"
    assert listed.body[0]["episodeCount"] == 2
    assert listed.body[0]["flowProjectId"] is None


def test_list_reads_the_status_query(archived_listed):
    assert archived_listed.call.args == (ProjectStatus.ARCHIVED,)


def test_list_rejects_an_unknown_status(bad_status_response):
    assert bad_status_response.status_code == 422


def test_create_answers_201_with_the_detail(created):
    assert created.status_code == 201
    assert created.body["characters"][0]["name"] == "Mai"
    assert created.body["characters"][0]["providerMedia"] is None
    assert created.body["episodes"] == []
    assert created.body["isLookFixed"] is False
    assert created.body["clipDurationS"] == 6


def test_create_passes_the_draft_with_defaults(created):
    assert created.call.args == (
        ProjectDraft(
            name="Harbor Mysteries",
            language=FilmLanguage.ENGLISH,
            orientation=Orientation.LANDSCAPE,
            style_id="anime",
            clip_duration_s=8,
            allow_dialogue=True,
            allow_narration=True,
            allow_music=False,
            description=None,
            narrator_voice_id=None,
            character_ids=["c-1"],
        ),
    )


def test_create_rejects_a_missing_field_or_enum_value(unprocessable_create_response):
    assert unprocessable_create_response.status_code == 422


def test_create_maps_domain_errors(rejected_create):
    assert rejected_create.status_code == rejected_create.expected_status
    assert rejected_create.body == rejected_create.expected_body


def test_get_returns_the_detail(fetched):
    assert fetched.status_code == 200
    assert fetched.call.args == ("p-1",)
    assert fetched.body["characters"][0]["styleName"] == "Photorealistic"
    assert fetched.body["openRequests"][0]["characterId"] == "c-1"


def test_get_of_unknown_project_is_404(missing_response):
    assert missing_response.status_code == 404
    assert missing_response.body == {"detail": "Film project p-x not found"}


def test_patch_turns_sent_nulls_into_cleared_values(patched):
    assert patched.status_code == 200
    assert patched.call.args == (
        "p-1",
        ProjectChanges(description="", clip_duration_s=10, narrator_voice_id=""),
    )


def test_patch_rejects_an_unknown_orientation(bad_orientation_response):
    assert bad_orientation_response.status_code == 422


def test_archive_returns_the_project(archived):
    assert archived.status_code == 200
    assert archived.call.args == ("p-1",)
    assert archived.body["status"] == "archived"


def test_unarchive_returns_the_project(unarchived):
    assert unarchived.status_code == 200
    assert unarchived.body["status"] == "active"


def test_delete_answers_204(deleted):
    assert deleted.status_code == 204
    assert deleted.call.args == ("p-1",)


def test_link_answers_204(linked):
    assert linked.status_code == 204
    assert linked.call.args == ("p-1", "c-1")


def test_unlink_answers_204(unlinked):
    assert unlinked.status_code == 204
    assert unlinked.call.args == ("p-1", "c-1")


def test_generate_missing_answers_202_with_the_requests(missing_generated):
    assert missing_generated.status_code == 202
    assert missing_generated.call.args == ("p-1",)
    assert missing_generated.body[0]["kind"] == "character_image"
    assert missing_generated.body[0]["characterId"] == "c-1"


def test_generate_reference_answers_202(reference_generated):
    assert reference_generated.status_code == 202
    assert reference_generated.call.args == ("p-1", "c-1")
    assert reference_generated.body["params"] == {"aspect": "9:16"}


def test_edit_reference_passes_the_prompt(reference_edited):
    assert reference_edited.status_code == 202
    assert reference_edited.call.args == ("p-1", "c-1", "Add a hat")
