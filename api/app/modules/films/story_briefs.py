from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AiModelChoice
from app.modules.film_clones.clone_catalog import LANGUAGE_NAMES_BY_CODE
from app.modules.films.analysis_source import AnalysisSource
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_imports import FilmImports
from app.modules.films.models import Character, Episode, EpisodeSource, FilmProject
from app.modules.films.repository import FilmRepository
from app.modules.prompt_presets.prompt_texts import FilmScriptAnalysis, StoryContextText

CAST_LINE_TEMPLATE = "{name} ({entity_type}): {description}"
VOICE_SUFFIX_TEMPLATE = ". Voice: {voice_description}"
EARLIER_EPISODE_TEMPLATE = "{number}. {title}"
LOGLINE_SUFFIX_TEMPLATE = " — {logline}"
SUMMARY_LINE_TEMPLATE = "Summary: {summary}"


@dataclass(frozen=True)
class ScriptWriterTools:
    repository: FilmRepository
    imports: FilmImports
    analysis_source: AnalysisSource
    ai_caller: AiCaller
    limits: AiLimits


@dataclass(frozen=True)
class StoryBrief:
    project: FilmProject
    episode: Episode
    cast: Sequence[Character]
    analysis: FilmScriptAnalysis | None


def to_cast_line(character: Character) -> str:
    return CAST_LINE_TEMPLATE.format(
        name=character.name,
        entity_type=character.entity_type,
        description=character.description,
    )


def to_voiced_cast_line(character: Character) -> str:
    line = to_cast_line(character)
    if not character.voice_description:
        return line
    return line + VOICE_SUFFIX_TEMPLATE.format(voice_description=character.voice_description)


def to_episode_heading(episode: Episode) -> str:
    line = EARLIER_EPISODE_TEMPLATE.format(number=episode.number, title=episode.title)
    if not episode.logline:
        return line
    return line + LOGLINE_SUFFIX_TEMPLATE.format(logline=episode.logline)


def to_earlier_episode_lines(episode: Episode) -> list[str]:
    lines = [to_episode_heading(episode)]
    if episode.summary:
        lines.append(SUMMARY_LINE_TEMPLATE.format(summary=episode.summary))
    return lines


def to_language_name(project: FilmProject) -> str:
    return LANGUAGE_NAMES_BY_CODE[project.language.value]


class StoryBriefs:
    def __init__(self, tools: ScriptWriterTools):
        self._tools = tools

    def load(self, episode_id: str) -> StoryBrief | None:
        repository = self._tools.repository
        episode = repository.find_episode(episode_id)
        project = None if episode is None else repository.find_project(episode.project_id)
        if episode is None or project is None:
            return None
        return StoryBrief(
            project=project,
            episode=episode,
            cast=repository.find_project_characters(project.id),
            analysis=self._read_analysis(episode),
        )

    def to_context(self, brief: StoryBrief) -> StoryContextText:
        return StoryContextText(
            series_name=brief.project.name,
            premise=brief.project.description,
            story_bible=brief.project.story_bible,
            language_name=to_language_name(brief.project),
            earlier_episode_lines=self._find_earlier_episode_lines(brief.episode),
            idea=brief.episode.idea,
            analysis=brief.analysis,
        )

    def ask(self, choice: AiModelChoice, ask: AiAsk) -> dict[str, Any]:
        try:
            return self._tools.ai_caller.ask_for_json(choice, ask, self._tools.limits)
        except AiCallError as error:
            raise EpisodeStepFailedError(str(error)) from error

    def _read_analysis(self, episode: Episode) -> FilmScriptAnalysis | None:
        if episode.source is not EpisodeSource.FILM_ANALYSIS:
            return None
        return self._tools.analysis_source.read(episode)

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
            line
            for earlier in earlier_episodes
            if scene_counts_by_episode_id.get(earlier.id, 0)
            for line in to_earlier_episode_lines(earlier)
        ]
