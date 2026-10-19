from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiCallError, AiLimits, AiModelChoice, AiStepGroup
from app.modules.films.analysis_source import AnalysisSource, AnalysisSourceTools
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_imports import FilmImports
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStep,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    ReferenceSource,
    Style,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.script_replies import SCRIPT_REPLY_SCHEMA
from app.modules.films.script_writer import EpisodeScriptWriter
from app.modules.films.story_briefs import ScriptWriterTools
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.providers.provider_catalog import ProviderId

UPLOAD_MAX_MB = 20
CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash")
SCRIPT_LIMITS = AiLimits(timeout_sec=900)
STYLE = Style(
    id="realistic",
    name="Photorealistic",
    is_builtin=True,
    style_instruction="Photorealistic photo.",
    negative_prompt=None,
    scene_prefix=None,
    lighting="Studio lighting, highly detailed",
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
    "Frame: 16:9 landscape\n"
    "Style: Photorealistic — Photorealistic photo.\n\n"
    "Write scenes whose clip lengths, each minus its first second, add up to about 40s. Give "
    "each scene the clip length its action needs, 4-30 s; a typical clip lasts 8s. The first "
    "second of every clip is cut, so a scene's narration must fit in its clip length minus 1 s."
    "\n\n"
    "No character speaks; clips carry ambient sound only.\n"
    "Narration: off — leave narratorText empty.\n\n"
    "Cast:\n"
    "Mai (character): A young woman in a red raincoat with short black hair. "
    "Voice: Soft, quick voice\n"
    "Old Harbor (location): A foggy fishing harbor at dawn\n"
    "Reuse these names exactly. Add a character only when the story needs one.\n\n"
    "Episode outline:\n"
    "1. The Pier: Mai walks to the pier.\n"
    "2. The Boat: Mai rows out to sea.\n"
    "3. The Bell: Mai rings the drowned bell.\n"
    "4. The Return: Mai sails home.\n"
    "Write part 3 now.\n\n"
    "Story so far:\n"
    "1. Mai finds a rope tied to the pier.\n"
    "2. Mai rows out to sea."
)
EXPECTED_PORTRAIT_MESSAGE = (
    "Series: Test Series\n\n"
    "Language of narration and dialogue: Japanese\n\n"
    "Episode idea:\n"
    "A storm\n\n"
    "Frame: 9:16 portrait\n"
    "Style: Photorealistic — Photorealistic photo.\n\n"
    "Write scenes whose clip lengths, each minus its first second, add up to about 12s. Give "
    "each scene the clip length its action needs, 4-30 s; a typical clip lasts 6s. The first "
    "second of every clip is cut, so a scene's narration must fit in its clip length minus 1 s."
    "\n\n"
    "Characters may speak inside clips.\n"
    "Narration: on\n\n"
    "Episode outline:\n"
    "1. The Storm: A storm hits the harbor.\n"
    "Write part 1 now."
)
EXPECTED_ANALYSIS_BLOCK = (
    "Adapt this film analysis:\n\n"
    "Character image prompts:\n## Mai\nRed coat\n\n"
    "Character voice prompts:\n## Mai\nSoft\n\n"
    "Scene prompts:\n## Scene 1\nFog\n\n"
    "Extra direction:\nSet it in winter\n\n"
    "Frame: 16:9 landscape"
)
EXPECTED_FRAMES_ENDING = "Write part 1 now.\n\nReference frames:\nframe-01.jpg\nframe-02.jpg"
EXPECTED_EMPTY_ANALYSIS_BLOCK = (
    "Adapt this film analysis:\n\n"
    "Character image prompts:\n\n\n"
    "Character voice prompts:\n\n\n"
    "Scene prompts:\n\n\n"
    "Frame: 16:9 landscape"
)


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "description": "A fishing town hides a drowned city.",
        "language": FilmLanguage.ENGLISH,
        "orientation": Orientation.LANDSCAPE,
        "style_id": "realistic",
        "clip_duration_s": 8,
        "allow_dialogue": False,
        "allow_narration": False,
    }
    return FilmProject(**{**defaults, **values})


