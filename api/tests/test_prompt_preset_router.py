from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.prompt_presets.errors import (
    InvalidPresetError,
    PresetConflictError,
    PresetFileTooLargeError,
    PresetVersionNotFoundError,
    PromptPresetNotFoundError,
)
from app.modules.prompt_presets.models import PresetChange, PromptPreset, PromptPresetVersion
from app.modules.prompt_presets.preset_files import PresetDraft
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    preset_prompts_to_prompts_by_key,
)
from app.modules.prompt_presets.router import build_attachment_disposition
from app.modules.prompt_presets.service import (
    PresetExport,
    PromptPresetDetail,
    PromptPresetService,
)

PRESET_ID = "preset-1"
CREATED_AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
PROMPTS_JSON = {
    key.value: text
    for key, text in preset_prompts_to_prompts_by_key(DEFAULT_PRESET_PROMPTS).items()
}


def build_preset() -> PromptPreset:
    return PromptPreset(
        id=PRESET_ID,
        name="Anime",
        is_system=False,
        is_default=True,
        current_version=3,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def build_version() -> PromptPresetVersion:
    return PromptPresetVersion(
        id="version-2",
        preset_id=PRESET_ID,
        version=2,
        change=PresetChange.RESTORED,
        change_source="v1",
        video_to_markdown=DEFAULT_PRESET_PROMPTS.video_to_markdown,
        character_image=DEFAULT_PRESET_PROMPTS.character_image,
        character_voice=DEFAULT_PRESET_PROMPTS.character_voice,
        scene=DEFAULT_PRESET_PROMPTS.scene,
        created_at=CREATED_AT,
    )


DETAIL = PromptPresetDetail(preset=build_preset(), prompts=DEFAULT_PRESET_PROMPTS)


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


@pytest.fixture
def preset_service():
    service = MagicMock(spec=PromptPresetService)
    service.list_presets.return_value = [build_preset()]
    for method in (
        service.create_preset,
        service.get_preset_detail,
        service.save_preset,
        service.duplicate_preset,
        service.restore_version,
        service.import_preset,
    ):
        method.return_value = DETAIL
    service.mark_default_preset.return_value = build_preset()
    service.list_versions.return_value = [build_version()]
    service.get_version.return_value = build_version()
    service.export_preset.return_value = PresetExport(
        filename="Phim hoạt hình.preset.json", content='{"name": "Phim hoạt hình"}'
    )
    return service


@pytest.fixture
def client(preset_service):
    app = create_app()
    app.state.container = SimpleNamespace(prompt_preset_service=preset_service)
    return TestClient(app)


@pytest.fixture
def list_response(client):
    return client.get("/prompt-presets")


@pytest.fixture
def create_response(client):
    return client.post("/prompt-presets", json={"name": "Anime"})


@pytest.fixture
def defaults_response(client):
    return client.get("/prompt-presets/defaults")


@pytest.fixture
def save_response(client):
    return client.put(
        f"/prompt-presets/{PRESET_ID}", json={"name": "Anime", "prompts": PROMPTS_JSON}
    )


@pytest.fixture
def save_missing_prompt_response(client):
    prompts = {key: text for key, text in PROMPTS_JSON.items() if key != "scene"}
    return client.put(f"/prompt-presets/{PRESET_ID}", json={"name": "Anime", "prompts": prompts})


@pytest.fixture
def delete_response(client):
    return client.delete(f"/prompt-presets/{PRESET_ID}")


@pytest.fixture
def mark_default_response(client):
    return client.post(f"/prompt-presets/{PRESET_ID}/default")


@pytest.fixture
def duplicate_response(client):
    return client.post(f"/prompt-presets/{PRESET_ID}/duplicate")


@pytest.fixture
def versions_response(client):
    return client.get(f"/prompt-presets/{PRESET_ID}/versions")


@pytest.fixture
def version_response(client):
    return client.get(f"/prompt-presets/{PRESET_ID}/versions/2")


@pytest.fixture
def restore_response(client):
    return client.post(f"/prompt-presets/{PRESET_ID}/versions/1/restore")


@pytest.fixture
def export_response(client):
    return client.get(f"/prompt-presets/{PRESET_ID}/export")


@pytest.fixture
def import_response(client):
    files = {"file": ("Anime.preset.json", b"{}", "application/json")}
    return client.post("/prompt-presets/import", files=files)


@pytest.fixture
def imported_filename(preset_service, import_response):
    return preset_service.import_preset.call_args.args[0].filename


@pytest.fixture(
    params=[
        (PromptPresetNotFoundError(PRESET_ID), 404),
        (PresetVersionNotFoundError(PRESET_ID, 1), 404),
        (InvalidPresetError("Not a prompt preset file"), 400),
        (PresetConflictError("The Default preset cannot be deleted"), 409),
        (PresetFileTooLargeError("Preset file exceeds 1 MB"), 413),
    ]
)
def mapped_error(request, client, preset_service):
    error, expected_status = request.param
    preset_service.get_preset_detail.side_effect = error
    response = client.get(f"/prompt-presets/{PRESET_ID}")
    return Outcome(
        actual=(response.status_code, response.json()["detail"]),
        expected=(expected_status, str(error)),
    )


@pytest.fixture
def ascii_disposition():
    return build_attachment_disposition("Anime.preset.json")


def test_list_prompt_presets_answers_camel_case(list_response):
    assert list_response.json() == [
        {
            "id": PRESET_ID,
            "name": "Anime",
            "isSystem": False,
            "isDefault": True,
            "currentVersion": 3,
            "createdAt": "2026-10-11T09:00:00Z",
            "updatedAt": "2026-10-11T09:00:00Z",
        }
    ]


def test_create_prompt_preset_answers_201_with_prompts(create_response, preset_service):
    assert create_response.status_code == 201
    assert create_response.json()["prompts"] == PROMPTS_JSON
    preset_service.create_preset.assert_called_once_with("Anime")


def test_get_prompt_defaults_returns_defaults_and_app_added_parts(defaults_response):
    assert defaults_response.json()["prompts"] == PROMPTS_JSON
    assert (
        "Choose at most {N} key moments"
        in (defaults_response.json()["appAddedParts"]["videoToMarkdown"])
    )


def test_prompt_defaults_tell_voices_apart_and_mark_sounds(defaults_response):
    prompts = defaults_response.json()["prompts"]
    assert "tell its voices apart" in prompts["speakersAndSounds"]
    assert "Mark the sounds that are not speech" in prompts["speakersAndSounds"]
    assert "one entry per distinct voice" in prompts["characterVoice"]
    assert "no speaker labels" not in prompts["characterVoice"]


def test_save_prompt_preset_forwards_a_draft(save_response, preset_service):
    assert save_response.status_code == 200
    preset_service.save_preset.assert_called_once_with(
        PRESET_ID, PresetDraft(name="Anime", prompts=DEFAULT_PRESET_PROMPTS)
    )


def test_save_prompt_preset_answers_422_without_a_prompt(save_missing_prompt_response):
    assert save_missing_prompt_response.status_code == 422


def test_delete_prompt_preset_answers_204(delete_response, preset_service):
    assert delete_response.status_code == 204
    preset_service.delete_preset.assert_called_once_with(PRESET_ID)


def test_mark_default_prompt_preset_returns_the_preset(mark_default_response, preset_service):
    assert mark_default_response.json()["isDefault"] is True
    preset_service.mark_default_preset.assert_called_once_with(PRESET_ID)


def test_duplicate_prompt_preset_answers_201(duplicate_response):
    assert duplicate_response.status_code == 201


def test_list_versions_omits_prompts(versions_response):
    assert versions_response.json() == [
        {
            "version": 2,
            "change": "restored",
            "changeSource": "v1",
            "createdAt": "2026-10-11T09:00:00Z",
        }
    ]


def test_get_version_includes_prompts(version_response, preset_service):
    assert version_response.json()["prompts"] == PROMPTS_JSON
    preset_service.get_version.assert_called_once_with(PRESET_ID, 2)


def test_restore_version_forwards_the_version_number(restore_response, preset_service):
    assert restore_response.status_code == 200
    preset_service.restore_version.assert_called_once_with(PRESET_ID, 1)


def test_export_sends_a_json_attachment_with_an_encoded_name(export_response):
    assert export_response.headers["content-type"] == "application/json"
    assert export_response.headers["content-disposition"] == (
        "attachment; filename*=utf-8''Phim%20ho%E1%BA%A1t%20h%C3%ACnh.preset.json"
    )


def test_import_forwards_the_uploaded_file(import_response, imported_filename):
    assert import_response.status_code == 201
    assert imported_filename == "Anime.preset.json"


def test_preset_errors_map_to_status_codes(mapped_error):
    assert mapped_error.actual == mapped_error.expected


def test_attachment_disposition_quotes_a_plain_ascii_name(ascii_disposition):
    assert ascii_disposition == 'attachment; filename="Anime.preset.json"'
