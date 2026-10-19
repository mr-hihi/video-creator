from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiAsk, AiCallError, AiLimits, AiModelChoice
from app.modules.films.analysis_source import AnalysisSource
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_imports import FilmImports
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    EpisodeSource,
    FilmLanguage,
    FilmProject,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.story_briefs import (
    ScriptWriterTools,
    StoryBrief,
    StoryBriefs,
    to_cast_line,
    to_earlier_episode_lines,
    to_episode_heading,
    to_language_name,
    to_voiced_cast_line,
)
from app.modules.prompt_presets.prompt_texts import FilmScriptAnalysis, StoryContextText
from app.modules.providers.provider_catalog import ProviderId

CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
SCRIPT_LIMITS = AiLimits(timeout_sec=900)
ASK = AiAsk(instructions="WRITE", message="Episode idea", reply_schema={"type": "object"})
ANALYSIS = FilmScriptAnalysis(
    character_image_prompts="## Mai\nRed coat",
    character_voice_prompts="## Mai\nSoft",
    scene_prompts="## Scene 1\nFog",
    frame_names=["frame-01.jpg"],
)


@dataclass(frozen=True)
class Outcome:
    actual: object
    expected: object


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
        "title": "Episode 4",
        "logline": None,
        "summary": None,
        "source": EpisodeSource.IDEA,
        "idea": "The bell rings again",
        "source_job_id": None,
    }
    return Episode(**{**defaults, **values})


def build_character(name: str, **values) -> Character:
    defaults = {
        "id": f"c-{name}",
        "name": name,
        "entity_type": EntityType.CHARACTER,
        "description": f"{name} looks",
        "voice_description": None,
    }
    return Character(**{**defaults, **values})


def build_briefs(episode: Episode, project: FilmProject):
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = episode
    repository.find_project.return_value = project
    repository.find_project_characters.return_value = [build_character("Mai")]
    repository.find_episodes.return_value = []
    repository.count_scenes_by_episode.return_value = {}
    analysis_source = MagicMock(spec=AnalysisSource)
    analysis_source.read.return_value = ANALYSIS
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.ask_for_json.return_value = {"title": "The Bell"}
    briefs = StoryBriefs(
        ScriptWriterTools(
            repository=repository,
            imports=MagicMock(spec=FilmImports),
            analysis_source=analysis_source,
            ai_caller=ai_caller,
            limits=SCRIPT_LIMITS,
        )
    )
    return SimpleNamespace(
        briefs=briefs,
        repository=repository,
        analysis_source=analysis_source,
        ai_caller=ai_caller,
    )


@pytest.fixture(
    params=[
        (
            build_character("Mai", voice_description="Soft, quick voice"),
            "Mai (character): Mai looks",
        ),
        (
            build_character("Old Harbor", entity_type=EntityType.LOCATION),
            "Old Harbor (location): Old Harbor looks",
        ),
    ]
)
def cast_line_outcome(request):
    character, expected = request.param
    return Outcome(actual=to_cast_line(character), expected=expected)


@pytest.fixture(
    params=[
        (
            build_character("Mai", voice_description="Soft, quick voice"),
            "Mai (character): Mai looks. Voice: Soft, quick voice",
        ),
        (build_character("Mai", voice_description=None), "Mai (character): Mai looks"),
        (build_character("Mai", voice_description=""), "Mai (character): Mai looks"),
    ]
)
def voiced_cast_line_outcome(request):
    character, expected = request.param
    return Outcome(actual=to_voiced_cast_line(character), expected=expected)


@pytest.fixture(
    params=[
        (
            build_episode(number=1, title="The Fog", logline="Mai hears a bell."),
            "1. The Fog — Mai hears a bell.",
        ),
        (build_episode(number=3, title="Harbor Lights", logline=None), "3. Harbor Lights"),
        (build_episode(number=3, title="Harbor Lights", logline=""), "3. Harbor Lights"),
    ]
)
def episode_heading_outcome(request):
    episode, expected = request.param
    return Outcome(actual=to_episode_heading(episode), expected=expected)


@pytest.fixture(
    params=[
        (
            build_episode(number=1, title="The Fog", summary="Mai follows the bell."),
            ["1. The Fog", "Summary: Mai follows the bell."],
        ),
        (build_episode(number=1, title="The Fog", summary=None), ["1. The Fog"]),
        (build_episode(number=1, title="The Fog", summary=""), ["1. The Fog"]),
    ]
)
def earlier_episode_lines_outcome(request):
    episode, expected = request.param
    return Outcome(actual=to_earlier_episode_lines(episode), expected=expected)


@pytest.fixture(
    params=[
        (FilmLanguage.VIETNAMESE, "Vietnamese"),
        (FilmLanguage.ENGLISH, "English"),
        (FilmLanguage.JAPANESE, "Japanese"),
    ]
)
def language_name_outcome(request):
    language, expected = request.param
    return Outcome(actual=to_language_name(build_project(language=language)), expected=expected)


@pytest.fixture
def idea_brief_run():
    run = build_briefs(build_episode(), build_project())
    return SimpleNamespace(brief=run.briefs.load("e4"), run=run)


@pytest.fixture
def analysis_brief_run():
    episode = build_episode(source=EpisodeSource.FILM_ANALYSIS, source_job_id="fa-1")
    run = build_briefs(episode, build_project())
    return SimpleNamespace(brief=run.briefs.load("e4"), run=run, episode=episode)


