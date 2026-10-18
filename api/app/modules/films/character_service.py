from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import uuid4

from app.modules.films.errors import FilmConflictError
from app.modules.films.field_rules import (
    to_bounded_text,
    to_optional_text,
    to_valid_changes,
    to_valid_values,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_prompts import build_character_image_prompt
from app.modules.films.film_summaries import FilmSummaries
from app.modules.films.models import Character, EntityType, MediaStatus, ReferenceSource
from app.modules.films.repository import FilmRepository
from app.modules.films.style_service import get_known_style
from app.modules.films.upload_rules import (
    IMAGE_UPLOAD,
    FileUpload,
    build_too_large_message,
    to_upload_extension,
)
from app.modules.films.views import CharacterDetail, CharacterSummary, ProjectLink

CHARACTER_NAME_LIMIT = 100
CHARACTER_DESCRIPTION_LIMIT = 2000
IMAGE_PROMPT_LIMIT = 4000
VOICE_DESCRIPTION_LIMIT = 300
CHARACTER_NAME_MESSAGE = f"Character name must be 1-{CHARACTER_NAME_LIMIT} characters"
CHARACTER_DESCRIPTION_MESSAGE = f"Description must be 1-{CHARACTER_DESCRIPTION_LIMIT} characters"
IMAGE_PROMPT_MESSAGE = f"Image prompt must be 1-{IMAGE_PROMPT_LIMIT} characters"
VOICE_DESCRIPTION_MESSAGE = (
    f"Voice description must be at most {VOICE_DESCRIPTION_LIMIT} characters"
)
DUPLICATE_CHARACTER_MESSAGE = "A character named '{name}' already exists"
CHARACTER_IN_USE_MESSAGE = "Character '{name}' is used by {count} project(s)"
GENERATION_RUNNING_MESSAGE = "Character '{name}' has generation running"
NEW_CHARACTER_PROJECT_COUNT = 0
UPLOADED_REFERENCE_VALUES = {
    "reference_status": MediaStatus.DONE,
    "reference_source": ReferenceSource.UPLOADED,
    "reference_error": None,
    "provider_media": None,
}

CHARACTER_TEXT_RULES = {
    "description": partial(
        to_bounded_text, limit=CHARACTER_DESCRIPTION_LIMIT, message=CHARACTER_DESCRIPTION_MESSAGE
    ),
    "voice_description": partial(
        to_optional_text, limit=VOICE_DESCRIPTION_LIMIT, message=VOICE_DESCRIPTION_MESSAGE
    ),
}
CHARACTER_CHANGE_RULES = {
    **CHARACTER_TEXT_RULES,
    "image_prompt": partial(
        to_bounded_text, limit=IMAGE_PROMPT_LIMIT, message=IMAGE_PROMPT_MESSAGE
    ),
}


@dataclass(frozen=True)
class CharacterDraft:
    name: str
    entity_type: EntityType
    description: str
    style_id: str
    image_prompt: str | None = None
    voice_description: str | None = None


@dataclass(frozen=True)
class CharacterChanges:
    name: str | None = None
    entity_type: EntityType | None = None
    description: str | None = None
    image_prompt: str | None = None
    voice_description: str | None = None
    style_id: str | None = None


class FilmCharacterService:
    def __init__(self, repository: FilmRepository, files: FilmFiles):
        self._repository = repository
        self._files = files
        self._access = FilmAccess(repository)
        self._summaries = FilmSummaries(repository)

    def list_characters(
        self, entity_type: EntityType | None, name_query: str
    ) -> list[CharacterSummary]:
        characters = self._repository.find_characters(entity_type, name_query.strip())
        return self._summaries.summarize_characters(characters)

    def get_character(self, character_id: str) -> CharacterDetail:
        character = self._access.get_character(character_id)
        projects = self._repository.find_projects_of_character(character.id)
        style = get_known_style(self._repository, character.style_id)
        return CharacterDetail(
            summary=CharacterSummary(character, style.name, len(projects)),
            projects=[ProjectLink(id=project.id, name=project.name) for project in projects],
        )

    def create_character(self, draft: CharacterDraft) -> CharacterSummary:
        character_id = str(uuid4())
        name = self._to_free_name(draft.name, character_id)
        values = to_valid_values(draft, CHARACTER_TEXT_RULES)
        style = get_known_style(self._repository, draft.style_id)
        image_prompt = to_optional_text(
            draft.image_prompt, IMAGE_PROMPT_LIMIT, IMAGE_PROMPT_MESSAGE
        ) or build_character_image_prompt(values["description"], draft.entity_type, style)
        character = Character(
            id=character_id,
            name=name,
            entity_type=draft.entity_type,
            image_prompt=image_prompt,
            style_id=style.id,
            reference_status=MediaStatus.NONE,
            **values,
        )
        added = self._repository.add_character(character)
        return CharacterSummary(added, style.name, NEW_CHARACTER_PROJECT_COUNT)

    def update_character(self, character_id: str, changes: CharacterChanges) -> CharacterSummary:
        character = self._access.get_character(character_id)
        values: dict[str, Any] = to_valid_changes(changes, CHARACTER_CHANGE_RULES)
        if changes.name is not None:
            values["name"] = self._to_free_name(changes.name, character.id)
        if changes.entity_type is not None:
            values["entity_type"] = changes.entity_type
        if changes.style_id is not None:
            values["style_id"] = get_known_style(self._repository, changes.style_id).id
        if values:
            self._repository.update_character(character.id, values)
        return self._summarize(character.id)

    def delete_character(self, character_id: str) -> None:
        character = self._access.get_character(character_id)
        project_counts_by_id = self._repository.count_projects_by_character([character.id])
        project_count = project_counts_by_id.get(character.id, 0)
        if project_count > 0:
            raise FilmConflictError(
                CHARACTER_IN_USE_MESSAGE.format(name=character.name, count=project_count)
            )
        ensure_reference_idle(self._repository, character)
        self._repository.delete_character(character.id)
        self._files.delete_dir(self._files.character_dir(character.id))

    def upload_reference(self, character_id: str, upload: FileUpload) -> CharacterSummary:
        character = self._access.get_character(character_id)
        extension = to_upload_extension(upload.filename, IMAGE_UPLOAD)
        ensure_reference_idle(self._repository, character)
        reference_path = self._files.save_upload(
            upload.stream,
            self._files.character_reference_path(character.id, extension),
            build_too_large_message(IMAGE_UPLOAD, self._files.max_upload_mb),
        )
        self._repository.update_character(
            character.id,
            {
                **UPLOADED_REFERENCE_VALUES,
                "reference_path": self._files.to_relative(reference_path),
            },
        )
        return self._summarize(character.id)

    def _summarize(self, character_id: str) -> CharacterSummary:
        character = self._access.get_character(character_id)
        return self._summaries.summarize_characters([character])[0]

    def _to_free_name(self, requested_name: str, own_character_id: str) -> str:
        name = to_bounded_text(requested_name, CHARACTER_NAME_LIMIT, CHARACTER_NAME_MESSAGE)
        existing = self._repository.find_character_by_name(name)
        if existing is not None and existing.id != own_character_id:
            raise FilmConflictError(DUPLICATE_CHARACTER_MESSAGE.format(name=name))
        return name


def ensure_reference_idle(repository: FilmRepository, character: Character) -> None:
    if repository.find_open_requests_for_character(character.id):
        raise FilmConflictError(GENERATION_RUNNING_MESSAGE.format(name=character.name))
