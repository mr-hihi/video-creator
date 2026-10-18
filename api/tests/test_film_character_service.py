import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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
from app.modules.films.film_files import FilmFiles
from app.modules.films.models import (
    Character,
    EntityType,
    FilmProject,
    MediaStatus,
    ReferenceSource,
    Style,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.upload_rules import FileUpload
from app.modules.films.views import ProjectLink
from app.modules.media_generation.models import GenerationRequest

MAX_UPLOAD_MB = 1
INK = Style(
    id="ink",
    name="Ink",
    is_builtin=False,
    style_instruction="Ink drawing.",
    negative_prompt="NOT color.",
    lighting="Soft light",
)
PHOTO = Style(id="realistic", name="Photorealistic", is_builtin=True, style_instruction="R")
HARBOR = FilmProject(id="p-1", name="Harbor Mysteries")


def build_character(**overrides) -> Character:
    fields = {
        "id": "c-1",
        "name": "Mai",
        "entity_type": EntityType.CHARACTER,
        "description": "A young fisher",
        "image_prompt": "Reference image of a young fisher",
        "voice_description": None,
        "style_id": INK.id,
        "reference_status": MediaStatus.NONE,
        "reference_source": None,
        "reference_path": None,
        "provider_media": None,
    }
    return Character(**{**fields, **overrides})


MAI = build_character()
BAO = build_character(id="c-2", name="Captain Bao", style_id=PHOTO.id)


def build_characters(tmp_path, characters=(MAI,), **arrangement):
    characters_by_id = {character.id: character for character in characters}
    styles_by_id = {style.id: style for style in (INK, PHOTO)}
    project_counts_by_id = arrangement.get("project_counts", {})
    repository = MagicMock(spec=FilmRepository)
    repository.find_character.side_effect = characters_by_id.get
    repository.find_character_by_name.side_effect = lambda name: next(
        (item for item in characters if item.name.casefold() == name.casefold()), None
    )
    repository.find_characters.return_value = list(characters)
    repository.add_character.side_effect = lambda character: character
    repository.find_style.side_effect = styles_by_id.get
    repository.find_styles_by_ids.side_effect = lambda ids: {
        style_id: styles_by_id[style_id] for style_id in ids
    }
    repository.count_projects_by_character.side_effect = lambda ids: {
        character_id: project_counts_by_id[character_id]
        for character_id in ids
        if character_id in project_counts_by_id
    }
    repository.find_projects_of_character.return_value = arrangement.get("projects", [])
    repository.find_open_requests_for_character.return_value = arrangement.get("open_requests", [])
    files = FilmFiles(tmp_path, MAX_UPLOAD_MB)
    return SimpleNamespace(
        service=FilmCharacterService(repository, files), repository=repository, files=files
    )


def capture(error_class, call):
    with pytest.raises(error_class) as caught:
        call()
    return caught.value


def build_draft(**overrides) -> CharacterDraft:
    fields = {
        "name": "  Sea Captain  ",
        "entity_type": EntityType.CHARACTER,
        "description": "  A sea captain  ",
        "style_id": INK.id,
    }
    return CharacterDraft(**{**fields, **overrides})


@pytest.fixture
def listed(tmp_path):
    characters = build_characters(tmp_path, [MAI, BAO], project_counts={MAI.id: 2})
    summaries = characters.service.list_characters(EntityType.CHARACTER, "  bao ")
    return SimpleNamespace(summaries=summaries, repository=characters.repository)


@pytest.fixture
def character_detail(tmp_path):
    characters = build_characters(tmp_path, projects=[HARBOR])
    return characters.service.get_character(MAI.id)


@pytest.fixture
def missing_character_error(tmp_path):
    characters = build_characters(tmp_path)
    return capture(CharacterNotFoundError, lambda: characters.service.get_character("c-x"))


@pytest.fixture
def created_with_built_prompt(tmp_path):
    characters = build_characters(tmp_path)
    return characters.service.create_character(
        build_draft(image_prompt="   ", voice_description="   ")
    )


@pytest.fixture
def created_with_typed_prompt(tmp_path):
    characters = build_characters(tmp_path)
    return characters.service.create_character(
        build_draft(
            entity_type=EntityType.LOCATION,
            image_prompt="  A harbor at dawn  ",
            voice_description=" Low, slow voice ",
        )
    )


@pytest.fixture(
    params=[
        (build_draft(name="   "), "Character name must be 1-100 characters"),
        (build_draft(name="n" * 101), "Character name must be 1-100 characters"),
        (build_draft(description="d" * 2001), "Description must be 1-2000 characters"),
        (build_draft(description="  "), "Description must be 1-2000 characters"),
        (build_draft(image_prompt="p" * 4001), "Image prompt must be 1-4000 characters"),
        (
            build_draft(voice_description="v" * 301),
            "Voice description must be at most 300 characters",
        ),
        (build_draft(style_id="no-such-style"), "Style no-such-style not found"),
    ]
)
def invalid_character_outcome(request, tmp_path):
    draft, expected_message = request.param
    characters = build_characters(tmp_path)
    error = capture(InvalidFilmRequestError, lambda: characters.service.create_character(draft))
    return SimpleNamespace(actual=str(error), expected=expected_message)


@pytest.fixture
def duplicate_character_error(tmp_path):
    characters = build_characters(tmp_path)
    return capture(
        FilmConflictError,
        lambda: characters.service.create_character(build_draft(name="mai")),
    )


@pytest.fixture
def updated_character(tmp_path):
    characters = build_characters(tmp_path, project_counts={MAI.id: 1})
    summary = characters.service.update_character(
        MAI.id,
        CharacterChanges(
            name=" MAI ",
            entity_type=EntityType.CREATURE,
            description=" A sea spirit ",
            image_prompt=" Reference image of a sea spirit ",
            voice_description="",
            style_id=PHOTO.id,
        ),
    )
    return SimpleNamespace(
        summary=summary, update_args=characters.repository.update_character.call_args.args
    )


@pytest.fixture
def unchanged_character_repository(tmp_path):
    characters = build_characters(tmp_path)
    characters.service.update_character(MAI.id, CharacterChanges())
    return characters.repository


@pytest.fixture
def blank_image_prompt_error(tmp_path):
    characters = build_characters(tmp_path)
    return capture(
        InvalidFilmRequestError,
        lambda: characters.service.update_character(MAI.id, CharacterChanges(image_prompt=" ")),
    )


@pytest.fixture
def renamed_onto_other_error(tmp_path):
    characters = build_characters(tmp_path, [MAI, BAO])
    return capture(
        FilmConflictError,
        lambda: characters.service.update_character(MAI.id, CharacterChanges(name="captain bao")),
    )


@pytest.fixture
def linked_delete_error(tmp_path):
    characters = build_characters(tmp_path, project_counts={MAI.id: 1})
    return capture(FilmConflictError, lambda: characters.service.delete_character(MAI.id))


@pytest.fixture
def busy_delete_error(tmp_path):
    characters = build_characters(tmp_path, open_requests=[GenerationRequest(id="r-1")])
    return capture(FilmConflictError, lambda: characters.service.delete_character(MAI.id))


@pytest.fixture
def deleted_character(tmp_path):
    characters = build_characters(tmp_path)
    reference_path = characters.files.character_reference_path(MAI.id, "png")
    reference_path.parent.mkdir(parents=True)
    reference_path.write_bytes(b"png")
    characters.service.delete_character(MAI.id)
    return SimpleNamespace(
        repository=characters.repository,
        is_folder_left=characters.files.character_dir(MAI.id).exists(),
    )


@pytest.fixture
def uploaded_reference(tmp_path):
    characters = build_characters(tmp_path)
    old_reference = characters.files.character_reference_path(MAI.id, "jpg")
    old_reference.parent.mkdir(parents=True)
    old_reference.write_bytes(b"old")
    characters.service.upload_reference(MAI.id, FileUpload("Mai.PNG", io.BytesIO(b"new")))
    return SimpleNamespace(
        update_args=characters.repository.update_character.call_args.args,
        stored_bytes=characters.files.character_reference_path(MAI.id, "png").read_bytes(),
        is_old_reference_left=old_reference.exists(),
    )


@pytest.fixture
def unsupported_reference_error(tmp_path):
    characters = build_characters(tmp_path)
    return capture(
        InvalidFilmRequestError,
        lambda: characters.service.upload_reference(
            MAI.id, FileUpload("notes.txt", io.BytesIO(b"x"))
        ),
    )


@pytest.fixture
def oversized_reference_error(tmp_path):
    characters = build_characters(tmp_path)
    oversized = io.BytesIO(b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1))
    return capture(
        FilmFileTooLargeError,
        lambda: characters.service.upload_reference(MAI.id, FileUpload("big.png", oversized)),
    )