def build_character(character_id: str, name: str, **values) -> Character:
    defaults = {
        "id": character_id,
        "name": name,
        "entity_type": EntityType.CHARACTER,
        "description": f"{name} description",
        "voice_description": None,
        "style_id": "realistic",
        "reference_status": MediaStatus.NONE,
        "reference_path": None,
    }
    return Character(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e4",
        "project_id": "p1",
        "number": 4,
        "title": "Episode 4",
        "logline": None,
        "source": EpisodeSource.IDEA,
        "idea": "The bell rings again",
        "source_job_id": None,
        "target_duration_s": 60,
        "film_script_prompt": "WRITE A SCRIPT",
    }
    return Episode(**{**defaults, **values})


def build_part(part_id: str, position: int, **values) -> EpisodePart:
    defaults = {
        "id": part_id,
        "episode_id": "e4",
        "position": position,
        "title": "The Pier",
        "plan": "Mai walks to the pier.",
        "target_duration_s": 60,
        "recap": None,
    }
    return EpisodePart(**{**defaults, **values})


def build_scene(image_prompt: str, character_names=(), **values) -> dict:
    return {
        "imagePrompt": image_prompt,
        "videoPrompt": f"{image_prompt} beats",
        "narratorText": None,
        "characterNames": list(character_names),
        **values,
    }


def build_reply(characters=(), scenes=None, **values) -> dict:
    return {
        "recap": "Mai rings the bell.",
        "characters": list(characters),
        "scenes": [build_scene("s1")] if scenes is None else scenes,
        **values,
    }


def build_written_character(name: str, reference_frame: str | None = None, **values) -> dict:
    return {
        "name": name,
        "entityType": "character",
        "description": f"{name} looks",
        "voiceDescription": None,
        "referenceFrame": reference_frame,
        **values,
    }


def build_writer(
    tmp_path, episode: Episode, project: FilmProject, cast=(), library=(), choice=CLAUDE_CHOICE
):
    part = build_part("pt1", 0, episode_id=episode.id)
    repository = MagicMock(spec=FilmRepository)
    repository.find_part.return_value = part
    repository.find_parts.return_value = [part]
    repository.find_episode.return_value = episode
    repository.find_project.return_value = project
    repository.find_style.return_value = STYLE
    repository.find_project_characters.return_value = list(cast)
    repository.find_episodes.return_value = []
    repository.count_scenes_by_episode.return_value = {}
    library_by_name = {character.name.casefold(): character for character in library}
    repository.find_character_by_name.side_effect = lambda name: library_by_name.get(
        name.casefold()
    )
    repository.save_part_script.return_value = True
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    analysis_source = AnalysisSource(
        AnalysisSourceTools(files, MagicMock(spec=JobRepository), JobStorage(tmp_path / "jobs", 1))
    )
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = choice
    ai_caller.ask_for_json.return_value = build_reply()
    writer = EpisodeScriptWriter(
        ScriptWriterTools(
            repository=repository,
            imports=FilmImports(files),
            analysis_source=analysis_source,
            ai_caller=ai_caller,
            limits=SCRIPT_LIMITS,
        )
    )
    return SimpleNamespace(writer=writer, repository=repository, ai_caller=ai_caller, files=files)


def write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def saved_script(parts):
    return parts.repository.save_part_script.call_args.args[1]


