import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiCallError, AiLimits, AiModelChoice, AiStepGroup
from app.modules.films.analysis_source import AnalysisSource
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_imports import FilmImports
from app.modules.films.models import (
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStep,
    FilmLanguage,
    FilmProject,
    Scene,
)
from app.modules.films.repository import FilmRepository, StoryBibleSave
from app.modules.films.story_bible_replies import STORY_BIBLE_REPLY_SCHEMA
from app.modules.films.story_bible_writer import StoryBibleWriter, to_part_lines
from app.modules.films.story_briefs import ScriptWriterTools
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.providers.provider_catalog import ProviderId

CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash")
SCRIPT_LIMITS = AiLimits(timeout_sec=900)
WRITER_LOGGER = "app.modules.films.story_bible_writer"
EXPECTED_FULL_MESSAGE = (
    "Series: Test Series\n"
    "Premise: A fishing town hides a drowned city.\n"
    "Language of narration and dialogue: English\n\n"
    "Current story bible:\n"
    "Mai keeps the harbor bell.\n\n"
    "Episode 4: The Bell — Mai rings the drowned bell.\n\n"
    "Parts:\n"
    "1. The Pier\n"
    "Mai finds a rope tied to the pier.\n"
    "2. The Boat\n"
    "Scene 3: Mai rows out. Narration: The sea is calm.\n"
    "Scene 4: The fog closes in.\n"
    "3. The Bell\n"
    "Mai rings the bell.\n\n"
    "Keep the story bible under 20000 characters."
)
EXPECTED_EMPTY_BIBLE_MESSAGE = (
    "Series: Test Series\n"
    "Language of narration and dialogue: Japanese\n\n"
    "Current story bible: (empty)\n\n"
    "Episode 4: The Bell\n\n"
    "Parts:\n"
    "1. The Pier\n"
    "Scene 1: Mai walks to the pier.\n\n"
    "Keep the story bible under 20000 characters."
)


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "description": "A fishing town hides a drowned city.",
        "language": FilmLanguage.ENGLISH,
        "story_bible": "Mai keeps the harbor bell.",
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e4",
        "project_id": "p1",
        "number": 4,
        "title": "The Bell",
        "logline": "Mai rings the drowned bell.",
        "source": EpisodeSource.IDEA,
        "story_bible_prompt": None,
    }
    return Episode(**{**defaults, **values})


def build_part(part_id: str, position: int, title: str, recap: str | None = None) -> EpisodePart:
    return EpisodePart(
        id=part_id,
        episode_id="e4",
        position=position,
        title=title,
        plan=f"{title} plan",
        target_duration_s=60,
        recap=recap,
    )


def build_scene(scene_id: str, part_id: str, video_prompt: str, narrator_text=None) -> Scene:
    return Scene(
        id=scene_id,
        episode_id="e4",
        part_id=part_id,
        position=0,
        video_prompt=video_prompt,
        narrator_text=narrator_text,
    )


def build_writer(episode: Episode, project: FilmProject, choice=CLAUDE_CHOICE):
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = episode
    repository.find_project.return_value = project
    repository.find_parts.return_value = [
        build_part("pt1", 0, "The Pier", recap="Mai finds a rope tied to the pier."),
        build_part("pt2", 1, "The Boat"),
        build_part("pt3", 2, "The Bell", recap="Mai rings the bell."),
    ]
    repository.find_scenes.return_value = [
        build_scene("s1", "pt1", "Mai walks to the pier."),
        build_scene("s2", "pt1", "Mai finds a rope.", narrator_text="A rope."),
        build_scene("s3", "pt2", "Mai rows out.", narrator_text="The sea is calm."),
        build_scene("s4", "pt2", "The fog closes in.", narrator_text=""),
        build_scene("s5", "pt3", "Mai rings the bell."),
    ]
    repository.save_story_bible.return_value = True
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = choice
    ai_caller.ask_for_json.return_value = {
        "summary": " Mai rings the bell. ",
        "storyBible": " Mai keeps the bell. ",
    }
    writer = StoryBibleWriter(
        ScriptWriterTools(
            repository=repository,
            imports=MagicMock(spec=FilmImports),
            analysis_source=MagicMock(spec=AnalysisSource),
            ai_caller=ai_caller,
            limits=SCRIPT_LIMITS,
        )
    )
    return SimpleNamespace(writer=writer, repository=repository, ai_caller=ai_caller)


@pytest.fixture
def full_run():
    parts = build_writer(build_episode(), build_project())
    parts.writer.update_story_bible("e4")
    return SimpleNamespace(ask=parts.ai_caller.ask_for_json.call_args.args[1], parts=parts)