@pytest.fixture
def busy_upload_error(tmp_path):
    characters = build_characters(tmp_path, open_requests=[GenerationRequest(id="r-1")])
    return capture(
        FilmConflictError,
        lambda: characters.service.upload_reference(
            MAI.id, FileUpload("mai.png", io.BytesIO(b"x"))
        ),
    )


def test_list_filters_by_type_and_trimmed_query(listed):
    listed.repository.find_characters.assert_called_once_with(EntityType.CHARACTER, "bao")


def test_list_summarizes_style_and_project_count(listed):
    assert listed.summaries[0].style_name == "Ink"
    assert listed.summaries[0].project_count == 2
    assert listed.summaries[1].style_name == "Photorealistic"
    assert listed.summaries[1].project_count == 0


def test_detail_lists_the_linked_projects(character_detail):
    assert character_detail.projects == [ProjectLink(id="p-1", name="Harbor Mysteries")]
    assert character_detail.summary.project_count == 1
    assert character_detail.summary.style_name == "Ink"


def test_unknown_character_is_not_found(missing_character_error):
    assert str(missing_character_error) == "Character c-x not found"


def test_create_builds_the_image_prompt_when_left_blank(created_with_built_prompt):
    assert created_with_built_prompt.character.image_prompt == (
        "Reference image of A sea captain. Ink drawing. NOT color. full body, head to toe, "
        "standing straight, centered, front-facing, neutral background Soft light"
    )
    assert created_with_built_prompt.character.voice_description is None


