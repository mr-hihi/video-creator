from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import utc_now
from app.modules.ai_models.ai_calls import AiModelChoice
from app.modules.ai_models.model_choices import to_model_value
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    EpisodePart,
    EpisodeStatus,
    EpisodeStep,
    FilmProject,
    FilmProjectCharacter,
    ProjectStatus,
    Scene,
    Style,
    VoiceTemplate,
)
from app.modules.media_generation.models import (
    OPEN_GENERATION_STATUSES,
    GenerationKind,
    GenerationRequest,
)


@dataclass(frozen=True)
class OutlineSave:
    episode_values: Mapping[str, Any]
    parts: Sequence[EpisodePart]


@dataclass(frozen=True)
class ScriptSave:
    recap: str | None
    new_characters: Sequence[Character] = ()
    linked_character_ids: Sequence[str] = ()
    character_values_by_id: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    scenes: Sequence[Scene] = ()


@dataclass(frozen=True)
class StoryBibleSave:
    summary: str | None
    story_bible: str


@dataclass(frozen=True)
class EpisodeCreation:
    episode: Episode
    new_characters: Sequence[Character] = ()
    linked_character_ids: Sequence[str] = ()
    parts: Sequence[EpisodePart] = ()
    scenes: Sequence[Scene] = ()


class FilmRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add_project(self, project: FilmProject, character_ids: Collection[str]) -> FilmProject:
        with self._session_factory.begin() as session:
            session.add(project)
            session.flush()
            for character_id in character_ids:
                session.add(FilmProjectCharacter(project_id=project.id, character_id=character_id))
        return project

    def find_project(self, project_id: str) -> FilmProject | None:
        with self._session_factory() as session:
            return session.get(FilmProject, project_id)

    def find_project_by_name(self, name: str) -> FilmProject | None:
        with self._session_factory() as session:
            return session.scalar(
                select(FilmProject).where(func.lower(FilmProject.name) == name.lower())
            )

    def find_projects(self, status: ProjectStatus) -> list[FilmProject]:
        with self._session_factory() as session:
            statement = (
                select(FilmProject)
                .where(FilmProject.status == status)
                .order_by(FilmProject.created_at.desc())
            )
            return list(session.scalars(statement))

    def find_projects_by_ids(self, project_ids: Collection[str]) -> dict[str, FilmProject]:
        with self._session_factory() as session:
            projects = session.scalars(select(FilmProject).where(FilmProject.id.in_(project_ids)))
            return {project.id: project for project in projects}

    def update_project(self, project_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(FilmProject).where(FilmProject.id == project_id).values(**values)
            )

    def delete_project(self, project_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(GenerationRequest).where(GenerationRequest.project_id == project_id)
            )
            episode_ids = select(Episode.id).where(Episode.project_id == project_id)
            session.execute(delete(Scene).where(Scene.episode_id.in_(episode_ids)))
            session.execute(delete(EpisodePart).where(EpisodePart.episode_id.in_(episode_ids)))
            session.execute(delete(Episode).where(Episode.project_id == project_id))
            session.execute(
                delete(FilmProjectCharacter).where(FilmProjectCharacter.project_id == project_id)
            )
            session.execute(delete(FilmProject).where(FilmProject.id == project_id))

    def count_episodes_by_project(self, project_ids: Collection[str]) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(Episode.project_id, func.count())
                .where(Episode.project_id.in_(project_ids))
                .group_by(Episode.project_id)
            )
            return {project_id: count for project_id, count in rows}

    def has_scene_image(self, project_id: str) -> bool:
        with self._session_factory() as session:
            statement = (
                select(Scene.id)
                .join(Episode, Episode.id == Scene.episode_id)
                .where(Episode.project_id == project_id, Scene.image_path.is_not(None))
                .limit(1)
            )
            return session.scalar(statement) is not None

    def add_character(self, character: Character) -> Character:
        with self._session_factory.begin() as session:
            session.add(character)
        return character

    def find_character(self, character_id: str) -> Character | None:
        with self._session_factory() as session:
            return session.get(Character, character_id)

    def find_character_by_name(self, name: str) -> Character | None:
        with self._session_factory() as session:
            return session.scalar(
                select(Character).where(func.lower(Character.name) == name.lower())
            )

    def find_characters(
        self, entity_type: EntityType | None, name_query: str | None
    ) -> list[Character]:
        with self._session_factory() as session:
            statement = select(Character).order_by(Character.name)
            if entity_type is not None:
                statement = statement.where(Character.entity_type == entity_type)
            if name_query:
                statement = statement.where(
                    func.lower(Character.name).contains(name_query.lower(), autoescape=True)
                )
            return list(session.scalars(statement))

    def find_characters_by_ids(self, character_ids: Collection[str]) -> dict[str, Character]:
        with self._session_factory() as session:
            characters = session.scalars(select(Character).where(Character.id.in_(character_ids)))
            return {character.id: character for character in characters}

    def find_project_characters(self, project_id: str) -> list[Character]:
        with self._session_factory() as session:
            statement = (
                select(Character)
                .join(FilmProjectCharacter, FilmProjectCharacter.character_id == Character.id)
                .where(FilmProjectCharacter.project_id == project_id)
                .order_by(FilmProjectCharacter.created_at, Character.name)
            )
            return list(session.scalars(statement))

    def update_character(self, character_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Character).where(Character.id == character_id).values(**values))

    def delete_character(self, character_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(FilmProjectCharacter).where(
                    FilmProjectCharacter.character_id == character_id
                )
            )
            session.execute(delete(Character).where(Character.id == character_id))

    def link_character(self, project_id: str, character_id: str) -> None:
        with self._session_factory.begin() as session:
            if session.get(FilmProjectCharacter, (project_id, character_id)) is None:
                session.add(FilmProjectCharacter(project_id=project_id, character_id=character_id))

    def unlink_character(self, project_id: str, character_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(FilmProjectCharacter).where(
                    FilmProjectCharacter.project_id == project_id,
                    FilmProjectCharacter.character_id == character_id,
                )
            )

    def is_linked(self, project_id: str, character_id: str) -> bool:
        with self._session_factory() as session:
            return session.get(FilmProjectCharacter, (project_id, character_id)) is not None

    def count_projects_by_character(self, character_ids: Collection[str]) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(FilmProjectCharacter.character_id, func.count())
                .where(FilmProjectCharacter.character_id.in_(character_ids))
                .group_by(FilmProjectCharacter.character_id)
            )
            return {character_id: count for character_id, count in rows}

    def find_projects_of_character(self, character_id: str) -> list[FilmProject]:
        with self._session_factory() as session:
            statement = (
                select(FilmProject)
                .join(FilmProjectCharacter, FilmProjectCharacter.project_id == FilmProject.id)
                .where(FilmProjectCharacter.character_id == character_id)
                .order_by(FilmProject.name)
            )
            return list(session.scalars(statement))

    def find_project_scenes(self, project_id: str) -> list[Scene]:
        with self._session_factory() as session:
            statement = (
                select(Scene)
                .join(Episode, Episode.id == Scene.episode_id)
                .where(Episode.project_id == project_id)
            )
            return list(session.scalars(statement))

    def add_missing_styles(self, styles: Sequence[Style]) -> None:
        with self._session_factory.begin() as session:
            existing_ids = set(session.scalars(select(Style.id)))
            for style in styles:
                if style.id not in existing_ids:
                    session.add(style)

    def add_style(self, style: Style) -> Style:
        with self._session_factory.begin() as session:
            session.add(style)
        return style

    def find_style(self, style_id: str) -> Style | None:
        with self._session_factory() as session:
            return session.get(Style, style_id)

    def find_style_by_name(self, name: str) -> Style | None:
        with self._session_factory() as session:
            return session.scalar(select(Style).where(func.lower(Style.name) == name.lower()))

    def find_styles(self) -> list[Style]:
        with self._session_factory() as session:
            statement = select(Style).order_by(Style.is_builtin.desc(), Style.name)
            return list(session.scalars(statement))

    def find_styles_by_ids(self, style_ids: Collection[str]) -> dict[str, Style]:
        with self._session_factory() as session:
            styles = session.scalars(select(Style).where(Style.id.in_(style_ids)))
            return {style.id: style for style in styles}

    def update_style(self, style_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Style).where(Style.id == style_id).values(**values))

    def delete_style(self, style_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(Style).where(Style.id == style_id))

    def count_style_usage(self, style_id: str) -> tuple[int, int]:
        with self._session_factory() as session:
            project_count = session.scalar(
                select(func.count())
                .select_from(FilmProject)
                .where(FilmProject.style_id == style_id)
            )
            character_count = session.scalar(
                select(func.count()).select_from(Character).where(Character.style_id == style_id)
            )
            return project_count or 0, character_count or 0

    def add_voice(self, voice: VoiceTemplate) -> VoiceTemplate:
        with self._session_factory.begin() as session:
            session.add(voice)
        return voice

    def find_voice(self, voice_id: str) -> VoiceTemplate | None:
        with self._session_factory() as session:
            return session.get(VoiceTemplate, voice_id)

    def find_voice_by_name(self, name: str) -> VoiceTemplate | None:
        with self._session_factory() as session:
            return session.scalar(
                select(VoiceTemplate).where(func.lower(VoiceTemplate.name) == name.lower())
            )

    def find_voices(self) -> list[VoiceTemplate]:
        with self._session_factory() as session:
            return list(session.scalars(select(VoiceTemplate).order_by(VoiceTemplate.name)))

    def update_voice(self, voice_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(VoiceTemplate).where(VoiceTemplate.id == voice_id).values(**values)
            )

    def delete_voice(self, voice_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(VoiceTemplate).where(VoiceTemplate.id == voice_id))

    def count_projects_with_narrator(self, voice_id: str) -> int:
        with self._session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(FilmProject)
                .where(FilmProject.narrator_voice_id == voice_id)
            )
            return count or 0

    def add_episode(self, creation: EpisodeCreation) -> Episode:
        episode = creation.episode
        with self._session_factory.begin() as session:
            project = session.get(FilmProject, episode.project_id, with_for_update=True)
            if project is None:
                raise LookupError(episode.project_id)
            episode.number = project.last_episode_number + 1
            project.last_episode_number = episode.number
            for character in creation.new_characters:
                session.add(character)
            session.flush()
            for character_id in creation.linked_character_ids:
                if session.get(FilmProjectCharacter, (project.id, character_id)) is None:
                    session.add(
                        FilmProjectCharacter(project_id=project.id, character_id=character_id)
                    )
            session.add(episode)
            session.flush()
            for part in creation.parts:
                session.add(part)
            session.flush()
            for scene in creation.scenes:
                session.add(scene)
        return episode

    def find_episode(self, episode_id: str) -> Episode | None:
        with self._session_factory() as session:
            return session.get(Episode, episode_id)

    def find_episodes(self, project_id: str) -> list[Episode]:
        with self._session_factory() as session:
            statement = (
                select(Episode).where(Episode.project_id == project_id).order_by(Episode.number)
            )
            return list(session.scalars(statement))

    def find_running_episodes(self, steps: Collection[EpisodeStep]) -> list[Episode]:
        with self._session_factory() as session:
            statement = (
                select(Episode)
                .where(Episode.status == EpisodeStatus.RUNNING, Episode.step.in_(steps))
                .order_by(Episode.updated_at)
            )
            return list(session.scalars(statement))

    def find_running_episodes_of_project(self, project_id: str) -> list[Episode]:
        with self._session_factory() as session:
            statement = select(Episode).where(
                Episode.project_id == project_id, Episode.status == EpisodeStatus.RUNNING
            )
            return list(session.scalars(statement))

    def update_episode(self, episode_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Episode).where(Episode.id == episode_id).values(**values))

    def save_ai_used(self, episode_id: str, step: EpisodeStep, choice: AiModelChoice) -> None:
        with self._session_factory.begin() as session:
            episode = session.get(Episode, episode_id)
            if episode is not None:
                episode.ai_used = {**episode.ai_used, step.value: to_model_value(choice)}

    def update_episode_if(
        self, episode_id: str, expected: Mapping[str, Any], values: Mapping[str, Any]
    ) -> bool:
        conditions = [getattr(Episode, name) == value for name, value in expected.items()]
        with self._session_factory.begin() as session:
            updated = session.execute(
                update(Episode).where(Episode.id == episode_id, *conditions).values(**values)
            )
            return updated.rowcount == 1

    def delete_episode(self, episode_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(GenerationRequest).where(GenerationRequest.episode_id == episode_id)
            )
            session.execute(delete(Scene).where(Scene.episode_id == episode_id))
            session.execute(delete(EpisodePart).where(EpisodePart.episode_id == episode_id))
            session.execute(delete(Episode).where(Episode.id == episode_id))

    def save_outline(self, episode_id: str, outline: OutlineSave) -> bool:
        with self._session_factory.begin() as session:
            episode = session.get(Episode, episode_id, with_for_update=True)
            if episode is None or not _is_running_at(episode, EpisodeStep.WRITING_OUTLINE):
                return False
            has_parts = session.scalar(
                select(EpisodePart.id).where(EpisodePart.episode_id == episode_id).limit(1)
            )
            if has_parts is not None:
                return False
            for part in outline.parts:
                session.add(part)
            session.execute(
                update(Episode).where(Episode.id == episode_id).values(**outline.episode_values)
            )
            return True

    def save_part_script(self, part: EpisodePart, script: ScriptSave) -> bool:
        with self._session_factory.begin() as session:
            episode = session.get(Episode, part.episode_id, with_for_update=True)
            if episode is None or not _is_running_at(episode, EpisodeStep.WRITING_SCRIPT):
                return False
            if session.get(EpisodePart, part.id) is None:
                return False
            has_scenes = session.scalar(select(Scene.id).where(Scene.part_id == part.id).limit(1))
            if has_scenes is not None:
                return False
            for character in script.new_characters:
                session.add(character)
            session.flush()
            for character_id in script.linked_character_ids:
                if session.get(FilmProjectCharacter, (episode.project_id, character_id)) is None:
                    session.add(
                        FilmProjectCharacter(
                            project_id=episode.project_id, character_id=character_id
                        )
                    )
            for character_id, values in script.character_values_by_id.items():
                session.execute(
                    update(Character).where(Character.id == character_id).values(**values)
                )
            for scene in script.scenes:
                session.add(scene)
            session.execute(
                update(EpisodePart).where(EpisodePart.id == part.id).values(recap=script.recap)
            )
            return True

    def save_story_bible(self, episode_id: str, story: StoryBibleSave) -> bool:
        with self._session_factory.begin() as session:
            episode = session.get(Episode, episode_id, with_for_update=True)
            if episode is None or not _is_running_at(episode, EpisodeStep.UPDATING_STORY_BIBLE):
                return False
            episode.summary = story.summary
            session.execute(
                update(FilmProject)
                .where(FilmProject.id == episode.project_id)
                .values(
                    story_bible=story.story_bible,
                    story_bible_episode_id=episode_id,
                    story_bible_updated_at=utc_now(),
                )
            )
            return True

    def find_parts(self, episode_id: str) -> list[EpisodePart]:
        with self._session_factory() as session:
            statement = (
                select(EpisodePart)
                .where(EpisodePart.episode_id == episode_id)
                .order_by(EpisodePart.position)
            )
            return list(session.scalars(statement))

    def find_part(self, part_id: str) -> EpisodePart | None:
        with self._session_factory() as session:
            return session.get(EpisodePart, part_id)

    def insert_part(self, part: EpisodePart) -> EpisodePart:
        with self._session_factory.begin() as session:
            session.execute(
                update(EpisodePart)
                .where(
                    EpisodePart.episode_id == part.episode_id,
                    EpisodePart.position >= part.position,
                )
                .values(position=EpisodePart.position + 1)
            )
            session.add(part)
        return part

    def update_part(self, part_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(EpisodePart).where(EpisodePart.id == part_id).values(**values))

    def move_part(self, part: EpisodePart, new_position: int) -> None:
        with self._session_factory.begin() as session:
            _shift_positions(
                session,
                EpisodePart,
                EpisodePart.episode_id == part.episode_id,
                (part.position, new_position),
            )
            session.execute(
                update(EpisodePart).where(EpisodePart.id == part.id).values(position=new_position)
            )

    def delete_part(self, part: EpisodePart) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(EpisodePart).where(EpisodePart.id == part.id))
            session.execute(
                update(EpisodePart)
                .where(
                    EpisodePart.episode_id == part.episode_id,
                    EpisodePart.position > part.position,
                )
                .values(position=EpisodePart.position - 1)
            )

    def delete_script(self, episode_id: str) -> None:
        with self._session_factory.begin() as session:
            scene_ids = select(Scene.id).where(Scene.episode_id == episode_id)
            session.execute(
                delete(GenerationRequest).where(GenerationRequest.scene_id.in_(scene_ids))
            )
            session.execute(delete(Scene).where(Scene.episode_id == episode_id))
            session.execute(delete(EpisodePart).where(EpisodePart.episode_id == episode_id))

    def clear_part_script(self, part_id: str) -> None:
        with self._session_factory.begin() as session:
            scene_ids = select(Scene.id).where(Scene.part_id == part_id)
            session.execute(
                delete(GenerationRequest).where(GenerationRequest.scene_id.in_(scene_ids))
            )
            session.execute(delete(Scene).where(Scene.part_id == part_id))
            session.execute(update(EpisodePart).where(EpisodePart.id == part_id).values(recap=None))

    def find_scenes(self, episode_id: str) -> list[Scene]:
        with self._session_factory() as session:
            statement = (
                select(Scene)
                .join(EpisodePart, EpisodePart.id == Scene.part_id)
                .where(Scene.episode_id == episode_id)
                .order_by(EpisodePart.position, Scene.position)
            )
            return list(session.scalars(statement))

    def find_part_scenes(self, part_id: str) -> list[Scene]:
        with self._session_factory() as session:
            statement = select(Scene).where(Scene.part_id == part_id).order_by(Scene.position)
            return list(session.scalars(statement))

    def count_scenes_by_part(self, part_ids: Collection[str]) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(Scene.part_id, func.count())
                .where(Scene.part_id.in_(part_ids))
                .group_by(Scene.part_id)
            )
            return {part_id: count for part_id, count in rows}

    def count_scenes_before_part(self, part: EpisodePart) -> int:
        with self._session_factory() as session:
            count = session.scalar(
                select(func.count())
                .select_from(Scene)
                .join(EpisodePart, EpisodePart.id == Scene.part_id)
                .where(
                    EpisodePart.episode_id == part.episode_id,
                    EpisodePart.position < part.position,
                )
            )
            return count or 0

    def count_scenes_by_episode(self, episode_ids: Collection[str]) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(Scene.episode_id, func.count())
                .where(Scene.episode_id.in_(episode_ids))
                .group_by(Scene.episode_id)
            )
            return {episode_id: count for episode_id, count in rows}

    def find_scene(self, scene_id: str) -> Scene | None:
        with self._session_factory() as session:
            return session.get(Scene, scene_id)

    def update_scene(self, scene_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Scene).where(Scene.id == scene_id).values(**values))

    def insert_scene(self, scene: Scene) -> Scene:
        with self._session_factory.begin() as session:
            session.execute(
                update(Scene)
                .where(Scene.part_id == scene.part_id, Scene.position >= scene.position)
                .values(position=Scene.position + 1)
            )
            session.add(scene)
        return scene

    def move_scene(self, scene: Scene, new_position: int) -> None:
        with self._session_factory.begin() as session:
            _shift_positions(
                session, Scene, Scene.part_id == scene.part_id, (scene.position, new_position)
            )
            session.execute(update(Scene).where(Scene.id == scene.id).values(position=new_position))

    def delete_scene(self, scene: Scene) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(GenerationRequest).where(GenerationRequest.scene_id == scene.id))
            session.execute(delete(Scene).where(Scene.id == scene.id))
            session.execute(
                update(Scene)
                .where(Scene.part_id == scene.part_id, Scene.position > scene.position)
                .values(position=Scene.position - 1)
            )

    def find_open_requests_for_project(self, project_id: str) -> list[GenerationRequest]:
        return self._find_open_requests(GenerationRequest.project_id == project_id)

    def find_open_requests_for_episode(self, episode_id: str) -> list[GenerationRequest]:
        return self._find_open_requests(GenerationRequest.episode_id == episode_id)

    def find_open_requests_for_scene(self, scene_id: str) -> list[GenerationRequest]:
        return self._find_open_requests(GenerationRequest.scene_id == scene_id)

    def find_open_requests_for_character(self, character_id: str) -> list[GenerationRequest]:
        return self._find_open_requests(GenerationRequest.character_id == character_id)

    def find_open_requests_for_characters(
        self, character_ids: Collection[str]
    ) -> list[GenerationRequest]:
        if not character_ids:
            return []
        return self._find_open_requests(GenerationRequest.character_id.in_(character_ids))

    def find_latest_requests(
        self, episode_id: str, kind: GenerationKind
    ) -> list[GenerationRequest]:
        with self._session_factory() as session:
            statement = (
                select(GenerationRequest)
                .where(GenerationRequest.episode_id == episode_id, GenerationRequest.kind == kind)
                .order_by(GenerationRequest.created_at.desc())
            )
            return list(session.scalars(statement))

    def delete_requests(self, request_ids: Collection[str]) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(GenerationRequest).where(GenerationRequest.id.in_(request_ids)))

    def _find_open_requests(self, condition: Any) -> list[GenerationRequest]:
        with self._session_factory() as session:
            statement = (
                select(GenerationRequest)
                .where(condition, GenerationRequest.status.in_(OPEN_GENERATION_STATUSES))
                .order_by(GenerationRequest.created_at)
            )
            return list(session.scalars(statement))


def _is_running_at(episode: Episode, step: EpisodeStep) -> bool:
    return episode.status is EpisodeStatus.RUNNING and episode.step is step


def _shift_positions(
    session: Session, model: type[Scene] | type[EpisodePart], scope: Any, move: tuple[int, int]
) -> None:
    old_position, new_position = move
    if new_position < old_position:
        session.execute(
            update(model)
            .where(scope, model.position >= new_position, model.position < old_position)
            .values(position=model.position + 1)
        )
        return
    session.execute(
        update(model)
        .where(scope, model.position > old_position, model.position <= new_position)
        .values(position=model.position - 1)
    )
