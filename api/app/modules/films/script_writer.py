import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AiModelChoice, AiStepGroup
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.film_clones.clone_catalog import LANGUAGE_NAMES_BY_CODE
from app.modules.films.analysis_source import AnalysisSource
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_imports import CharacterSeed, FileCopy, FilmImports, ReferenceFile
from app.modules.films.film_prompts import to_project_aspect
from app.modules.films.models import (
    Character,
    Episode,
    EpisodeSource,
    EpisodeStep,
    FilmProject,
    MediaStatus,
    ReferenceSource,
    Scene,
    Style,
)
from app.modules.films.repository import FilmRepository, ScriptSave
from app.modules.films.scene_resets import DEFAULT_TRIM_START_MS
from app.modules.films.script_replies import (
    SCRIPT_REPLY_SCHEMA,
    ScriptShape,
    WrittenCharacter,
    WrittenScript,
    normalize_script_reply,
    to_character_ids,
)
from app.modules.films.style_service import get_known_style
from app.modules.prompt_presets.prompt_texts import (
    FilmScriptAnalysis,
    FilmScriptRequestText,
    build_film_script_message,
)

FRAME_LABEL_TEMPLATE = "{aspect} {orientation}"
STYLE_LINE_TEMPLATE = "{name} — {instruction}"
CAST_LINE_TEMPLATE = "{name} ({entity_type}): {description}"
VOICE_SUFFIX_TEMPLATE = ". Voice: {voice_description}"
EARLIER_EPISODE_TEMPLATE = "{number}. {title}"
LOGLINE_SUFFIX_TEMPLATE = " — {logline}"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScriptWriterTools:
    repository: FilmRepository
    imports: FilmImports
    analysis_source: AnalysisSource
    ai_caller: AiCaller
    limits: AiLimits


@dataclass(frozen=True)
class _ScriptBrief:
    project: FilmProject
    episode: Episode
    style: Style
    cast: Sequence[Character]
    analysis: FilmScriptAnalysis | None


@dataclass
class _CastPlan:
    brief: _ScriptBrief
    characters_by_name: dict[str, Character]
    new_characters: list[Character] = field(default_factory=list)
    linked_character_ids: list[str] = field(default_factory=list)
    character_values_by_id: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    file_copies: list[FileCopy] = field(default_factory=list)


def to_cast_line(character: Character) -> str:
    line = CAST_LINE_TEMPLATE.format(
        name=character.name,
        entity_type=character.entity_type,
        description=character.description,
    )
    if not character.voice_description:
        return line
    return line + VOICE_SUFFIX_TEMPLATE.format(voice_description=character.voice_description)


def to_earlier_episode_line(episode: Episode) -> str:
    line = EARLIER_EPISODE_TEMPLATE.format(number=episode.number, title=episode.title)
    if not episode.logline:
        return line
    return line + LOGLINE_SUFFIX_TEMPLATE.format(logline=episode.logline)


