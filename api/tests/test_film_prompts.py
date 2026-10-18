from types import SimpleNamespace

import pytest

from app.modules.films.film_prompts import (
    AMBIENT_AUDIO_LINE,
    DIALOGUE_AUDIO_LINE,
    CharacterVoice,
    ClipPromptParts,
    build_character_image_prompt,
    build_clip_prompt,
    build_scene_image_prompt,
    build_thumbnail_prompt,
    pick_thumbnail_character_ids,
    to_character_aspect,
    to_project_aspect,
)
from app.modules.films.models import EntityType, Orientation, Scene, Style

VIDEO_PROMPT = "0-3s: Mai walks. 3-6s: She stops. 6-8s: She looks up."
MAI_VOICE = CharacterVoice("Mai", "Soft, quick voice")
HARBOR_VOICE = CharacterVoice("Old Harbor", None)


def build_style(**overrides) -> Style:
    values = {
        "id": "film_still",
        "name": "Film Still",
        "is_builtin": False,
        "style_instruction": "Shot on 35mm film.",
        "negative_prompt": "No text.",
        "scene_prefix": "Cinematic still,",
        "lighting": "Studio lighting, highly detailed",
    }
    return Style(**{**values, **overrides})


def build_scene(character_ids: list[str]) -> Scene:
    return Scene(character_ids=character_ids)


@pytest.fixture(
    params=[
        (EntityType.CHARACTER, "9:16"),
        (EntityType.LOCATION, "16:9"),
        (EntityType.CREATURE, "9:16"),
        (EntityType.VISUAL_ASSET, "9:16"),
        (EntityType.GENERIC_TROOP, "9:16"),
        (EntityType.FACTION, "9:16"),
    ]
)
def character_aspect(request):
    entity_type, expected = request.param
    return SimpleNamespace(actual=to_character_aspect(entity_type), expected=expected)


@pytest.fixture(params=[(Orientation.LANDSCAPE, "16:9"), (Orientation.PORTRAIT, "9:16")])
def project_aspect(request):
    orientation, expected = request.param
    return SimpleNamespace(actual=to_project_aspect(orientation), expected=expected)


@pytest.fixture
def character_prompt():
    return build_character_image_prompt(
        "  a young woman in a red raincoat  ", EntityType.CHARACTER, build_style()
    )


@pytest.fixture
def location_prompt_without_negative():
    return build_character_image_prompt(
        "a foggy harbor", EntityType.LOCATION, build_style(negative_prompt=None)
    )


@pytest.fixture
def scene_prompt():
    return build_scene_image_prompt(build_style(), "Mai stands on the pier")


@pytest.fixture
def scene_prompt_without_prefix():
    return build_scene_image_prompt(build_style(scene_prefix=None), "Mai stands on the pier")


@pytest.fixture
def thumbnail_prompt():
    return build_thumbnail_prompt(build_style(), "Mai holds the compass")


@pytest.fixture
def dialogue_clip_prompt():
    return build_clip_prompt(ClipPromptParts(VIDEO_PROMPT, True, [MAI_VOICE, HARBOR_VOICE]))


@pytest.fixture
def ambient_clip_prompt():
    return build_clip_prompt(ClipPromptParts(VIDEO_PROMPT, False, [MAI_VOICE, HARBOR_VOICE]))


@pytest.fixture
def clip_prompt_with_audio_line():
    return build_clip_prompt(
        ClipPromptParts("0-3s: Mai walks. Audio: waves crash.", True, [MAI_VOICE])
    )


@pytest.fixture
def clip_prompt_with_music_line():
    return build_clip_prompt(ClipPromptParts("0-3s: Mai walks. Music: none.", False, []))


@pytest.fixture
def clip_prompt_without_voices():
    return build_clip_prompt(ClipPromptParts(VIDEO_PROMPT, True, [HARBOR_VOICE]))


@pytest.fixture
def thumbnail_characters():
    return pick_thumbnail_character_ids(
        [
            build_scene(["c4", "c1", "c1"]),
            build_scene(["c2", "c1"]),
            build_scene(["c1", "c3"]),
            build_scene(["c3", "c4"]),
            build_scene(["c2"]),
        ]
    )


def test_character_aspect_follows_the_entity_type(character_aspect):
    assert character_aspect.actual == character_aspect.expected


def test_project_aspect_follows_the_orientation(project_aspect):
    assert project_aspect.actual == project_aspect.expected


def test_character_prompt_joins_description_style_composition_and_lighting(character_prompt):
    assert character_prompt == (
        "Reference image of a young woman in a red raincoat. Shot on 35mm film. No text. "
        "full body, head to toe, standing straight, centered, front-facing, neutral background "
        "Studio lighting, highly detailed"
    )


def test_character_prompt_skips_a_missing_negative_prompt(location_prompt_without_negative):
    assert location_prompt_without_negative == (
        "Reference image of a foggy harbor. Shot on 35mm film. establishing shot of the whole "
        "place, level horizon, clear focal point, depth Studio lighting, highly detailed"
    )


def test_scene_prompt_starts_with_the_style_prefix(scene_prompt):
    assert scene_prompt == "Cinematic still, Mai stands on the pier"


def test_scene_prompt_without_prefix_is_the_image_prompt(scene_prompt_without_prefix):
    assert scene_prompt_without_prefix == "Mai stands on the pier"


def test_thumbnail_prompt_starts_with_the_style_prefix(thumbnail_prompt):
    assert thumbnail_prompt == "Cinematic still, Mai holds the compass"


def test_dialogue_clip_prompt_lists_voices_and_keeps_dialogue(dialogue_clip_prompt):
    assert dialogue_clip_prompt == "\n".join(
        [VIDEO_PROMPT, "Character voices: Mai: Soft, quick voice.", DIALOGUE_AUDIO_LINE]
    )


def test_ambient_clip_prompt_has_no_voices_and_ambient_audio(ambient_clip_prompt):
    assert ambient_clip_prompt == "\n".join([VIDEO_PROMPT, AMBIENT_AUDIO_LINE])


def test_clip_prompt_with_an_audio_line_adds_none(clip_prompt_with_audio_line):
    assert clip_prompt_with_audio_line == "\n".join(
        ["0-3s: Mai walks. Audio: waves crash.", "Character voices: Mai: Soft, quick voice."]
    )


def test_clip_prompt_with_a_music_line_adds_no_audio_line(clip_prompt_with_music_line):
    assert clip_prompt_with_music_line == "0-3s: Mai walks. Music: none."


def test_clip_prompt_without_voice_descriptions_has_no_voices_line(clip_prompt_without_voices):
    assert clip_prompt_without_voices == "\n".join([VIDEO_PROMPT, DIALOGUE_AUDIO_LINE])


def test_thumbnail_characters_are_the_three_listed_in_the_most_scenes(thumbnail_characters):
    assert thumbnail_characters == ["c1", "c4", "c2"]