@pytest.fixture
def idea_request(tmp_path):
    cast = [
        build_character(
            "c1",
            "Mai",
            description="A young woman in a red raincoat with short black hair",
            voice_description="Soft, quick voice",
        ),
        build_character(
            "c2",
            "Old Harbor",
            entity_type=EntityType.LOCATION,
            description="A foggy fishing harbor at dawn",
        ),
    ]
    project = build_project(story_bible="Mai keeps the harbor bell.")
    parts = build_writer(tmp_path, build_episode(), project, cast=cast)
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
        build_episode(),
        build_episode(id="e5", number=5, title="Later", summary="Not yet."),
    ]
    parts.repository.count_scenes_by_episode.return_value = {"e1": 3, "e3": 2, "e5": 4}
    third_part = build_part(
        "pt3", 2, title="The Bell", plan="Mai rings the drowned bell.", target_duration_s=40
    )
    parts.repository.find_part.return_value = third_part
    parts.repository.find_parts.return_value = [
        build_part("pt1", 0, recap="Mai finds a rope tied to the pier."),
        build_part("pt2", 1, title="The Boat", plan="Mai rows out to sea."),
        third_part,
        build_part("pt4", 3, title="The Return", plan="Mai sails home.", recap="Home again."),
    ]
    parts.writer.write_part("pt3")
    return parts.ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def portrait_request(tmp_path):
    project = build_project(
        description=None,
        language=FilmLanguage.JAPANESE,
        orientation=Orientation.PORTRAIT,
        clip_duration_s=6,
        allow_dialogue=True,
        allow_narration=True,
    )
    parts = build_writer(tmp_path, build_episode(idea="A storm"), project)
    parts.repository.find_part.return_value = build_part(
        "pt1", 0, title="The Storm", plan="A storm hits the harbor.", target_duration_s=12
    )
    parts.repository.find_parts.return_value = [parts.repository.find_part.return_value]
    parts.writer.write_part("pt1")
    return parts.ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def normalised_save(tmp_path):
    mai = build_character("c1", "Mai")
    harbor = build_character("c2", "Old Harbor", entity_type=EntityType.LOCATION)
    episode = build_episode(id="e1", number=1, title="Episode 1", target_duration_s=16)
    parts = build_writer(tmp_path, episode, build_project(), cast=[mai], library=[harbor])
    parts.ai_caller.ask_for_json.return_value = build_reply(
        recap="  Mai rings the bell twice.  ",
        characters=[
            build_written_character("MAI"),
            build_written_character("old harbor", entityType="location"),
            build_written_character(
                "Ferryman", entityType="wizard", description="", voiceDescription="Hoarse whisper"
            ),
            build_written_character("  "),
        ],
        scenes=[
            build_scene("s1", ["mai", "Ferryman", "Nobody", "MAI"]),
            build_scene("s2", videoPrompt=""),
            build_scene("s3", narratorText="   "),
            build_scene("s4", durationS=12),
            build_scene("s5"),
        ],
    )
    parts.writer.write_part("pt1")
    script = saved_script(parts)
    return SimpleNamespace(script=script, ferryman=script.new_characters[0], parts=parts)


@pytest.fixture
def analysis_save(tmp_path):
    episode = build_episode(
        id="e3",
        number=3,
        source=EpisodeSource.FILM_ANALYSIS,
        source_job_id="fa-1",
        idea="Set it in winter",
        target_duration_s=8,
    )
    mai = build_character("c1", "Mai")
    harbor = build_character("c2", "Old Harbor", reference_status=MediaStatus.DONE)
    lighthouse = build_character("c9", "Lighthouse", entity_type=EntityType.LOCATION)
    parts = build_writer(
        tmp_path, episode, build_project(), cast=[mai, harbor], library=[lighthouse]
    )
    source_dir = parts.files.source_dir("p1", "e3")
    (source_dir / "images").mkdir(parents=True)
    (source_dir / "character_image_prompts.md").write_text("## Mai\nRed coat", encoding="utf-8")
    (source_dir / "character_voice_prompts.md").write_text("## Mai\nSoft", encoding="utf-8")
    (source_dir / "scene_prompts.md").write_text("## Scene 1\nFog", encoding="utf-8")
    write_file(source_dir / "images" / "frame-01.jpg", b"frame-1")
    write_file(source_dir / "images" / "frame-02.jpg", b"frame-2")
    parts.ai_caller.ask_for_json.return_value = build_reply(
        characters=[
            build_written_character("Woman in red coat", "images/frame-01.jpg"),
            build_written_character("Mai", "frame-02.jpg"),
            build_written_character("Old Harbor", "frame-02.jpg"),
            build_written_character("Ghost", "missing.jpg"),
            build_written_character("Lighthouse", "frame-01.jpg"),
        ],
        scenes=[build_scene("s1", ["Woman in red coat", "mai"])],
    )
    parts.writer.write_part("pt1")
    script = saved_script(parts)
    return SimpleNamespace(
        message=parts.ai_caller.ask_for_json.call_args.args[1].message,
        script=script,
        woman=script.new_characters[0],
        ghost=script.new_characters[1],
        files=parts.files,
    )