class EpisodeScriptWriter:
    def __init__(self, tools: ScriptWriterTools):
        self._tools = tools

    def write_script(self, episode_id: str) -> None:
        brief = self._load_brief(episode_id)
        if brief is None:
            return
        episode = brief.episode
        choice = self._tools.ai_caller.find_model(AiStepGroup.FILM_SCRIPT)
        self._tools.repository.save_ai_used(episode.id, EpisodeStep.WRITING_SCRIPT, choice)
        script = normalize_script_reply(
            self._ask_for_script(choice, brief),
            ScriptShape(brief.project.clip_duration_s, episode.number, to_ai_name(choice.provider)),
        )
        self._save(script, self._plan_cast(brief, script))

    def _ask_for_script(self, choice: AiModelChoice, brief: _ScriptBrief) -> dict[str, Any]:
        try:
            return self._tools.ai_caller.ask_for_json(
                choice,
                AiAsk(
                    instructions=brief.episode.film_script_prompt,
                    message=build_film_script_message(self._to_request_text(brief)),
                    reply_schema=SCRIPT_REPLY_SCHEMA,
                ),
                self._tools.limits,
            )
        except AiCallError as error:
            raise EpisodeStepFailedError(str(error)) from error

    def _load_brief(self, episode_id: str) -> _ScriptBrief | None:
        repository = self._tools.repository
        episode = repository.find_episode(episode_id)
        project = None if episode is None else repository.find_project(episode.project_id)
        if episode is None or project is None:
            return None
        return _ScriptBrief(
            project=project,
            episode=episode,
            style=get_known_style(repository, project.style_id),
            cast=repository.find_project_characters(project.id),
            analysis=self._read_analysis(episode),
        )

    def _read_analysis(self, episode: Episode) -> FilmScriptAnalysis | None:
        if episode.source is not EpisodeSource.FILM_ANALYSIS:
            return None
        return self._tools.analysis_source.read(episode)

    def _to_request_text(self, brief: _ScriptBrief) -> FilmScriptRequestText:
        project = brief.project
        return FilmScriptRequestText(
            series_name=project.name,
            premise=project.description,
            language_name=LANGUAGE_NAMES_BY_CODE[project.language.value],
            frame_label=FRAME_LABEL_TEMPLATE.format(
                aspect=to_project_aspect(project.orientation), orientation=project.orientation
            ),
            style_line=STYLE_LINE_TEMPLATE.format(
                name=brief.style.name, instruction=brief.style.style_instruction
            ),
            target_seconds=str(brief.episode.target_duration_s),
            clip_seconds=str(project.clip_duration_s),
            allow_dialogue=project.allow_dialogue,
            allow_narration=project.allow_narration,
            cast_lines=[to_cast_line(character) for character in brief.cast],
            earlier_episode_lines=self._find_earlier_episode_lines(brief.episode),
            idea=brief.episode.idea,
            analysis=brief.analysis,
        )

    def _find_earlier_episode_lines(self, episode: Episode) -> list[str]:
        earlier_episodes = [
            earlier
            for earlier in self._tools.repository.find_episodes(episode.project_id)
            if earlier.number < episode.number
        ]
        scene_counts_by_episode_id = self._tools.repository.count_scenes_by_episode(
            [earlier.id for earlier in earlier_episodes]
        )
        return [
            to_earlier_episode_line(earlier)
            for earlier in earlier_episodes
            if scene_counts_by_episode_id.get(earlier.id, 0)
        ]

    def _plan_cast(self, brief: _ScriptBrief, script: WrittenScript) -> _CastPlan:
        plan = _CastPlan(
            brief=brief,
            characters_by_name={character.name.casefold(): character for character in brief.cast},
        )
        for written in script.characters:
            name_key = written.name.casefold()
            if name_key in plan.characters_by_name:
                self._attach_frame(plan.characters_by_name[name_key], written, plan)
            else:
                plan.characters_by_name[name_key] = self._link_or_create(written, plan)
        return plan

    def _link_or_create(self, written: WrittenCharacter, plan: _CastPlan) -> Character:
        library_character = self._tools.repository.find_character_by_name(written.name)
        if library_character is None:
            return self._create_character(written, plan)
        plan.linked_character_ids.append(library_character.id)
        self._attach_frame(library_character, written, plan)
        return library_character

    def _create_character(self, written: WrittenCharacter, plan: _CastPlan) -> Character:
        planned = self._tools.imports.plan_character(
            CharacterSeed(
                id=str(uuid4()),
                name=written.name,
                entity_type=written.entity_type,
                description=written.description,
                voice_description=written.voice_description,
                style=plan.brief.style,
                reference=self._find_frame(written, plan.brief),
                origin_job_id=plan.brief.episode.source_job_id,
            )
        )
        plan.new_characters.append(planned.character)
        plan.linked_character_ids.append(planned.character.id)
        plan.file_copies.extend(planned.file_copies)
        return planned.character

    def _attach_frame(
        self, character: Character, written: WrittenCharacter, plan: _CastPlan
    ) -> None:
        frame = self._find_frame(written, plan.brief)
        if frame is None or character.reference_status is not MediaStatus.NONE:
            return
        planned = self._tools.imports.plan_reference(character.id, frame)
        plan.character_values_by_id[character.id] = planned.values
        plan.file_copies.append(planned.file_copy)

    def _find_frame(self, written: WrittenCharacter, brief: _ScriptBrief) -> ReferenceFile | None:
        if written.reference_frame is None or brief.analysis is None:
            return None
        frame_name = Path(written.reference_frame).name
        if frame_name not in brief.analysis.frame_names:
            return None
        return ReferenceFile(
            self._tools.analysis_source.frame_path(brief.episode, frame_name),
            ReferenceSource.FILM_ANALYSIS,
        )

    def _save(self, script: WrittenScript, plan: _CastPlan) -> None:
        episode_id = plan.brief.episode.id
        script_save = ScriptSave(
            episode_values={
                "title": script.title,
                "logline": script.logline,
                "music_prompt": script.music_prompt,
                "thumbnail_prompt": script.thumbnail_prompt,
            },
            new_characters=plan.new_characters,
            linked_character_ids=plan.linked_character_ids,
            character_values_by_id=plan.character_values_by_id,
            scenes=self._to_scenes(script, plan),
        )
        try:
            self._tools.imports.copy_files(plan.file_copies)
            is_saved = self._tools.repository.save_script(episode_id, script_save)
        except Exception:
            self._tools.imports.discard_files(plan.file_copies)
            raise
        if not is_saved:
            self._tools.imports.discard_files(plan.file_copies)
            logger.warning(
                "Episode %s script dropped: episode gone, stopped or scenes exist", episode_id
            )

    def _to_scenes(self, script: WrittenScript, plan: _CastPlan) -> list[Scene]:
        character_ids_by_name = {
            name_key: character.id for name_key, character in plan.characters_by_name.items()
        }
        return [
            Scene(
                id=str(uuid4()),
                episode_id=plan.brief.episode.id,
                position=position,
                image_prompt=written.image_prompt,
                video_prompt=written.video_prompt,
                narrator_text=written.narrator_text,
                character_ids=to_character_ids(written.character_names, character_ids_by_name),
                clip_duration_s=written.clip_duration_s,
                image_status=MediaStatus.NONE,
                clip_status=MediaStatus.NONE,
                narration_status=MediaStatus.NONE,
                trim_start_ms=DEFAULT_TRIM_START_MS,
                trim_end_ms=None,
            )
            for position, written in enumerate(script.scenes)
        ]
