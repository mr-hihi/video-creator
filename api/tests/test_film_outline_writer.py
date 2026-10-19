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
    Character,
    EntityType,
    Episode,
    EpisodeSource,
    EpisodeStep,
    FilmLanguage,
    FilmProject,
)
from app.modules.films.outline_replies import OUTLINE_REPLY_SCHEMA
from app.modules.films.outline_writer import EpisodeOutlineWriter
from app.modules.films.repository import FilmRepository
from app.modules.films.story_briefs import ScriptWriterTools
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS, FilmScriptAnalysis
from app.modules.providers.provider_catalog import ProviderId

CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash")
SCRIPT_LIMITS = AiLimits(timeout_sec=900)
WRITER_LOGGER = "app.modules.films.outline_writer"
ANALYSIS = FilmScriptAnalysis(
    character_image_prompts="## Mai\nRed coat",
    character_voice_prompts="## Mai\nSoft",
    scene_prompts="## Scene 1\nFog",
    frame_names=["frame-01.jpg"],
)
EXPECTED_IDEA_MESSAGE = (
    "Series: Test Series\n"
    "Premise: A fishing town hides a drowned city.\n\n"
    "Story bible:\n"
    "Mai keeps the harbor bell.\n\n"
    "Language of narration and dialogue: English\n\n"
    "Earlier episodes:\n"
    "1. The Fog — Mai hears a bell.\n"
    "Summary: Mai follows the bell to the pier.\n"
    "3. Harbor Lights\n\n"
    "Episode idea:\n"
    "The bell rings again\n\n"
    "Split the episode into parts whose lengths add up to about 300s. Each part lasts 8-600 s.\n\n"
    "Cast:\n"
    "Mai (character): A young woman in a red raincoat\n"
    "Old Harbor (location): A foggy fishing harbor at dawn"
)
EXPECTED_BARE_MESSAGE = (
    "Series: Test Series\n\n"
    "Language of narration and dialogue: Vietnamese\n\n"
    "Episode idea:\n"
    "A storm\n\n"
    "Split the episode into parts whose lengths add up to about 60s. Each part lasts 8-600 s."
)
EXPECTED_ANALYSIS_MESSAGE = (
    "Series: Test Series\n\n"
    "Language of narration and dialogue: Vietnamese\n\n"
    "Adapt this film analysis:\n\n"
    "Character image prompts:\n## Mai\nRed coat\n\n"
    "Character voice prompts:\n## Mai\nSoft\n\n"
    "Scene prompts:\n## Scene 1\nFog\n\n"
    "Extra direction:\n"
    "Set it in winter\n\n"
    "Split the episode into parts whose lengths add up to about 60s. Each part lasts 8-600 s."
)


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "description": None,
        "language": FilmLanguage.VIETNAMESE,
        "story_bible": None,
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e4",
        "project_id": "p1",
        "number": 4,
        "title": "Episode 4",
        "logline": None,
        "summary": None,
        "source": EpisodeSource.IDEA,
        "idea": "A storm",
        "source_job_id": None,
        "target_duration_s": 60,
        "film_outline_prompt": None,
    }
    return Episode(**{**defaults, **values})


def build_character(character_id: str, name: str, **values) -> Character:
    defaults = {
        "id": character_id,
        "name": name,
        "entity_type": EntityType.CHARACTER,
        "description": f"{name} looks",
        "voice_description": None,
    }
    return Character(**{**defaults, **values})


def build_reply(**values) -> dict:
    return {
        "title": "The Bell",
        "logline": "Mai rings the drowned bell.",
        "parts": [
            {"title": "The Pier", "plan": "Mai walks to the pier.", "durationS": 120},
            {"title": "The Bell", "plan": "Mai rings the drowned bell.", "durationS": 180},
        ],
        "musicPrompt": "Slow cello",
        "thumbnailPrompt": "A bell in fog",
        **values,
    }