def test_create_stores_a_new_character_without_reference(created_with_built_prompt):
    assert created_with_built_prompt.character.name == "Sea Captain"
    assert created_with_built_prompt.character.description == "A sea captain"
    assert created_with_built_prompt.character.reference_status is MediaStatus.NONE
    assert created_with_built_prompt.style_name == "Ink"
    assert created_with_built_prompt.project_count == 0


def test_create_keeps_a_typed_image_prompt(created_with_typed_prompt):
    assert created_with_typed_prompt.character.image_prompt == "A harbor at dawn"
    assert created_with_typed_prompt.character.voice_description == "Low, slow voice"
    assert created_with_typed_prompt.character.entity_type is EntityType.LOCATION


def test_create_rejects_invalid_fields(invalid_character_outcome):
    assert invalid_character_outcome.actual == invalid_character_outcome.expected


def test_create_rejects_a_name_taken_in_another_case(duplicate_character_error):
    assert str(duplicate_character_error) == "A character named 'mai' already exists"


def test_update_writes_every_sent_field(updated_character):
    assert updated_character.update_args == (
        "c-1",
        {
            "description": "A sea spirit",
            "voice_description": None,
            "image_prompt": "Reference image of a sea spirit",
            "name": "MAI",
            "entity_type": EntityType.CREATURE,
            "style_id": "realistic",
        },
    )


def test_update_returns_the_summary(updated_character):
    assert updated_character.summary.project_count == 1


def test_update_without_changes_writes_nothing(unchanged_character_repository):
    assert unchanged_character_repository.update_character.called is False


def test_update_rejects_a_blank_image_prompt(blank_image_prompt_error):
    assert str(blank_image_prompt_error) == "Image prompt must be 1-4000 characters"


def test_update_rejects_the_name_of_another_character(renamed_onto_other_error):
    assert str(renamed_onto_other_error) == "A character named 'captain bao' already exists"


def test_delete_refuses_a_linked_character(linked_delete_error):
    assert str(linked_delete_error) == "Character 'Mai' is used by 1 project(s)"


def test_delete_refuses_a_character_with_generation_running(busy_delete_error):
    assert str(busy_delete_error) == "Character 'Mai' has generation running"


def test_delete_removes_the_row_and_its_folder(deleted_character):
    deleted_character.repository.delete_character.assert_called_once_with("c-1")
    assert deleted_character.is_folder_left is False


def test_upload_stores_the_reference_as_uploaded(uploaded_reference):
    assert uploaded_reference.update_args == (
        "c-1",
        {
            "reference_status": MediaStatus.DONE,
            "reference_source": ReferenceSource.UPLOADED,
            "reference_error": None,
            "provider_media": None,
            "reference_path": "characters/c-1/reference.png",
        },
    )


def test_upload_replaces_the_previous_reference_file(uploaded_reference):
    assert uploaded_reference.stored_bytes == b"new"
    assert uploaded_reference.is_old_reference_left is False


def test_upload_rejects_an_unsupported_type(unsupported_reference_error):
    assert str(unsupported_reference_error) == (
        "Unsupported image type '.txt'. Use one of: .jpeg, .jpg, .png, .webp"
    )


def test_upload_rejects_a_file_over_the_limit(oversized_reference_error):
    assert str(oversized_reference_error) == "Image exceeds 1 MB"


def test_upload_refuses_while_generation_runs(busy_upload_error):
    assert str(busy_upload_error) == "Character 'Mai' has generation running"