@pytest.fixture
def empty_analysis_message(tmp_path):
    episode = build_episode(source=EpisodeSource.FILM_ANALYSIS, source_job_id="fa-1", idea=None)
    parts = build_writer(tmp_path, episode, build_project())
    parts.writer.write_part("pt1")
    return parts.ai_caller.ask_for_json.call_args.args[1].message


@pytest.fixture
def dropped_script_files(tmp_path):
    episode = build_episode(source=EpisodeSource.FILM_ANALYSIS, source_job_id="fa-1")
    parts = build_writer(tmp_path, episode, build_project())
    write_file(parts.files.source_dir("p1", "e4") / "images" / "frame-01.jpg", b"frame-1")
    parts.ai_caller.ask_for_json.return_value = build_reply(
        characters=[build_written_character("Woman", "frame-01.jpg")]
    )
    parts.repository.save_part_script.return_value = False
    parts.writer.write_part("pt1")
    return parts.files.to_absolute(saved_script(parts).new_characters[0].reference_path)


@pytest.fixture
def failed_save(tmp_path):
    episode = build_episode(source=EpisodeSource.FILM_ANALYSIS, source_job_id="fa-1")
    parts = build_writer(tmp_path, episode, build_project())
    write_file(parts.files.source_dir("p1", "e4") / "images" / "frame-01.jpg", b"frame-1")
    parts.ai_caller.ask_for_json.return_value = build_reply(
        characters=[build_written_character("Woman", "frame-01.jpg")]
    )
    parts.repository.save_part_script.side_effect = RuntimeError("database gone")
    with pytest.raises(RuntimeError) as error:
        parts.writer.write_part("pt1")
    copied = parts.files.to_absolute(saved_script(parts).new_characters[0].reference_path)
    return SimpleNamespace(error=error.value, copied=copied)


@pytest.fixture(params=["find_part", "find_episode", "find_project"])
def missing_record_run(request, tmp_path):
    parts = build_writer(tmp_path, build_episode(), build_project())
    getattr(parts.repository, request.param).return_value = None
    parts.writer.write_part("pt1")
    return parts


@pytest.fixture
def claude_failure(tmp_path):
    parts = build_writer(tmp_path, build_episode(), build_project())
    second_part = build_part("pt2", 1)
    parts.repository.find_part.return_value = second_part
    parts.repository.find_parts.return_value = [build_part("pt1", 0), second_part]
    parts.ai_caller.ask_for_json.side_effect = AiCallError("claude failed: Overloaded")
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.write_part("pt2")
    return SimpleNamespace(error=error.value, parts=parts)


@pytest.fixture
def no_scene_failure(tmp_path):
    parts = build_writer(tmp_path, build_episode(), build_project())
    parts.ai_caller.ask_for_json.return_value = build_reply(
        scenes=[build_scene(""), build_scene("  ")]
    )
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.write_part("pt1")
    return SimpleNamespace(error=error.value, parts=parts)


def test_the_call_uses_the_episode_prompt_and_the_fixed_schema(idea_request):
    assert (idea_request.instructions, idea_request.reply_schema) == (
        "WRITE A SCRIPT",
        SCRIPT_REPLY_SCHEMA,
    )