def build_writer(episode: Episode, project: FilmProject, choice=CLAUDE_CHOICE):
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = episode
    repository.find_project.return_value = project
    repository.find_project_characters.return_value = []
    repository.find_episodes.return_value = []
    repository.count_scenes_by_episode.return_value = {}
    repository.save_outline.return_value = True
    analysis_source = MagicMock(spec=AnalysisSource)
    analysis_source.read.return_value = ANALYSIS
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = choice
    ai_caller.ask_for_json.return_value = build_reply()
    writer = EpisodeOutlineWriter(
        ScriptWriterTools(
            repository=repository,
            imports=MagicMock(spec=FilmImports),
            analysis_source=analysis_source,
            ai_caller=ai_caller,
            limits=SCRIPT_LIMITS,
        )
    )
    return SimpleNamespace(writer=writer, repository=repository, ai_caller=ai_caller)


def saved_outline(parts):
    return parts.repository.save_outline.call_args.args[1]


@pytest.fixture
def idea_run():
    project = build_project(
        description="A fishing town hides a drowned city.",
        language=FilmLanguage.ENGLISH,
        story_bible="Mai keeps the harbor bell.",
    )
    episode = build_episode(idea="The bell rings again", target_duration_s=300)
    parts = build_writer(episode, project)
    parts.repository.find_project_characters.return_value = [
        build_character(
            "c1",
            "Mai",
            description="A young woman in a red raincoat",
            voice_description="Soft, quick voice",
        ),
        build_character(
            "c2",
            "Old Harbor",
            entity_type=EntityType.LOCATION,
            description="A foggy fishing harbor at dawn",
        ),
    ]
    parts.repository.find_episodes.return_value = [
        build_episode(
            id="e1",
            number=1,
            title="The Fog",
            logline="Mai hears a bell.",
            summary="Mai follows the bell to the pier.",
        ),
        build_episode(id="e2", number=2, title="Episode 2", summary="Never written."),
        build_episode(id="e3", number=3, title="Harbor Lights"),
        episode,
        build_episode(id="e5", number=5, title="Later", summary="Not yet."),
    ]
    parts.repository.count_scenes_by_episode.return_value = {"e1": 3, "e3": 2, "e5": 4}
    parts.writer.write_outline("e4")
    return SimpleNamespace(ask=parts.ai_caller.ask_for_json.call_args.args[1], parts=parts)


@pytest.fixture
def bare_request():
    parts = build_writer(build_episode(film_outline_prompt="PLAN AN OUTLINE"), build_project())
    parts.writer.write_outline("e4")
    return parts.ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def analysis_message():
    episode = build_episode(
        source=EpisodeSource.FILM_ANALYSIS, source_job_id="fa-1", idea="Set it in winter"
    )
    parts = build_writer(episode, build_project())
    parts.writer.write_outline("e4")
    return parts.ai_caller.ask_for_json.call_args.args[1].message


@pytest.fixture
def saved_run():
    parts = build_writer(build_episode(), build_project())
    parts.ai_caller.ask_for_json.return_value = build_reply(
        title="  ",
        logline=" ",
        parts=[
            {"title": "The Pier", "plan": "Mai walks to the pier.", "durationS": 120.4},
            {"title": " ", "plan": "Dropped.", "durationS": 30},
            {"title": "The Boat", "plan": "Mai rows out.", "durationS": 2},
            {"title": "The Bell", "plan": "Mai rings the bell."},
        ],
        musicPrompt=" Slow cello ",
        thumbnailPrompt="",
    )
    parts.writer.write_outline("e4")
    return SimpleNamespace(outline=saved_outline(parts), parts=parts)


@pytest.fixture
def dropped_outline_log(caplog):
    parts = build_writer(build_episode(), build_project())
    parts.repository.save_outline.return_value = False
    with caplog.at_level(logging.WARNING, logger=WRITER_LOGGER):
        parts.writer.write_outline("e4")
    return [record.getMessage() for record in caplog.records]


@pytest.fixture(params=["find_episode", "find_project"])
def missing_record_run(request):
    parts = build_writer(build_episode(), build_project())
    getattr(parts.repository, request.param).return_value = None
    parts.writer.write_outline("e4")
    return parts


@pytest.fixture
def claude_failure():
    parts = build_writer(build_episode(), build_project())
    parts.ai_caller.ask_for_json.side_effect = AiCallError("claude failed: Overloaded")
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.write_outline("e4")
    return SimpleNamespace(error=error.value, parts=parts)


