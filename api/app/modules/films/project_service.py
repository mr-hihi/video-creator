from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import uuid4

from app.db import utc_now
from app.modules.films.character_service import ensure_reference_idle
from app.modules.films.errors import FilmConflictError, InvalidFilmRequestError
from app.modules.films.field_rules import (
    keep_value,
    to_bounded_text,
    to_optional_text,
    to_valid_changes,
    to_valid_values,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_summaries import FilmSummaries
from app.modules.films.media_queue import FilmMediaQueue
from app.modules.films.models import (
    MISSING_MEDIA_STATUSES,
    Character,
    EpisodeStep,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    ProjectStatus,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.story_rules import to_valid_story_bible
from app.modules.films.style_service import get_known_style
from app.modules.films.views import EpisodeSummary, ProjectDetail, ProjectSummary
from app.modules.media_generation.models import GenerationRequest

PROJECT_NAME_LIMIT = 100
PROJECT_DESCRIPTION_LIMIT = 5000
EDIT_PROMPT_LIMIT = 2000
CLIP_DURATIONS_S = frozenset({4, 6, 8, 10, 15, 20, 30})
NEW_PROJECT_EPISODE_NUMBER = 0
LOOK_FIELDS = ("orientation", "style_id")
PROJECT_NAME_MESSAGE = f"Project name must be 1-{PROJECT_NAME_LIMIT} characters"
PROJECT_DESCRIPTION_MESSAGE = f"Description must be at most {PROJECT_DESCRIPTION_LIMIT} characters"
EDIT_PROMPT_MESSAGE = f"Edit prompt must be 1-{EDIT_PROMPT_LIMIT} characters"
CLIP_DURATION_MESSAGE = "Clip length must be 4, 6, 8, 10, 15, 20 or 30 seconds"
DUPLICATE_PROJECT_MESSAGE = "A project named '{name}' already exists"
UNKNOWN_VOICE_MESSAGE = "Voice {voice_id} not found"
UNKNOWN_CHARACTER_MESSAGE = "Character {character_id} not found"
LOOK_FIXED_MESSAGE = "Orientation and style are fixed once a scene image exists"
PROJECT_GENERATION_RUNNING_MESSAGE = "Film project {project_id} has generation running"
CHARACTER_IN_SCENES_MESSAGE = "Character '{name}' appears in {count} scene(s) of this project"
CHARACTER_NOT_IN_PROJECT_MESSAGE = "Character '{name}' is not in this project"
NO_REFERENCE_MESSAGE = "Character '{name}' has no reference image to edit"
STORY_BIBLE_BUSY_MESSAGE = (
    "Episode {number} is updating the story bible — try again when it finishes"
)


def to_valid_clip_duration(clip_duration_s: int) -> int:
    if clip_duration_s not in CLIP_DURATIONS_S:
        raise InvalidFilmRequestError(CLIP_DURATION_MESSAGE)
    return clip_duration_s


PROJECT_FIELD_RULES = {
    "description": partial(
        to_optional_text, limit=PROJECT_DESCRIPTION_LIMIT, message=PROJECT_DESCRIPTION_MESSAGE
    ),
    "language": keep_value,
    "orientation": keep_value,
    "clip_duration_s": to_valid_clip_duration,
    "allow_dialogue": keep_value,
    "allow_narration": keep_value,
    "allow_music": keep_value,
}


@dataclass(frozen=True)
class ProjectDraft:
    name: str
    language: FilmLanguage
    orientation: Orientation
    style_id: str
    clip_duration_s: int
    allow_dialogue: bool
    allow_narration: bool
    allow_music: bool
    description: str | None = None
    narrator_voice_id: str | None = None
    character_ids: Sequence[str] = ()


@dataclass(frozen=True)
class ProjectChanges:
    name: str | None = None
    description: str | None = None
    language: FilmLanguage | None = None
    orientation: Orientation | None = None
    style_id: str | None = None
    clip_duration_s: int | None = None
    allow_dialogue: bool | None = None
    allow_narration: bool | None = None
    narrator_voice_id: str | None = None
    allow_music: bool | None = None
    story_bible: str | None = None


@dataclass(frozen=True)
class FilmProjectTools:
    repository: FilmRepository
    files: FilmFiles
    media_queue: FilmMediaQueue


class FilmProjectService:
    def __init__(self, tools: FilmProjectTools):
        self._repository = tools.repository
        self._files = tools.files
        self._media_queue = tools.media_queue
        self._access = FilmAccess(tools.repository)
        self._summaries = FilmSummaries(tools.repository)

    def list_projects(self, status: ProjectStatus) -> list[ProjectSummary]:
        return self._summaries.summarize_projects(self._repository.find_projects(status))

    def get_project(self, project_id: str) -> ProjectDetail:
        project = self._access.get_project(project_id)
        style = get_known_style(self._repository, project.style_id)
        characters = self._repository.find_project_characters(project.id)
        episodes = self._repository.find_episodes(project.id)
        return ProjectDetail(
            summary=ProjectSummary(project, style.name, len(episodes)),
            characters=self._summaries.summarize_characters(characters),
            episodes=[EpisodeSummary(episode) for episode in episodes],
            is_look_fixed=self._repository.has_scene_image(project.id),
            open_requests=self._repository.find_open_requests_for_characters(
                [character.id for character in characters]
            ),
        )

    def create_project(self, draft: ProjectDraft) -> ProjectDetail:
        project_id = str(uuid4())
        name = self._to_free_name(draft.name, project_id)
        values = to_valid_values(draft, PROJECT_FIELD_RULES)
        style = get_known_style(self._repository, draft.style_id)
        project = FilmProject(
            id=project_id,
            name=name,
            style_id=style.id,
            narrator_voice_id=self._to_known_voice_id(draft.narrator_voice_id),
            status=ProjectStatus.ACTIVE,
            last_episode_number=NEW_PROJECT_EPISODE_NUMBER,
            flow_project_id=None,
            **values,
        )
        self._repository.add_project(project, self._to_known_character_ids(draft.character_ids))
        return self.get_project(project_id)

    def update_project(self, project_id: str, changes: ProjectChanges) -> ProjectDetail:
        project = self._access.get_active_project(project_id)
        values: dict[str, Any] = to_valid_changes(changes, PROJECT_FIELD_RULES)
        if changes.name is not None:
            values["name"] = self._to_free_name(changes.name, project.id)
        if changes.style_id is not None:
            values["style_id"] = get_known_style(self._repository, changes.style_id).id
        if changes.narrator_voice_id is not None:
            values["narrator_voice_id"] = self._to_known_voice_id(changes.narrator_voice_id)
        if changes.story_bible is not None:
            values.update(self._to_story_bible_values(project, changes.story_bible))
        self._ensure_look_editable(project, values)
        if values:
            self._repository.update_project(project.id, values)
        return self.get_project(project.id)

    def archive_project(self, project_id: str) -> ProjectSummary:
        project = self._access.get_project(project_id)
        self._ensure_no_generation(project)
        return self._change_status(project, ProjectStatus.ARCHIVED)

    def unarchive_project(self, project_id: str) -> ProjectSummary:
        return self._change_status(self._access.get_project(project_id), ProjectStatus.ACTIVE)

    def delete_project(self, project_id: str) -> None:
        project = self._access.get_project(project_id)
        self._ensure_no_generation(project)
        self._repository.delete_project(project.id)
        self._files.delete_dir(self._files.project_dir(project.id))

    def link_character(self, project_id: str, character_id: str) -> None:
        project = self._access.get_active_project(project_id)
        character = self._access.get_character(character_id)
        self._repository.link_character(project.id, character.id)

    def unlink_character(self, project_id: str, character_id: str) -> None:
        project = self._access.get_active_project(project_id)
        character = self._access.get_character(character_id)
        scene_count = sum(
            1
            for scene in self._repository.find_project_scenes(project.id)
            if character.id in scene.character_ids
        )
        if scene_count > 0:
            raise FilmConflictError(
                CHARACTER_IN_SCENES_MESSAGE.format(name=character.name, count=scene_count)
            )
        self._repository.unlink_character(project.id, character.id)

    def generate_reference(self, project_id: str, character_id: str) -> GenerationRequest:
        project = self._access.get_active_project(project_id)
        character = self._access.get_character(character_id)
        self._ensure_linked(project, character)
        ensure_reference_idle(self._repository, character)
        return self._media_queue.queue_character_image(project, character)

    def edit_reference(self, project_id: str, character_id: str, prompt: str) -> GenerationRequest:
        project = self._access.get_active_project(project_id)
        character = self._access.get_character(character_id)
        edit_prompt = to_bounded_text(prompt, EDIT_PROMPT_LIMIT, EDIT_PROMPT_MESSAGE)
        self._ensure_linked(project, character)
        ensure_reference_idle(self._repository, character)
        if character.reference_status is not MediaStatus.DONE:
            raise FilmConflictError(NO_REFERENCE_MESSAGE.format(name=character.name))
        return self._media_queue.queue_character_edit(project, character, edit_prompt)

    def generate_missing_references(self, project_id: str) -> list[GenerationRequest]:
        project = self._access.get_active_project(project_id)
        return [
            self._media_queue.queue_character_image(project, character)
            for character in self._repository.find_project_characters(project.id)
            if character.reference_status in MISSING_MEDIA_STATUSES
        ]

    def _change_status(self, project: FilmProject, status: ProjectStatus) -> ProjectSummary:
        self._repository.update_project(project.id, {"status": status})
        changed = self._access.get_project(project.id)
        return self._summaries.summarize_projects([changed])[0]

    def _ensure_no_generation(self, project: FilmProject) -> None:
        if self._repository.find_open_requests_for_project(project.id):
            raise FilmConflictError(
                PROJECT_GENERATION_RUNNING_MESSAGE.format(project_id=project.id)
            )

    def _to_story_bible_values(self, project: FilmProject, story_bible: str) -> dict[str, Any]:
        valid_story_bible = to_valid_story_bible(story_bible)
        updating_episodes = [
            episode
            for episode in self._repository.find_running_episodes_of_project(project.id)
            if episode.step is EpisodeStep.UPDATING_STORY_BIBLE
        ]
        if updating_episodes:
            raise FilmConflictError(
                STORY_BIBLE_BUSY_MESSAGE.format(number=updating_episodes[0].number)
            )
        return {
            "story_bible": valid_story_bible,
            "story_bible_episode_id": None,
            "story_bible_updated_at": utc_now(),
        }

    def _ensure_look_editable(self, project: FilmProject, values: dict[str, Any]) -> None:
        is_look_changed = any(
            values.get(field, getattr(project, field)) != getattr(project, field)
            for field in LOOK_FIELDS
        )
        if is_look_changed and self._repository.has_scene_image(project.id):
            raise FilmConflictError(LOOK_FIXED_MESSAGE)

    def _ensure_linked(self, project: FilmProject, character: Character) -> None:
        if not self._repository.is_linked(project.id, character.id):
            raise FilmConflictError(CHARACTER_NOT_IN_PROJECT_MESSAGE.format(name=character.name))

    def _to_free_name(self, requested_name: str, own_project_id: str) -> str:
        name = to_bounded_text(requested_name, PROJECT_NAME_LIMIT, PROJECT_NAME_MESSAGE)
        existing = self._repository.find_project_by_name(name)
        if existing is not None and existing.id != own_project_id:
            raise FilmConflictError(DUPLICATE_PROJECT_MESSAGE.format(name=name))
        return name

    def _to_known_voice_id(self, voice_id: str | None) -> str | None:
        if not voice_id:
            return None
        if self._repository.find_voice(voice_id) is None:
            raise InvalidFilmRequestError(UNKNOWN_VOICE_MESSAGE.format(voice_id=voice_id))
        return voice_id

    def _to_known_character_ids(self, character_ids: Sequence[str]) -> list[str]:
        unique_ids = list(dict.fromkeys(character_ids))
        characters_by_id = self._repository.find_characters_by_ids(unique_ids)
        missing_ids = [
            character_id for character_id in unique_ids if character_id not in characters_by_id
        ]
        if missing_ids:
            raise InvalidFilmRequestError(
                UNKNOWN_CHARACTER_MESSAGE.format(character_id=missing_ids[0])
            )
        return unique_ids