def test_the_idea_message_carries_the_story_context_outline_and_story_so_far(idea_request):
    assert idea_request.message == EXPECTED_IDEA_MESSAGE


def test_the_message_follows_language_frame_dialogue_and_narration(portrait_request):
    assert portrait_request.message == EXPECTED_PORTRAIT_MESSAGE


def test_scenes_keep_the_valid_ones_at_positions_from_zero(normalised_save):
    assert [
        (scene.position, scene.image_prompt, scene.narrator_text)
        for scene in normalised_save.script.scenes
    ] == [(0, "s1", None), (1, "s3", None), (2, "s4", None), (3, "s5", None)]


def test_each_scene_keeps_its_clip_length_or_the_project_default(normalised_save):
    assert [scene.clip_duration_s for scene in normalised_save.script.scenes] == [8, 8, 12, 8]


def test_new_scenes_start_with_every_status_none_and_the_default_trim(normalised_save):
    assert {
        (
            scene.episode_id,
            scene.part_id,
            scene.image_status,
            scene.clip_status,
            scene.narration_status,
            scene.trim_start_ms,
            scene.trim_end_ms,
        )
        for scene in normalised_save.script.scenes
    } == {("e1", "pt1", MediaStatus.NONE, MediaStatus.NONE, MediaStatus.NONE, 1000, None)}


def test_scene_characters_resolve_against_the_cast(normalised_save):
    assert normalised_save.script.scenes[0].character_ids == ["c1", normalised_save.ferryman.id]


def test_a_library_character_is_linked_and_a_new_one_created(normalised_save):
    assert normalised_save.script.linked_character_ids == ["c2", normalised_save.ferryman.id]


def test_a_new_character_gets_the_defaults_and_a_built_prompt(normalised_save):
    ferryman = normalised_save.ferryman
    assert (
        ferryman.name,
        ferryman.entity_type,
        ferryman.description,
        ferryman.voice_description,
        ferryman.style_id,
        ferryman.reference_status,
        ferryman.origin_job_id,
        ferryman.image_prompt.startswith("Reference image of Ferryman."),
    ) == (
        "Ferryman",
        EntityType.CHARACTER,
        "Ferryman",
        "Hoarse whisper",
        "realistic",
        MediaStatus.NONE,
        None,
        True,
    )


def test_cast_characters_are_left_unchanged(normalised_save):
    assert normalised_save.script.character_values_by_id == {}


def test_the_part_gets_the_trimmed_recap(normalised_save):
    assert normalised_save.script.recap == "Mai rings the bell twice."


def test_the_script_is_saved_for_its_part(normalised_save):
    assert normalised_save.parts.repository.save_part_script.call_args.args[0] is (
        normalised_save.parts.repository.find_part.return_value
    )


def test_an_analysis_message_adapts_the_copied_analysis(analysis_save):
    assert EXPECTED_ANALYSIS_BLOCK in analysis_save.message


def test_an_analysis_message_ends_with_the_copied_frame_names(analysis_save):
    assert analysis_save.message.endswith(EXPECTED_FRAMES_ENDING)


def test_an_analysis_message_has_no_episode_idea(analysis_save):
    assert "Episode idea:" not in analysis_save.message


def test_a_new_character_takes_its_reference_frame(analysis_save):
    woman = analysis_save.woman
    assert (
        woman.reference_status,
        woman.reference_source,
        woman.reference_path,
        woman.origin_job_id,
    ) == (
        MediaStatus.DONE,
        ReferenceSource.FILM_ANALYSIS,
        f"characters/{woman.id}/reference.jpg",
        "fa-1",
    )


def test_the_reference_frame_is_copied(analysis_save):
    assert analysis_save.files.to_absolute(analysis_save.woman.reference_path).read_bytes() == (
        b"frame-1"
    )