@pytest.fixture(params=["find_episode", "find_project"])
def missing_record_brief(request):
    run = build_briefs(build_episode(), build_project())
    getattr(run.repository, request.param).return_value = None
    return SimpleNamespace(brief=run.briefs.load("e4"), run=run)


@pytest.fixture
def story_context_run():
    episode = build_episode()
    run = build_briefs(episode, build_project())
    run.repository.find_episodes.return_value = [
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
    run.repository.count_scenes_by_episode.return_value = {"e1": 3, "e2": 0, "e3": 2, "e5": 4}
    brief = StoryBrief(project=build_project(), episode=episode, cast=[], analysis=ANALYSIS)
    return SimpleNamespace(context=run.briefs.to_context(brief), run=run)


@pytest.fixture
def bare_story_context():
    project = build_project(description=None, story_bible=None, language=FilmLanguage.JAPANESE)
    episode = build_episode(idea=None)
    run = build_briefs(episode, project)
    brief = StoryBrief(project=project, episode=episode, cast=[], analysis=None)
    return run.briefs.to_context(brief)


@pytest.fixture
def answered_ask():
    run = build_briefs(build_episode(), build_project())
    return SimpleNamespace(reply=run.briefs.ask(CLAUDE_CHOICE, ASK), run=run)


@pytest.fixture
def failed_ask():
    run = build_briefs(build_episode(), build_project())
    run.ai_caller.ask_for_json.side_effect = AiCallError("claude failed: Overloaded")
    with pytest.raises(EpisodeStepFailedError) as error:
        run.briefs.ask(CLAUDE_CHOICE, ASK)
    return error.value


def test_a_cast_line_names_the_character_without_its_voice(cast_line_outcome):
    assert cast_line_outcome.actual == cast_line_outcome.expected


def test_a_voiced_cast_line_adds_the_voice_when_set(voiced_cast_line_outcome):
    assert voiced_cast_line_outcome.actual == voiced_cast_line_outcome.expected


def test_an_episode_heading_adds_the_logline_when_set(episode_heading_outcome):
    assert episode_heading_outcome.actual == episode_heading_outcome.expected


def test_earlier_episode_lines_add_the_summary_when_set(earlier_episode_lines_outcome):
    assert earlier_episode_lines_outcome.actual == earlier_episode_lines_outcome.expected


def test_the_language_name_follows_the_project_language(language_name_outcome):
    assert language_name_outcome.actual == language_name_outcome.expected


def test_a_brief_holds_the_project_episode_and_cast(idea_brief_run):
    brief = idea_brief_run.brief
    assert (brief.project.id, brief.episode.id, [character.name for character in brief.cast]) == (
        "p1",
        "e4",
        ["Mai"],
    )


def test_the_cast_is_read_for_the_episode_project(idea_brief_run):
    idea_brief_run.run.repository.find_project_characters.assert_called_once_with("p1")


def test_an_idea_brief_has_no_analysis(idea_brief_run):
    assert idea_brief_run.brief.analysis is None


def test_an_idea_brief_reads_no_analysis(idea_brief_run):
    assert not idea_brief_run.run.analysis_source.read.called


def test_an_analysis_brief_reads_the_copied_analysis(analysis_brief_run):
    assert analysis_brief_run.brief.analysis is ANALYSIS


def test_an_analysis_brief_reads_the_analysis_of_its_episode(analysis_brief_run):
    analysis_brief_run.run.analysis_source.read.assert_called_once_with(analysis_brief_run.episode)


def test_a_missing_episode_or_project_gives_no_brief(missing_record_brief):
    assert missing_record_brief.brief is None


def test_a_missing_episode_or_project_reads_no_cast(missing_record_brief):
    assert not missing_record_brief.run.repository.find_project_characters.called


def test_the_context_lists_only_earlier_episodes_with_scenes(story_context_run):
    assert story_context_run.context == StoryContextText(
        series_name="Test Series",
        premise="A fishing town hides a drowned city.",
        story_bible="Mai keeps the harbor bell.",
        language_name="English",
        earlier_episode_lines=[
            "1. The Fog — Mai hears a bell.",
            "Summary: Mai follows the bell to the pier.",
            "3. Harbor Lights",
        ],
        idea="The bell rings again",
        analysis=ANALYSIS,
    )


def test_scenes_are_counted_only_for_earlier_episodes(story_context_run):
    story_context_run.run.repository.count_scenes_by_episode.assert_called_once_with(
        ["e1", "e2", "e3"]
    )


def test_the_episodes_are_read_for_the_episode_project(story_context_run):
    story_context_run.run.repository.find_episodes.assert_called_once_with("p1")


def test_a_bare_context_has_no_premise_story_bible_or_earlier_episodes(bare_story_context):
    assert bare_story_context == StoryContextText(
        series_name="Test Series",
        premise=None,
        story_bible=None,
        language_name="Japanese",
        earlier_episode_lines=[],
        idea=None,
        analysis=None,
    )


def test_an_ask_returns_the_model_reply(answered_ask):
    assert answered_ask.reply == {"title": "The Bell"}


def test_an_ask_passes_the_choice_and_the_limits(answered_ask):
    answered_ask.run.ai_caller.ask_for_json.assert_called_once_with(
        CLAUDE_CHOICE, ASK, SCRIPT_LIMITS
    )


def test_a_failed_ask_fails_the_step_with_the_call_message(failed_ask):
    assert str(failed_ask) == "claude failed: Overloaded"


def test_a_failed_ask_keeps_the_call_error_as_its_cause(failed_ask):
    assert isinstance(failed_ask.__cause__, AiCallError)