@pytest.fixture
def gemini_no_parts_run():
    parts = build_writer(build_episode(), build_project(), choice=GEMINI_CHOICE)
    parts.ai_caller.ask_for_json.return_value = build_reply(parts=[])
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.write_outline("e4")
    return SimpleNamespace(error=error.value, parts=parts)


def test_a_null_outline_prompt_uses_the_code_default(idea_run):
    assert idea_run.ask.instructions == DEFAULT_PRESET_PROMPTS.film_outline


def test_the_call_uses_the_fixed_outline_schema(idea_run):
    assert idea_run.ask.reply_schema == OUTLINE_REPLY_SCHEMA


def test_the_idea_message_carries_the_story_context_target_and_cast(idea_run):
    assert idea_run.ask.message == EXPECTED_IDEA_MESSAGE


def test_the_outline_is_asked_of_the_film_script_model(idea_run):
    idea_run.parts.ai_caller.find_model.assert_called_once_with(AiStepGroup.FILM_SCRIPT)


def test_the_outline_is_asked_with_the_chosen_model_within_its_limits(idea_run):
    call_args = idea_run.parts.ai_caller.ask_for_json.call_args.args
    assert (call_args[0], call_args[2]) == (CLAUDE_CHOICE, SCRIPT_LIMITS)


def test_the_model_is_recorded_for_the_outline_step(idea_run):
    idea_run.parts.repository.save_ai_used.assert_called_once_with(
        "e4", EpisodeStep.WRITING_OUTLINE, CLAUDE_CHOICE
    )


def test_the_episode_outline_prompt_is_used_when_set(bare_request):
    assert bare_request.instructions == "PLAN AN OUTLINE"


def test_a_bare_message_has_no_premise_story_bible_earlier_episodes_or_cast(bare_request):
    assert bare_request.message == EXPECTED_BARE_MESSAGE


def test_an_analysis_message_adapts_the_analysis_without_reference_frames(analysis_message):
    assert analysis_message == EXPECTED_ANALYSIS_MESSAGE


def test_the_outline_is_saved_for_its_episode(saved_run):
    assert saved_run.parts.repository.save_outline.call_args.args[0] == "e4"


def test_the_episode_gets_the_outline_texts_and_a_default_title(saved_run):
    assert saved_run.outline.episode_values == {
        "title": "Episode 4",
        "logline": None,
        "music_prompt": "Slow cello",
        "thumbnail_prompt": None,
    }


def test_parts_are_saved_at_positions_from_zero_without_a_recap(saved_run):
    assert [
        (
            part.episode_id,
            part.position,
            part.title,
            part.plan,
            part.target_duration_s,
            part.recap,
        )
        for part in saved_run.outline.parts
    ] == [
        ("e4", 0, "The Pier", "Mai walks to the pier.", 120, None),
        ("e4", 1, "The Boat", "Mai rows out.", 8, None),
        ("e4", 2, "The Bell", "Mai rings the bell.", 600, None),
    ]


def test_each_saved_part_gets_its_own_id(saved_run):
    assert len({part.id for part in saved_run.outline.parts}) == 3


def test_a_dropped_outline_is_logged_without_failing(dropped_outline_log):
    assert dropped_outline_log == [
        "Episode e4 outline dropped: episode gone, stopped or parts exist"
    ]


def test_a_missing_episode_or_project_calls_nothing(missing_record_run):
    assert not missing_record_run.ai_caller.ask_for_json.called


def test_a_missing_episode_or_project_records_no_model(missing_record_run):
    assert not missing_record_run.repository.save_ai_used.called


def test_a_claude_failure_fails_the_step_with_its_message(claude_failure):
    assert str(claude_failure.error) == "claude failed: Overloaded"


def test_a_claude_failure_saves_nothing(claude_failure):
    assert not claude_failure.parts.repository.save_outline.called


def test_a_reply_without_parts_names_the_model(gemini_no_parts_run):
    assert str(gemini_no_parts_run.error) == "gemini returned no parts"


def test_a_reply_without_parts_saves_nothing(gemini_no_parts_run):
    assert not gemini_no_parts_run.parts.repository.save_outline.called
