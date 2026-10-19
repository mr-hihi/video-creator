import logging
from uuid import uuid4

from app.modules.ai_models.ai_calls import AiAsk, AiStepGroup
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.films.models import EpisodePart, EpisodeStep
from app.modules.films.outline_replies import (
    OUTLINE_REPLY_SCHEMA,
    OutlineShape,
    WrittenOutline,
    normalize_outline_reply,
)
from app.modules.films.repository import OutlineSave
from app.modules.films.story_briefs import (
    ScriptWriterTools,
    StoryBrief,
    StoryBriefs,
    to_cast_line,
)
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    FilmOutlineRequestText,
    build_film_outline_message,
)

logger = logging.getLogger(__name__)


class EpisodeOutlineWriter:
    def __init__(self, tools: ScriptWriterTools):
        self._tools = tools
        self._briefs = StoryBriefs(tools)

    def write_outline(self, episode_id: str) -> None:
        brief = self._briefs.load(episode_id)
        if brief is None:
            return
        choice = self._tools.ai_caller.find_model(AiStepGroup.FILM_SCRIPT)
        self._tools.repository.save_ai_used(episode_id, EpisodeStep.WRITING_OUTLINE, choice)
        reply = self._briefs.ask(
            choice,
            AiAsk(
                instructions=brief.episode.film_outline_prompt
                or DEFAULT_PRESET_PROMPTS.film_outline,
                message=build_film_outline_message(self._to_request_text(brief)),
                reply_schema=OUTLINE_REPLY_SCHEMA,
            ),
        )
        outline = normalize_outline_reply(
            reply, OutlineShape(brief.episode.number, to_ai_name(choice.provider))
        )
        if not self._tools.repository.save_outline(
            episode_id, _to_outline_save(episode_id, outline)
        ):
            logger.warning(
                "Episode %s outline dropped: episode gone, stopped or parts exist", episode_id
            )

    def _to_request_text(self, brief: StoryBrief) -> FilmOutlineRequestText:
        return FilmOutlineRequestText(
            context=self._briefs.to_context(brief),
            target_seconds=str(brief.episode.target_duration_s),
            cast_lines=[to_cast_line(character) for character in brief.cast],
        )


def _to_outline_save(episode_id: str, outline: WrittenOutline) -> OutlineSave:
    return OutlineSave(
        episode_values={
            "title": outline.title,
            "logline": outline.logline,
            "music_prompt": outline.music_prompt,
            "thumbnail_prompt": outline.thumbnail_prompt,
        },
        parts=[
            EpisodePart(
                id=str(uuid4()),
                episode_id=episode_id,
                position=position,
                title=written.title,
                plan=written.plan,
                target_duration_s=written.target_duration_s,
                recap=None,
            )
            for position, written in enumerate(outline.parts)
        ],
    )
