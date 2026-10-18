from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.common.captcha import CaptchaService
from app.main import create_app
from app.modules.ai_models.ai_calls import AiModelChoice
from app.modules.film_clones.clone_actions import CloneActionService
from app.modules.film_clones.clone_activity import AiActivity
from app.modules.film_clones.editing import (
    CloneEditingService,
    LocalizedAssetChanges,
    OriginalAssetChanges,
    SceneChanges,
)
from app.modules.film_clones.errors import (
    CloneActionNotAllowedError,
    CloneFileNotFoundError,
    FilmCloneNotFoundError,
    InvalidCloneRequestError,
)
from app.modules.film_clones.localization_rules import LocalizationChoices
from app.modules.film_clones.models import (
    AssetKind,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.service import (
    CloneDetail,
    CloneOptions,
    CloneSummary,
    FilmCloneService,
)
from app.modules.jobs.errors import InvalidUploadError
from app.modules.jobs.models import Job, JobStatus, JobStep, JobType
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.providers.provider_catalog import MediaKind, ProviderId

CREATED_AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
CAPTCHA_HEADERS = {"X-Captcha-Token": "token-1"}
UPLOAD_FILES = {"file": ("escape.mp4", b"video", "video/mp4")}


def build_summary(job_type: JobType = JobType.FILM_CLONE) -> CloneSummary:
    clone = FilmClone(
        id="clone-1",
        job_id="job-1",
        status=CloneStatus.RUNNING,
        step=CloneStep.ANALYZING,
        error_message=None,
        target_country=None,
        target_setting=None,
        change_appearance=False,
        change_costume=False,
        change_setting=False,
        should_run_automatically=False,
        script_language=None,
        aspect=None,
        script_title=None,
        logline=None,
        preset={"id": "p-1", "name": "Default", "version": 1},
        prompts={"cloneScript": "S"},
        ai_used={"extracting_assets": {"provider": "google", "model": "gemini-3.8-flash"}},
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        finished_at=None,
    )
    job = Job(
        id="job-1",
        type=job_type,
        status=JobStatus.PROCESSING,
        step=JobStep.EXTRACTING_ASSETS,
        source_filename="escape.mp4",
        options={},
        error_message=None,
        created_at=CREATED_AT,
        started_at=None,
        finished_at=None,
    )
    return CloneSummary(clone, job, True)


def build_asset() -> CloneAsset:
    return CloneAsset(
        id="asset-1",
        clone_id="clone-1",
        position=0,
        kind=AssetKind.PROP,
        name="Fan",
        description="A fan",
        culture="Korean",
        period="Joseon dynasty",
        frames=[],
        reference_frame=None,
        changed=True,
        localized_name="Uchiwa",
        localized_description="A paper uchiwa fan",
        localization_note=None,
        reference_status=CloneImageStatus.NONE,
        reference_path=None,
        reference_error=None,
    )


def build_scene() -> CloneScene:
    return CloneScene(
        id="scene-1",
        clone_id="clone-1",
        shot_id="shot-1",
        position=0,
        description="He runs",
        dialogue=None,
        image_prompt="P",
        asset_ids=[],
        image_status=CloneImageStatus.NONE,
        image_path=None,
        image_error=None,
    )


def build_request() -> GenerationRequest:
    return GenerationRequest(
        id="r-1",
        kind=GenerationKind.CLONE_REFERENCE_IMAGE,
        media_kind=MediaKind.IMAGE,
        clone_id="clone-1",
        clone_asset_id="asset-1",
        provider="fal",
        status=GenerationStatus.QUEUED,
        params={"aspect": "9:16"},
        attempts=0,
        created_at=CREATED_AT,
    )


@pytest.fixture
def services():
    clones = MagicMock(spec=FilmCloneService)
    clones.create_from_upload.return_value = build_summary()
    clones.create_from_youtube.return_value = build_summary(JobType.YOUTUBE_FILM_CLONE)
    clones.get_summary.return_value = build_summary()
    clones.get_detail.return_value = CloneDetail(
        summary=build_summary(),
        video_notes="# Notes",
        assets=[build_asset()],
        shots=[],
        scenes=[build_scene()],
        open_requests=[build_request()],
        ai_activity=AiActivity(
            choice=AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash"),
            started_at=CREATED_AT,
            last_output_at=None,
        ),
    )
    editing = MagicMock(spec=CloneEditingService)
    editing.update_localized_asset.return_value = build_asset()
    editing.update_original_asset.return_value = build_asset()
    editing.update_scene.return_value = build_scene()
    editing.generate_reference.return_value = build_request()
    return SimpleNamespace(
        clones=clones, actions=MagicMock(spec=CloneActionService), editing=editing
    )


@pytest.fixture
def captcha_service():
    service = MagicMock(spec=CaptchaService)
    service.verify.return_value = True
    return service


@pytest.fixture
def client(services, captcha_service):
    app = create_app()
    app.state.container = SimpleNamespace(
        film_clone_service=services.clones,
        clone_action_service=services.actions,
        clone_editing_service=services.editing,
        captcha_service=captcha_service,
    )
    return TestClient(app)


@pytest.fixture
def created_response(client):
    return client.post(
        "/film-clones",
        files=UPLOAD_FILES,
        data={"language": "ko", "maxFrames": "30"},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def automatic_created_response(client):
    return client.post(
        "/film-clones",
        files=UPLOAD_FILES,
        data={
            "language": "ko",
            "maxFrames": "30",
            "shouldRunAutomatically": "true",
            "targetCountry": "jp",
            "targetSetting": "a modern Tokyo office district",
            "changeCostume": "true",
        },
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def youtube_response(client):
    return client.post(
        "/film-clones/youtube",
        json={"url": "https://youtu.be/vfjegxHDOwI", "maxFrames": 20},
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def automatic_youtube_response(client):
    return client.post(
        "/film-clones/youtube",
        json={
            "url": "https://youtu.be/vfjegxHDOwI",
            "shouldRunAutomatically": True,
            "changeSetting": True,
            "targetCountry": "vn",
            "targetSetting": "a modern Saigon street",
        },
        headers=CAPTCHA_HEADERS,
    )


@pytest.fixture
def rejected_captcha_response(client, captcha_service):
    captcha_service.verify.return_value = False
    return client.post("/film-clones", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def bad_upload_response(client, services):
    services.clones.create_from_upload.side_effect = InvalidUploadError(
        "Unsupported file type '.txt'"
    )
    return client.post("/film-clones", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def bad_max_frames_response(client, services):
    services.clones.create_from_upload.side_effect = InvalidCloneRequestError(
        "Max frames must be between 10 and 1000"
    )
    return client.post("/film-clones", files=UPLOAD_FILES, headers=CAPTCHA_HEADERS)


@pytest.fixture
def detail_response(client):
    return client.get("/film-clones/clone-1")


@pytest.fixture
def missing_response(client, services):
    services.clones.get_detail.side_effect = FilmCloneNotFoundError("nope")
    return client.get("/film-clones/nope")


@pytest.fixture
def localize_response(client, services):
    return client.post(
        "/film-clones/clone-1/localization",
        json={
            "targetCountry": "vn",
            "targetSetting": "a modern Saigon street",
            "changeAppearance": True,
        },
    )


@pytest.fixture
def step_conflict_response(client, services):
    services.actions.resume.side_effect = CloneActionNotAllowedError(
        "resume", "clone-1", "failed", "analyzing"
    )
    return client.post("/film-clones/clone-1/resume")


@pytest.fixture
def localized_patch_response(client):
    return client.patch(
        "/film-clones/assets/asset-1", json={"changed": True, "localizedDescription": "Fan"}
    )


@pytest.fixture
def original_patch_response(client):
    return client.patch("/film-clones/assets/asset-1", json={"name": "Old Fan", "kind": "prop"})


@pytest.fixture
def cleared_dialogue_response(client):
    return client.patch("/film-clones/scenes/scene-1", json={"dialogue": None})


@pytest.fixture
def reference_response(client):
    return client.post("/film-clones/assets/asset-1/generate-reference")


@pytest.fixture
def missing_file_response(client, services):
    services.clones.resolve_file.side_effect = CloneFileNotFoundError("../secret.txt")
    return client.get("/film-clones/files/clone-1/scenes/missing.png")


def test_create_answers_201_with_the_clone(created_response, services):
    upload, options = services.clones.create_from_upload.call_args.args
    assert created_response.status_code == 201
    assert created_response.json()["sourceKind"] == "upload"
    assert created_response.json()["jobStep"] == "extracting_assets"
    assert created_response.json()["hasOpenRequests"] is True
    assert created_response.json()["shouldRunAutomatically"] is False
    assert created_response.json()["targetSetting"] is None
    assert (upload.filename, upload.language, options.max_frames) == ("escape.mp4", "ko", 30)
    assert options.should_run_automatically is False


def test_create_passes_the_automatic_run_choices(automatic_created_response, services):
    options = services.clones.create_from_upload.call_args.args[1]
    assert automatic_created_response.status_code == 201
    assert options == CloneOptions(
        max_frames=30,
        should_run_automatically=True,
        choices=LocalizationChoices(
            target_country="jp",
            target_setting="a modern Tokyo office district",
            change_appearance=False,
            change_costume=True,
            change_setting=False,
        ),
    )


def test_youtube_create_passes_the_link_and_max_frames(youtube_response, services):
    request, options = services.clones.create_from_youtube.call_args.args
    assert youtube_response.status_code == 201
    assert youtube_response.json()["sourceKind"] == "youtube"
    assert (request.link, request.language, options.max_frames) == (
        "https://youtu.be/vfjegxHDOwI",
        "auto",
        20,
    )


def test_youtube_create_passes_the_automatic_run_choices(automatic_youtube_response, services):
    options = services.clones.create_from_youtube.call_args.args[1]
    assert automatic_youtube_response.status_code == 201
    assert options == CloneOptions(
        max_frames=None,
        should_run_automatically=True,
        choices=LocalizationChoices(
            target_country="vn",
            target_setting="a modern Saigon street",
            change_appearance=False,
            change_costume=False,
            change_setting=True,
        ),
    )


def test_create_needs_a_valid_captcha(rejected_captcha_response):
    assert rejected_captcha_response.status_code == 403


def test_upload_checks_answer_400(bad_upload_response, bad_max_frames_response):
    assert bad_upload_response.status_code == 400
    assert bad_max_frames_response.json() == {"detail": "Max frames must be between 10 and 1000"}


def test_detail_carries_notes_assets_scenes_and_requests(detail_response):
    body = detail_response.json()
    assert detail_response.status_code == 200
    assert body["videoNotes"] == "# Notes"
    assert body["assets"][0]["localizedName"] == "Uchiwa"
    assert body["scenes"][0]["imageStatus"] == "none"
    assert body["generationRequests"][0]["cloneAssetId"] == "asset-1"
    assert body["job"]["sourceFilename"] == "escape.mp4"
    assert body["aiActivity"] == {
        "provider": "google",
        "model": "gemini-3.8-flash",
        "label": "Gemini 3.8 Flash",
        "startedAt": "2026-10-11T09:00:00Z",
        "lastOutputAt": None,
    }


def test_detail_labels_each_ai_used_entry(detail_response):
    assert detail_response.json()["aiUsed"] == {
        "extracting_assets": {
            "provider": "google",
            "model": "gemini-3.8-flash",
            "label": "Gemini 3.8 Flash",
        }
    }


def test_unknown_clone_answers_404(missing_response):
    assert missing_response.status_code == 404
    assert missing_response.json() == {"detail": "Film clone nope not found"}


def test_localize_passes_the_choices(localize_response, services):
    assert localize_response.status_code == 200
    services.actions.localize.assert_called_once_with(
        "clone-1",
        LocalizationChoices(
            target_country="vn",
            target_setting="a modern Saigon street",
            change_appearance=True,
            change_costume=False,
            change_setting=False,
        ),
    )


def test_action_at_the_wrong_step_answers_409(step_conflict_response):
    assert step_conflict_response.status_code == 409
    assert step_conflict_response.json() == {
        "detail": "Cannot resume clone clone-1 while it is failed at analyzing"
    }


def test_localized_fields_go_to_the_review_edit(localized_patch_response, services):
    assert localized_patch_response.status_code == 200
    services.editing.update_localized_asset.assert_called_once_with(
        "asset-1", LocalizedAssetChanges(changed=True, localized_description="Fan")
    )
    services.editing.update_original_asset.assert_not_called()


def test_original_fields_go_to_the_asset_edit(original_patch_response, services):
    services.editing.update_original_asset.assert_called_once_with(
        "asset-1", OriginalAssetChanges(name="Old Fan", kind=AssetKind.PROP)
    )


def test_null_dialogue_clears_it(cleared_dialogue_response, services):
    services.editing.update_scene.assert_called_once_with("scene-1", SceneChanges(dialogue=""))


def test_generate_reference_answers_202_with_the_request(reference_response):
    assert reference_response.status_code == 202
    assert reference_response.json()["kind"] == "clone_reference_image"
    assert reference_response.json()["status"] == "queued"


def test_missing_clone_file_answers_404(missing_file_response):
    assert missing_file_response.status_code == 404