def test_a_frame_that_was_not_copied_gives_no_reference(analysis_save):
    assert analysis_save.ghost.reference_status is MediaStatus.NONE


def test_characters_without_a_reference_take_their_frame(analysis_save):
    assert analysis_save.script.character_values_by_id == {
        "c1": {
            "reference_status": MediaStatus.DONE,
            "reference_source": ReferenceSource.FILM_ANALYSIS,
            "reference_path": "characters/c1/reference.jpg",
            "reference_error": None,
        },
        "c9": {
            "reference_status": MediaStatus.DONE,
            "reference_source": ReferenceSource.FILM_ANALYSIS,
            "reference_path": "characters/c9/reference.jpg",
            "reference_error": None,
        },
    }


def test_new_and_library_characters_are_linked_in_reply_order(analysis_save):
    assert analysis_save.script.linked_character_ids == [
        analysis_save.woman.id,
        analysis_save.ghost.id,
        "c9",
    ]


def test_a_missing_analysis_copy_sends_empty_sections(empty_analysis_message):
    assert EXPECTED_EMPTY_ANALYSIS_BLOCK in empty_analysis_message


def test_a_missing_analysis_copy_sends_no_frame_names(empty_analysis_message):
    assert empty_analysis_message.endswith("Write part 1 now.\n\nReference frames:\n(none)")


def test_a_script_that_is_not_saved_removes_its_copied_frames(dropped_script_files):
    assert not dropped_script_files.exists()


def test_a_failed_save_removes_its_copied_frames(failed_save):
    assert not failed_save.copied.exists()


def test_a_failed_save_is_raised(failed_save):
    assert str(failed_save.error) == "database gone"


def test_a_missing_part_episode_or_project_calls_nothing(missing_record_run):
    assert not missing_record_run.ai_caller.ask_for_json.called


def test_a_missing_part_episode_or_project_records_no_model(missing_record_run):
    assert not missing_record_run.repository.save_ai_used.called


def test_a_claude_failure_is_raised_with_the_part_number(claude_failure):
    assert str(claude_failure.error) == "Part 2: claude failed: Overloaded"


def test_a_claude_failure_saves_nothing(claude_failure):
    assert not claude_failure.parts.repository.save_part_script.called


def test_a_reply_without_scenes_fails_with_the_part_number(no_scene_failure):
    assert str(no_scene_failure.error) == "Part 1: claude returned no scenes"


def test_a_reply_without_scenes_saves_nothing(no_scene_failure):
    assert not no_scene_failure.parts.repository.save_part_script.called


@pytest.fixture
def gemini_episode_run(tmp_path):
    parts = build_writer(tmp_path, build_episode(), build_project(), choice=GEMINI_CHOICE)
    parts.ai_caller.ask_for_json.return_value = build_reply(scenes=[])
    with pytest.raises(EpisodeStepFailedError) as error:
        parts.writer.write_part("pt1")
    return SimpleNamespace(error=error.value, parts=parts)


def test_the_script_is_asked_of_the_film_script_model(gemini_episode_run):
    gemini_episode_run.parts.ai_caller.find_model.assert_called_once_with(AiStepGroup.FILM_SCRIPT)


def test_the_script_is_asked_with_the_chosen_model_within_its_limits(gemini_episode_run):
    call_args = gemini_episode_run.parts.ai_caller.ask_for_json.call_args.args
    assert (call_args[0], call_args[2]) == (GEMINI_CHOICE, SCRIPT_LIMITS)


def test_the_model_is_recorded_before_the_call(gemini_episode_run):
    gemini_episode_run.parts.repository.save_ai_used.assert_called_once_with(
        "e4", EpisodeStep.WRITING_SCRIPT, GEMINI_CHOICE
    )


def test_a_gemini_reply_without_scenes_names_gemini(gemini_episode_run):
    assert str(gemini_episode_run.error) == "Part 1: gemini returned no scenes"
