import logging
from collections.abc import Sequence

from app.modules.ai_models.ai_calls import AiAsk, AiStepGroup
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.films.models import Episode, EpisodePart, EpisodeStep, FilmProject, Scene
from app.modules.films.part_rules import to_part_number
from app.modules.films.repository import StoryBibleSave
from app.modules.films.story_bible_replies import (
    STORY_BIBLE_REPLY_SCHEMA,
    normalize_story_bible_reply,
)
from app.modules.films.story_briefs import (
    LOGLINE_SUFFIX_TEMPLATE,
    ScriptWriterTools,
    StoryBriefs,
    to_language_name,
)
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    StoryBibleRequestText,
    build_story_bible_message,
)

EPISODE_LINE_TEMPLATE = "Episode {number}: {title}"
PART_HEADING_TEMPLATE = "{number}. {title}"
SCENE_LINE_TEMPLATE = "Scene {number}: {video_prompt}"
NARRATION_SUFFIX_TEMPLATE = " Narration: {narrator_text}"

logger = logging.getLogger(__name__)


class StoryBibleWriter:
    def __init__(self, tools: ScriptWriterTools):
        self._tools = tools
        self._briefs = StoryBriefs(tools)

    def update_story_bible(self, episode_id: str) -> None:
        repository = self._tools.repository
        episode = repository.find_episode(episode_id)
        project = None if episode is None else repository.find_project(episode.project_id)
        if episode is None or project is None:
            return
        choice = self._tools.ai_caller.find_model(AiStepGroup.FILM_SCRIPT)
        repository.save_ai_used(episode_id, EpisodeStep.UPDATING_STORY_BIBLE, choice)
        reply = self._briefs.ask(
            choice,
            AiAsk(
                instructions=episode.story_bible_prompt or DEFAULT_PRESET_PROMPTS.story_bible,
                message=build_story_bible_message(self._to_request_text(project, episode)),
                reply_schema=STORY_BIBLE_REPLY_SCHEMA,
            ),
        )
        written = normalize_story_bible_reply(reply, to_ai_name(choice.provider))
        story = StoryBibleSave(summary=written.summary, story_bible=written.story_bible)
        if not repository.save_story_bible(episode_id, story):
            logger.warning("Episode %s story bible dropped: episode gone or stopped", episode_id)

    def _to_request_text(self, project: FilmProject, episode: Episode) -> StoryBibleRequestText:
        return StoryBibleRequestText(
            series_name=project.name,
            premise=project.description,
            language_name=to_language_name(project),
            story_bible=project.story_bible,
            episode_line=to_episode_line(episode),
            part_lines=to_part_lines(
                self._tools.repository.find_parts(episode.id),
                self._tools.repository.find_scenes(episode.id),
            ),
        )


def to_episode_line(episode: Episode) -> str:
    line = EPISODE_LINE_TEMPLATE.format(number=episode.number, title=episode.title)
    if not episode.logline:
        return line
    return line + LOGLINE_SUFFIX_TEMPLATE.format(logline=episode.logline)


def to_part_lines(parts: Sequence[EpisodePart], scenes: Sequence[Scene]) -> list[str]:
    scene_numbers_by_id = {scene.id: number for number, scene in enumerate(scenes, start=1)}
    lines: list[str] = []
    for part in parts:
        lines.append(
            PART_HEADING_TEMPLATE.format(number=to_part_number(part.position), title=part.title)
        )
        if part.recap:
            lines.append(part.recap)
            continue
        lines.extend(
            to_scene_line(scene_numbers_by_id[scene.id], scene)
            for scene in scenes
            if scene.part_id == part.id
        )
    return lines


def to_scene_line(number: int, scene: Scene) -> str:
    line = SCENE_LINE_TEMPLATE.format(number=number, video_prompt=scene.video_prompt)
    if not scene.narrator_text:
        return line
    return line + NARRATION_SUFFIX_TEMPLATE.format(narrator_text=scene.narrator_text)
