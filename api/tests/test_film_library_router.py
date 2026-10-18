from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.films.character_service import (
    CharacterChanges,
    CharacterDraft,
    FilmCharacterService,
)
from app.modules.films.errors import (
    CharacterNotFoundError,
    FilmConflictError,
    FilmFileTooLargeError,
    InvalidFilmRequestError,
)
from app.modules.films.http_errors import register_film_error_handlers
from app.modules.films.library_router import router
from app.modules.films.models import (
    Character,
    EntityType,
    MediaStatus,
    ReferenceSource,
    Style,
    VoiceTemplate,
)
from app.modules.films.style_service import FilmStyleService, StyleChanges, StyleDraft
from app.modules.films.views import CharacterDetail, CharacterSummary, ProjectLink
from app.modules.films.voice_service import FilmVoiceService, VoiceChanges

CREATED_AT = datetime.now(UTC)
CHARACTER_BODY = {
    "name": "Captain Bao",
    "entityType": "character",
    "description": "A stocky sea captain",
    "styleId": "realistic",
}
MAI = Character(
    id="c-1",
    name="Mai",
    entity_type=EntityType.CHARACTER,
    description="A young fisher",
    image_prompt="Reference image of a young fisher",
    voice_description=None,
    style_id="realistic",
    reference_status=MediaStatus.DONE,
    reference_source=ReferenceSource.UPLOADED,
    reference_path="characters/c-1/reference.png",
    reference_error=None,
    provider_media=None,
    origin_job_id=None,
    origin_clone_id=None,
    created_at=CREATED_AT,
    updated_at=CREATED_AT,
)
MAI_SUMMARY = CharacterSummary(MAI, "Photorealistic", 1)
NOIR = Style(
    id="noir-1",
    name="Noir",
    is_builtin=False,
    style_instruction="Black and white film noir",
    negative_prompt=None,
    scene_prefix=None,
    lighting="Studio lighting, highly detailed",
)
NARRATOR = VoiceTemplate(
    id="vt-1",
    name="narrator-en",
    description=None,
    sample_path="voices/vt-1/sample.wav",
    sample_text="Solar warning",
    sample_duration_ms=12000,
    consent_path="voices/vt-1/consent.wav",
    provider_voices={"elevenlabs": "el-1"},
    created_at=CREATED_AT,
    updated_at=CREATED_AT,
)


@pytest.fixture
def services():
    characters = MagicMock(spec=FilmCharacterService)
    characters.list_characters.return_value = [MAI_SUMMARY]
    characters.create_character.return_value = MAI_SUMMARY
    characters.get_character.return_value = CharacterDetail(
        summary=MAI_SUMMARY, projects=[ProjectLink(id="p-1", name="Harbor Mysteries")]
    )
    characters.update_character.return_value = MAI_SUMMARY
    characters.upload_reference.return_value = MAI_SUMMARY
    styles = MagicMock(spec=FilmStyleService)
    styles.list_styles.return_value = [NOIR]
    styles.create_style.return_value = NOIR
    styles.update_style.return_value = NOIR
    voices = MagicMock(spec=FilmVoiceService)
    voices.list_voices.return_value = [NARRATOR]
    voices.create_voice.return_value = NARRATOR
    voices.update_voice.return_value = NARRATOR
    voices.upload_consent.return_value = NARRATOR
    return SimpleNamespace(characters=characters, styles=styles, voices=voices)


@pytest.fixture
def client(services):
    app = FastAPI()
    app.include_router(router)
    register_film_error_handlers(app)
    app.state.container = SimpleNamespace(
        film_character_service=services.characters,
        film_style_service=services.styles,
        film_voice_service=services.voices,
    )
    return TestClient(app)


def to_outcome(response, service_method):
    return SimpleNamespace(
        status_code=response.status_code,
        body=response.json() if response.content else None,
        call=service_method.call_args,
    )


@pytest.fixture
def characters_listed(client, services):
    return to_outcome(
        client.get("/films/characters?type=location&q=bao"), services.characters.list_characters
    )


@pytest.fixture
def all_characters_listed(client, services):
    return to_outcome(client.get("/films/characters"), services.characters.list_characters)


@pytest.fixture
def bad_type_response(client):
    return client.get("/films/characters?type=robot")


@pytest.fixture
def character_created(client, services):
    return to_outcome(
        client.post("/films/characters", json=CHARACTER_BODY),
        services.characters.create_character,
    )