@pytest.fixture
def empty_bible_request():
    project = build_project(description=None, story_bible=None, language=FilmLanguage.JAPANESE)
    parts = build_writer(build_episode(logline=None, story_bible_prompt="KEEP THE BIBLE"), project)
    parts.repository.find_parts.return_value = [build_part("pt1", 0, "The Pier")]
    parts.repository.find_scenes.return_value = [build_scene("s1", "pt1", "Mai walks to the pier.")]
    parts.writer.update_story_bible("e4")
    return parts.ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def unwritten_part_lines():
    return to_part_lines([build_part("pt1", 0, "The Pier")], [])


@pytest.fixture
def dropped_story_bible_log(caplog):
    parts = build_writer(build_episode(), build_project())
    parts.repository.save_story_bible.return_value = False
    with caplog.at_level(logging.WARNING, logger=WRITER_LOGGER):
        parts.writer.update_story_bible("e4")
    return [record.getMessage() for record in caplog.records]


@pytest.fixture(params=["find_episode", "find_project"])
def missing_record_run(request):
    parts = build_writer(build_episode(), build_project())
    getattr(parts.repository, request.param).return_value = None
    parts.writer.update_story_bible("e4")
    return parts


@pytest.fixture
def claude_failure():
    parts = build_writer(build_episode(), build_project())
    parts.ai_caller.ask_for_json.side_effect = AiCallError("claude failed: Overloaded")
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.update_story_bible("e4")
    return SimpleNamespace(error=error.value, parts=parts)


@pytest.fixture
def gemini_empty_run():
    parts = build_writer(build_episode(), build_project(), choice=GEMINI_CHOICE)
    parts.ai_caller.ask_for_json.return_value = {"summary": "Summary", "storyBible": "  "}
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.update_story_bible("e4")
    return SimpleNamespace(error=error.value, parts=parts)


def test_a_null_story_bible_prompt_uses_the_code_default(full_run):
    assert full_run.ask.instructions == DEFAULT_PRESET_PROMPTS.story_bible


def test_the_call_uses_the_fixed_story_bible_schema(full_run):
    assert full_run.ask.reply_schema == STORY_BIBLE_REPLY_SCHEMA


def test_the_message_lists_the_bible_episode_and_parts_by_recap_or_scenes(full_run):
    assert full_run.ask.message == EXPECTED_FULL_MESSAGE


def test_the_parts_and_scenes_are_read_for_the_episode(full_run):
    repository = full_run.parts.repository
    assert (repository.find_parts.call_args.args, repository.find_scenes.call_args.args) == (
        ("e4",),
        ("e4",),
    )


def test_the_story_bible_is_asked_of_the_film_script_model(full_run):
    full_run.parts.ai_caller.find_model.assert_called_once_with(AiStepGroup.FILM_SCRIPT)


def test_the_story_bible_is_asked_with_the_chosen_model_within_its_limits(full_run):
    call_args = full_run.parts.ai_caller.ask_for_json.call_args.args
    assert (call_args[0], call_args[2]) == (CLAUDE_CHOICE, SCRIPT_LIMITS)


def test_the_model_is_recorded_for_the_story_bible_step(full_run):
    full_run.parts.repository.save_ai_used.assert_called_once_with(
        "e4", EpisodeStep.UPDATING_STORY_BIBLE, CLAUDE_CHOICE
    )


def test_the_trimmed_summary_and_story_bible_are_saved_for_the_episode(full_run):
    full_run.parts.repository.save_story_bible.assert_called_once_with(
        "e4", StoryBibleSave(summary="Mai rings the bell.", story_bible="Mai keeps the bell.")
    )


def test_the_episode_story_bible_prompt_is_used_when_set(empty_bible_request):
    assert empty_bible_request.instructions == "KEEP THE BIBLE"


def test_an_empty_story_bible_and_no_logline_are_sent_as_such(empty_bible_request):
    assert empty_bible_request.message == EXPECTED_EMPTY_BIBLE_MESSAGE


def test_a_part_without_a_recap_or_scenes_gives_only_its_heading(unwritten_part_lines):
    assert unwritten_part_lines == ["1. The Pier"]


def test_a_dropped_story_bible_is_logged_without_failing(dropped_story_bible_log):
    assert dropped_story_bible_log == ["Episode e4 story bible dropped: episode gone or stopped"]


def test_a_missing_episode_or_project_calls_nothing(missing_record_run):
    assert not missing_record_run.ai_caller.ask_for_json.called


def test_a_missing_episode_or_project_records_no_model(missing_record_run):
    assert not missing_record_run.repository.save_ai_used.called


def test_a_claude_failure_fails_the_step_with_its_message(claude_failure):
    assert str(claude_failure.error) == "claude failed: Overloaded"


def test_a_claude_failure_saves_nothing(claude_failure):
    assert not claude_failure.parts.repository.save_story_bible.called


def test_an_empty_story_bible_reply_names_the_model(gemini_empty_run):
    assert str(gemini_empty_run.error) == "gemini returned an empty story bible"


def test_an_empty_story_bible_reply_saves_nothing(gemini_empty_run):
    assert not gemini_empty_run.parts.repository.save_story_bible.called
