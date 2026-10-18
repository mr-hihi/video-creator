import pytest

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import EntityType
from app.modules.films.script_replies import (
    SCRIPT_REPLY_SCHEMA,
    ScriptShape,
    WrittenCharacter,
    WrittenScene,
    normalize_script_reply,
    to_character_ids,
)

SHAPE = ScriptShape(default_clip_duration_s=8, episode_number=1, ai_name="gemini")
SIX_SECOND_SHAPE = ScriptShape(default_clip_duration_s=6, episode_number=1, ai_name="gemini")


def build_scene(image_prompt: str, **values) -> dict:
    return {
        "imagePrompt": image_prompt,
        "videoPrompt": "0-3s: beat",
        "narratorText": "A line",
        "characterNames": [],
        "durationS": 8,
        **values,
    }


@pytest.fixture
def messy_script():
    reply = {
        "title": "  ",
        "logline": " Mai hears a bell. ",
        "characters": [
            {"name": "MAI", "entityType": "character", "description": "Mai"},
            {"name": "old harbor", "entityType": "location", "description": "A harbor"},
            {
                "name": "Ferryman",
                "entityType": "wizard",
                "description": "",
                "voiceDescription": "Hoarse whisper",
                "referenceFrame": None,
            },
            {"name": "  ", "entityType": "character", "description": "Nobody"},
        ],
        "scenes": [
            build_scene("s1", characterNames=["mai", "Ferryman", "Nobody", "MAI"]),
            build_scene("s2", videoPrompt=""),
            build_scene("s3", narratorText="   "),
            build_scene("s4"),
            build_scene("s5"),
        ],
        "musicPrompt": " Slow cello ",
        "thumbnailPrompt": "",
    }
    return normalize_script_reply(reply, SHAPE)


@pytest.fixture
def bare_script():
    reply = {
        "title": "T" * 200,
        "characters": [
            "not a mapping",
            {"name": "Lantern", "entityType": " Visual_Asset ", "referenceFrame": "f.jpg"},
            {"name": "LANTERN", "entityType": "location", "description": "Second"},
        ],
        "scenes": [
            "not a mapping",
            build_scene("only", narratorText="n" * 1200, characterNames="Lantern"),
            build_scene("   "),
        ],
    }
    return normalize_script_reply(reply, SHAPE)


@pytest.fixture
def crowded_script():
    reply = {"scenes": [build_scene(f"s{number}") for number in range(1, 82)]}
    return normalize_script_reply(reply, SHAPE)


@pytest.fixture
def timed_script():
    scenes = [
        build_scene(f"s{number}", durationS=duration_s)
        for number, duration_s in enumerate([12.6, 2, 45, "10", True, None, float("nan")])
    ]
    del scenes[5]["durationS"]
    return normalize_script_reply({"scenes": scenes}, SIX_SECOND_SHAPE)


@pytest.fixture(params=[{}, {"scenes": "none"}, {"scenes": [build_scene(" "), build_scene("")]}])
def no_scenes_error(request):
    with pytest.raises(EpisodeStepFailedError) as error:
        normalize_script_reply(request.param, SHAPE)
    return error.value


@pytest.fixture
def resolved_ids():
    return to_character_ids(
        ["mai", "Ferryman", "Nobody", "MAI"], {"mai": "c-mai", "ferryman": "c-ferry"}
    )


def test_blank_scenes_are_dropped(messy_script):
    assert [scene.image_prompt for scene in messy_script.scenes] == ["s1", "s3", "s4", "s5"]


def test_only_the_first_80_scenes_are_kept(crowded_script):
    assert [scene.image_prompt for scene in crowded_script.scenes] == [
        f"s{number}" for number in range(1, 81)
    ]


def test_scene_lengths_are_rounded_into_range_or_take_the_project_default(timed_script):
    assert [scene.clip_duration_s for scene in timed_script.scenes] == [13, 4, 30, 6, 6, 6, 6]


def test_blank_narration_becomes_null(messy_script):
    assert messy_script.scenes[1].narrator_text is None


def test_scene_character_names_are_kept_raw_for_resolution(messy_script):
    assert messy_script.scenes[0] == WrittenScene(
        image_prompt="s1",
        video_prompt="0-3s: beat",
        narrator_text="A line",
        character_names=("mai", "Ferryman", "Nobody", "MAI"),
        clip_duration_s=8,
    )


def test_blank_title_falls_back_to_the_episode_number(messy_script):
    assert messy_script.title == "Episode 1"


def test_texts_are_trimmed_and_blank_ones_are_null(messy_script):
    assert (messy_script.logline, messy_script.music_prompt, messy_script.thumbnail_prompt) == (
        "Mai hears a bell.",
        "Slow cello",
        None,
    )


def test_characters_with_a_name_are_kept_with_defaults(messy_script):
    assert messy_script.characters == (
        WrittenCharacter("MAI", EntityType.CHARACTER, "Mai", None, None),
        WrittenCharacter("old harbor", EntityType.LOCATION, "A harbor", None, None),
        WrittenCharacter("Ferryman", EntityType.CHARACTER, "Ferryman", "Hoarse whisper", None),
    )


def test_a_long_title_is_cut_to_150(bare_script):
    assert bare_script.title == "T" * 150


def test_missing_texts_are_null(bare_script):
    assert (bare_script.logline, bare_script.music_prompt) == (None, None)


def test_a_repeated_character_name_keeps_the_first_entry(bare_script):
    assert bare_script.characters == (
        WrittenCharacter("Lantern", EntityType.VISUAL_ASSET, "Lantern", None, "f.jpg"),
    )


def test_narration_is_cut_to_1000_and_names_must_be_a_list(bare_script):
    assert bare_script.scenes == (
        WrittenScene(
            image_prompt="only",
            video_prompt="0-3s: beat",
            narrator_text="n" * 1000,
            character_names=(),
            clip_duration_s=8,
        ),
    )


def test_no_usable_scene_fails_the_step(no_scenes_error):
    assert str(no_scenes_error) == "gemini returned no scenes"


def test_scene_names_resolve_case_insensitively_without_unknowns_or_repeats(resolved_ids):
    assert resolved_ids == ["c-mai", "c-ferry"]


def test_the_reply_schema_requires_the_fixed_shape():
    assert SCRIPT_REPLY_SCHEMA["required"] == [
        "title",
        "logline",
        "characters",
        "scenes",
        "musicPrompt",
        "thumbnailPrompt",
    ]


def test_every_scene_of_the_reply_states_its_clip_length():
    assert SCRIPT_REPLY_SCHEMA["properties"]["scenes"]["items"]["required"] == [
        "imagePrompt",
        "videoPrompt",
        "narratorText",
        "characterNames",
        "durationS",
    ]