@pytest.fixture
def character_rejected(client, services):
    services.characters.create_character.side_effect = InvalidFilmRequestError(
        "Description must be 1-2000 characters"
    )
    return to_outcome(
        client.post("/films/characters", json=CHARACTER_BODY),
        services.characters.create_character,
    )


@pytest.fixture
def character_fetched(client, services):
    return to_outcome(client.get("/films/characters/c-1"), services.characters.get_character)


@pytest.fixture
def missing_character(client, services):
    services.characters.get_character.side_effect = CharacterNotFoundError("c-x")
    return to_outcome(client.get("/films/characters/c-x"), services.characters.get_character)


@pytest.fixture
def character_patched(client, services):
    return to_outcome(
        client.patch(
            "/films/characters/c-1", json={"voiceDescription": None, "description": "New"}
        ),
        services.characters.update_character,
    )


@pytest.fixture
def character_deleted(client, services):
    return to_outcome(client.delete("/films/characters/c-1"), services.characters.delete_character)


@pytest.fixture
def busy_character_delete(client, services):
    services.characters.delete_character.side_effect = FilmConflictError(
        "Character 'Mai' has generation running"
    )
    return to_outcome(client.delete("/films/characters/c-1"), services.characters.delete_character)


@pytest.fixture
def reference_uploaded(client, services):
    outcome = to_outcome(
        client.post(
            "/films/characters/c-1/reference",
            files={"file": ("landscape.png", b"png", "image/png")},
        ),
        services.characters.upload_reference,
    )
    return SimpleNamespace(outcome=outcome, upload=outcome.call.args[1])


@pytest.fixture
def oversized_reference(client, services):
    services.characters.upload_reference.side_effect = FilmFileTooLargeError("Image exceeds 20 MB")
    return to_outcome(
        client.post(
            "/films/characters/c-1/reference",
            files={"file": ("big.png", b"png", "image/png")},
        ),
        services.characters.upload_reference,
    )


@pytest.fixture
def styles_listed(client, services):
    return to_outcome(client.get("/films/styles"), services.styles.list_styles)


@pytest.fixture
def style_created(client, services):
    return to_outcome(
        client.post(
            "/films/styles",
            json={"name": "Noir", "styleInstruction": "Black and white film noir"},
        ),
        services.styles.create_style,
    )


@pytest.fixture
def style_patched(client, services):
    return to_outcome(
        client.patch(
            "/films/styles/noir-1",
            json={"negativePrompt": None, "lighting": None, "name": "Noir 2"},
        ),
        services.styles.update_style,
    )


@pytest.fixture
def style_deleted(client, services):
    return to_outcome(client.delete("/films/styles/noir-1"), services.styles.delete_style)


@pytest.fixture
def voices_listed(client, services):
    return to_outcome(client.get("/films/voices"), services.voices.list_voices)


@pytest.fixture
def voice_created(client, services):
    outcome = to_outcome(
        client.post(
            "/films/voices",
            files={"file": ("voice-sample.wav", b"RIFF", "audio/wav")},
            data={"name": "narrator-auto", "sampleText": "Solar warning", "description": "Calm"},
        ),
        services.voices.create_voice,
    )
    return SimpleNamespace(outcome=outcome, draft=outcome.call.args[0])


@pytest.fixture
def nameless_voice_response(client):
    return client.post("/films/voices", files={"file": ("voice-sample.wav", b"RIFF", "audio/wav")})


@pytest.fixture
def voice_patched(client, services):
    return to_outcome(
        client.patch("/films/voices/vt-1", json={"description": None, "sampleText": "Hi"}),
        services.voices.update_voice,
    )


@pytest.fixture
def voice_deleted(client, services):
    return to_outcome(client.delete("/films/voices/vt-1"), services.voices.delete_voice)


@pytest.fixture
def consent_uploaded(client, services):
    outcome = to_outcome(
        client.post(
            "/films/voices/vt-1/consent",
            files={"file": ("consent.wav", b"RIFF", "audio/wav")},
        ),
        services.voices.upload_consent,
    )
    return SimpleNamespace(outcome=outcome, upload=outcome.call.args[1])


@pytest.fixture
def consent_deleted(client, services):
    return to_outcome(client.delete("/films/voices/vt-1/consent"), services.voices.delete_consent)


def test_characters_list_reads_type_and_query(characters_listed):
    assert characters_listed.status_code == 200
    assert characters_listed.call.args == (EntityType.LOCATION, "bao")
    assert characters_listed.body[0]["projectCount"] == 1
    assert characters_listed.body[0]["providerMedia"] is None


def test_characters_list_without_filters(all_characters_listed):
    assert all_characters_listed.call.args == (None, "")


