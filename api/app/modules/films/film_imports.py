from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.modules.films.film_files import FilmFiles
from app.modules.films.film_prompts import build_character_image_prompt
from app.modules.films.models import Character, EntityType, MediaStatus, ReferenceSource, Style

DEFAULT_IMAGE_EXTENSION = "jpg"


@dataclass(frozen=True)
class FileCopy:
    source: Path
    destination: Path


@dataclass(frozen=True)
class ReferenceFile:
    path: Path
    source: ReferenceSource


@dataclass(frozen=True)
class CharacterSeed:
    id: str
    name: str
    entity_type: EntityType
    description: str
    voice_description: str | None
    style: Style
    reference: ReferenceFile | None
    origin_job_id: str | None = None
    origin_clone_id: str | None = None


@dataclass(frozen=True)
class PlannedReference:
    values: dict[str, Any]
    file_copy: FileCopy


@dataclass(frozen=True)
class PlannedCharacter:
    character: Character
    file_copies: tuple[FileCopy, ...]


def to_image_extension(file_path: Path) -> str:
    return file_path.suffix.removeprefix(".").lower() or DEFAULT_IMAGE_EXTENSION


class FilmImports:
    def __init__(self, files: FilmFiles):
        self._files = files

    def plan_reference(self, character_id: str, reference: ReferenceFile) -> PlannedReference:
        destination = self._files.character_reference_path(
            character_id, to_image_extension(reference.path)
        )
        return PlannedReference(
            values={
                "reference_status": MediaStatus.DONE,
                "reference_source": reference.source,
                "reference_path": self._files.to_relative(destination),
                "reference_error": None,
            },
            file_copy=FileCopy(reference.path, destination),
        )

    def plan_character(self, seed: CharacterSeed) -> PlannedCharacter:
        planned = None if seed.reference is None else self.plan_reference(seed.id, seed.reference)
        reference_values = (
            {"reference_status": MediaStatus.NONE} if planned is None else planned.values
        )
        character = Character(
            id=seed.id,
            name=seed.name,
            entity_type=seed.entity_type,
            description=seed.description,
            image_prompt=build_character_image_prompt(
                seed.description, seed.entity_type, seed.style
            ),
            voice_description=seed.voice_description,
            style_id=seed.style.id,
            origin_job_id=seed.origin_job_id,
            origin_clone_id=seed.origin_clone_id,
            **reference_values,
        )
        return PlannedCharacter(character, () if planned is None else (planned.file_copy,))

    def copy_files(self, file_copies: Sequence[FileCopy]) -> None:
        for file_copy in file_copies:
            self._files.copy_into(file_copy.source, file_copy.destination)

    def discard_files(self, file_copies: Sequence[FileCopy]) -> None:
        for file_copy in file_copies:
            file_copy.destination.unlink(missing_ok=True)
