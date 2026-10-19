import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.ai_models.ai_calls import AiAsk, AiModelChoice, AiStepGroup
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_imports import CharacterSeed, FileCopy, ReferenceFile
from app.modules.films.film_prompts import to_project_aspect
from app.modules.films.models import (
    Character,
    EpisodePart,
    EpisodeStep,
    MediaStatus,
    ReferenceSource,
    Scene,
    Style,
)
from app.modules.films.part_rules import to_part_number
from app.modules.films.repository import ScriptSave
from app.modules.films.scene_resets import DEFAULT_TRIM_START_MS
from app.modules.films.script_replies import (
    SCRIPT_REPLY_SCHEMA,
    ScriptShape,
    WrittenCharacter,
    WrittenScript,
    normalize_script_reply,
    to_character_ids,
)
from app.modules.films.story_briefs import (
    ScriptWriterTools,
    StoryBrief,
    StoryBriefs,
    to_voiced_cast_line,
)
from app.modules.films.style_service import get_known_style
from app.modules.prompt_presets.prompt_texts import (
    FilmScriptRequestText,
    build_film_script_message,
)

FRAME_LABEL_TEMPLATE = "{aspect} {orientation}"
STYLE_LINE_TEMPLATE = "{name} — {instruction}"
OUTLINE_LINE_TEMPLATE = "{number}. {title}: {plan}"
STORY_SO_FAR_LINE_TEMPLATE = "{number}. {story}"
PART_FAILED_MESSAGE = "Part {number}: {message}"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PartBrief:
    story: StoryBrief
    style: Style
    parts: Sequence[EpisodePart]
    part: EpisodePart


@dataclass
class _CastPlan:
    brief: _PartBrief
    characters_by_name: dict[str, Character]
    new_characters: list[Character] = field(default_factory=list)
    linked_character_ids: list[str] = field(default_factory=list)
    character_values_by_id: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    file_copies: list[FileCopy] = field(default_factory=list)


class EpisodeScriptWriter:
    def __init__(self, tools: ScriptWriterTools):
        self._tools = tools
        self._briefs = StoryBriefs(tools)

    def write_part(self, part_id: str) -> None:
        brief = self._load_brief(part_id)
        if brief is None:
            return
        choice = self._tools.ai_caller.find_model(AiStepGroup.FILM_SCRIPT)
        self._tools.repository.save_ai_used(
            brief.part.episode_id, EpisodeStep.WRITING_SCRIPT, choice
        )
        try:
            script = normalize_script_reply(
                self._ask_for_part(choice, brief),
                ScriptShape(brief.story.project.clip_duration_s, to_ai_name(choice.provider)),
            )
        except EpisodeStepFailedError as error:
            raise EpisodeStepFailedError(
                PART_FAILED_MESSAGE.format(
                    number=to_part_number(brief.part.position), message=error
                )
            ) from error
        self._save(script, self._plan_cast(brief, script))

    def _ask_for_part(self, choice: AiModelChoice, brief: _PartBrief) -> dict[str, Any]:
        return self._briefs.ask(
            choice,
            AiAsk(
                instructions=brief.story.episode.film_script_prompt,
                message=build_film_script_message(self._to_request_text(brief)),
                reply_schema=SCRIPT_REPLY_SCHEMA,
            ),
        )

    def _load_brief(self, part_id: str) -> _PartBrief | None:
        repository = self._tools.repository
        part = repository.find_part(part_id)
        story = None if part is None else self._briefs.load(part.episode_id)
        if part is None or story is None:
            return None
        return _PartBrief(
            story=story,
            style=get_known_style(repository, story.project.style_id),
            parts=repository.find_parts(part.episode_id),
            part=part,
        )

    def _to_request_text(self, brief: _PartBrief) -> FilmScriptRequestText:
        project = brief.story.project
        return FilmScriptRequestText(
            context=self._briefs.to_context(brief.story),
            frame_label=FRAME_LABEL_TEMPLATE.format(
                aspect=to_project_aspect(project.orientation), orientation=project.orientation
            ),
            style_line=STYLE_LINE_TEMPLATE.format(
                name=brief.style.name, instruction=brief.style.style_instruction
            ),
            target_seconds=str(brief.part.target_duration_s),
            clip_seconds=str(project.clip_duration_s),
            allow_dialogue=project.allow_dialogue,
            allow_narration=project.allow_narration,
            cast_lines=[to_voiced_cast_line(character) for character in brief.story.cast],
            outline_lines=[
                OUTLINE_LINE_TEMPLATE.format(
                    number=to_part_number(part.position), title=part.title, plan=part.plan
                )
                for part in brief.parts
            ],
            part_number=str(to_part_number(brief.part.position)),
            story_so_far_lines=[
                STORY_SO_FAR_LINE_TEMPLATE.format(
                    number=to_part_number(part.position), story=part.recap or part.plan
                )
                for part in brief.parts
                if part.position < brief.part.position
            ],
        )

    def _plan_cast(self, brief: _PartBrief, script: WrittenScript) -> _CastPlan:
        plan = _CastPlan(
            brief=brief,
            characters_by_name={
                character.name.casefold(): character for character in brief.story.cast
            },
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
                origin_job_id=plan.brief.story.episode.source_job_id,
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

    def _find_frame(self, written: WrittenCharacter, brief: _PartBrief) -> ReferenceFile | None:
        analysis = brief.story.analysis
        if written.reference_frame is None or analysis is None:
            return None
        frame_name = Path(written.reference_frame).name
        if frame_name not in analysis.frame_names:
            return None
        return ReferenceFile(
            self._tools.analysis_source.frame_path(brief.story.episode, frame_name),
            ReferenceSource.FILM_ANALYSIS,
        )

    def _save(self, script: WrittenScript, plan: _CastPlan) -> None:
        part = plan.brief.part
        script_save = ScriptSave(
            recap=script.recap,
            new_characters=plan.new_characters,
            linked_character_ids=plan.linked_character_ids,
            character_values_by_id=plan.character_values_by_id,
            scenes=self._to_scenes(script, plan),
        )
        try:
            self._tools.imports.copy_files(plan.file_copies)
            is_saved = self._tools.repository.save_part_script(part, script_save)
        except Exception:
            self._tools.imports.discard_files(plan.file_copies)
            raise
        if not is_saved:
            self._tools.imports.discard_files(plan.file_copies)
            logger.warning(
                "Part %s script dropped: episode gone or stopped, or part gone or written", part.id
            )

    def _to_scenes(self, script: WrittenScript, plan: _CastPlan) -> list[Scene]:
        character_ids_by_name = {
            name_key: character.id for name_key, character in plan.characters_by_name.items()
        }
        return [
            Scene(
                id=str(uuid4()),
                episode_id=plan.brief.part.episode_id,
                part_id=plan.brief.part.id,
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