def test_characters_list_rejects_an_unknown_type(bad_type_response):
    assert bad_type_response.status_code == 422


def test_character_create_answers_201(character_created):
    assert character_created.status_code == 201
    assert character_created.call.args == (
        CharacterDraft(
            name="Captain Bao",
            entity_type=EntityType.CHARACTER,
            description="A stocky sea captain",
            style_id="realistic",
            image_prompt=None,
            voice_description=None,
        ),
    )
    assert character_created.body["styleName"] == "Photorealistic"


def test_character_create_maps_a_bad_request(character_rejected):
    assert character_rejected.status_code == 400
    assert character_rejected.body == {"detail": "Description must be 1-2000 characters"}


def test_character_detail_lists_projects(character_fetched):
    assert character_fetched.status_code == 200
    assert character_fetched.body["projects"] == [{"id": "p-1", "name": "Harbor Mysteries"}]


def test_unknown_character_is_404(missing_character):
    assert missing_character.status_code == 404
    assert missing_character.body == {"detail": "Character c-x not found"}


def test_character_patch_turns_a_sent_null_into_a_cleared_value(character_patched):
    assert character_patched.status_code == 200
    assert character_patched.call.args == (
        "c-1",
        CharacterChanges(description="New", voice_description=""),
    )


def test_character_delete_answers_204(character_deleted):
    assert character_deleted.status_code == 204
    assert character_deleted.call.args == ("c-1",)


def test_character_delete_maps_a_conflict(busy_character_delete):
    assert busy_character_delete.status_code == 409
    assert busy_character_delete.body == {"detail": "Character 'Mai' has generation running"}


def test_reference_upload_passes_the_file(reference_uploaded):
    assert reference_uploaded.outcome.status_code == 200
    assert reference_uploaded.outcome.call.args[0] == "c-1"
    assert reference_uploaded.upload.filename == "landscape.png"
    assert reference_uploaded.outcome.body["referenceSource"] == "uploaded"


def test_reference_upload_maps_too_large(oversized_reference):
    assert oversized_reference.status_code == 413
    assert oversized_reference.body == {"detail": "Image exceeds 20 MB"}


def test_styles_list(styles_listed):
    assert styles_listed.status_code == 200
    assert styles_listed.body[0]["isBuiltin"] is False
    assert styles_listed.body[0]["styleInstruction"] == "Black and white film noir"


def test_style_create_answers_201(style_created):
    assert style_created.status_code == 201
    assert style_created.call.args == (
        StyleDraft(name="Noir", style_instruction="Black and white film noir"),
    )
    assert style_created.body["lighting"] == "Studio lighting, highly detailed"


def test_style_patch_turns_sent_nulls_into_cleared_values(style_patched):
    assert style_patched.status_code == 200
    assert style_patched.call.args == (
        "noir-1",
        StyleChanges(name="Noir 2", negative_prompt="", lighting=""),
    )


def test_style_delete_answers_204(style_deleted):
    assert style_deleted.status_code == 204
    assert style_deleted.call.args == ("noir-1",)


def test_voices_list_shows_provider_copies(voices_listed):
    assert voices_listed.status_code == 200
    assert voices_listed.body[0]["providerVoices"] == {"elevenlabs": "el-1"}
    assert voices_listed.body[0]["consentPath"] == "voices/vt-1/consent.wav"


def test_voice_create_reads_the_form(voice_created):
    assert voice_created.outcome.status_code == 201
    assert voice_created.draft.name == "narrator-auto"
    assert voice_created.draft.sample_text == "Solar warning"
    assert voice_created.draft.description == "Calm"
    assert voice_created.draft.sample.filename == "voice-sample.wav"


def test_voice_create_needs_a_name(nameless_voice_response):
    assert nameless_voice_response.status_code == 422


def test_voice_patch_turns_a_sent_null_into_a_cleared_value(voice_patched):
    assert voice_patched.status_code == 200
    assert voice_patched.call.args == ("vt-1", VoiceChanges(sample_text="Hi", description=""))


def test_voice_delete_answers_204(voice_deleted):
    assert voice_deleted.status_code == 204
    assert voice_deleted.call.args == ("vt-1",)


def test_consent_upload_passes_the_file(consent_uploaded):
    assert consent_uploaded.outcome.status_code == 200
    assert consent_uploaded.outcome.call.args[0] == "vt-1"
    assert consent_uploaded.upload.filename == "consent.wav"


def test_consent_delete_answers_204(consent_deleted):
    assert consent_deleted.status_code == 204
    assert consent_deleted.call.args == ("vt-1",)
