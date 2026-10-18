from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue, SceneOrderContext
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    Scene,
    Style,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import GenerationKind
from app.modules.media_generation.service import GenerationService, GenerationTargetIds
from app.modules.providers.provider_catalog import MediaKind, ProviderId

UPLOAD_MAX_MB = 20
MAI = Character(
    id="c1",
    name="Mai",
    entity_type=EntityType.CHARACTER,
    voice_description="Soft, quick voice",
    reference_status=MediaStatus.DONE,
    reference_path="characters/c1/reference.png",
    image_prompt="Reference image of Mai",
)
HARBOR = Character(
    id="c2",
    name="Old Harbor",
    entity_type=EntityType.LOCATION,
    voice_description=None,
    reference_status=MediaStatus.DONE,
    reference_path="characters/c2/reference.png",
)
STRANGER = Character(
    id="c3",
    name="Stranger",
    entity_type=EntityType.CHARACTER,
    reference_status=MediaStatus.NONE,
    reference_path=None,
)
PROJECT = FilmProject(
    id="p1",
    style_id="film_still",
    language=FilmLanguage.ENGLISH,
    orientation=Orientation.LANDSCAPE,
    clip_duration_s=8,
    allow_dialogue=True,
)
SCENE = Scene(
    id="s1",
    image_prompt="Mai stands on the pier",
    video_prompt="0-3s: Mai walks.",
    narrator_text="The fog never lifts here.",
    character_ids=["c1", "c2", "c3", "missing"],
    clip_duration_s=12,
    image_path="projects/p1/episodes/e1/scenes/s1/image.png",
)
STYLE = Style(
    id="film_still",
    style_instruction="Shot on 35mm film.",
    scene_prefix="Cinematic still,",
    lighting="Studio lighting",
)
EPISODE = Episode(id="e1", music_prompt="Slow cello", thumbnail_prompt="Mai holds the compass")


def build_queue(tmp_path, style: Style | None = STYLE):
    repository = MagicMock(spec=FilmRepository)
    repository.find_style.return_value = style
    repository.find_characters_by_ids.side_effect = lambda ids: {
        character.id: character for character in (MAI, HARBOR, STRANGER) if character.id in ids
    }
    generation_service = MagicMock(spec=GenerationService)
    generation_service.queue.side_effect = lambda order: order
    pick_speech_provider = MagicMock(return_value=ProviderId.ELEVENLABS)
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    queue = FilmMediaQueue(repository, files, generation_service, pick_speech_provider)
    return SimpleNamespace(queue=queue, root=tmp_path / "films")


@pytest.fixture
def parts(tmp_path):
    return build_queue(tmp_path)


@pytest.fixture
def scene_context():
    return SceneOrderContext(PROJECT, "e1", SCENE)


@pytest.fixture
def character_order(parts):
    return parts.queue.queue_character_image(PROJECT, HARBOR, "e1")


@pytest.fixture
def character_edit_order(parts):
    return parts.queue.queue_character_edit(PROJECT, MAI, "Give her a hat")


@pytest.fixture
def scene_image_order(parts, scene_context):
    return parts.queue.queue_scene_image(scene_context)


@pytest.fixture
def scene_edit_order(parts, scene_context):
    return parts.queue.queue_scene_edit(scene_context, "Make it night")


@pytest.fixture
def clip_order(parts, scene_context):
    return parts.queue.queue_scene_clip(scene_context)


@pytest.fixture
def narration_order(parts, scene_context):
    voice = VoiceTemplate(
        name="narrator-en",
        sample_path="voices/v1/sample.wav",
        sample_text="The solar warning flashes.",
        sample_duration_ms=65000,
        consent_path="voices/v1/consent.wav",
        provider_voices={"elevenlabs": "voice-x"},
    )
    return parts.queue.queue_narration(scene_context, voice)


@pytest.fixture
def narration_order_without_copy(parts, scene_context):
    voice = VoiceTemplate(
        name="narrator-en",
        sample_path="voices/v1/sample.wav",
        sample_text="The solar warning flashes.",
        sample_duration_ms=4000,
        consent_path=None,
        provider_voices={},
    )
    return parts.queue.queue_narration(scene_context, voice)


@pytest.fixture
def music_order(parts):
    return parts.queue.queue_music(PROJECT, EPISODE, 63)


@pytest.fixture
def thumbnail_order(parts):
    scenes = [Scene(character_ids=["c2"]), Scene(character_ids=["c2", "c1"])]
    return parts.queue.queue_thumbnail(PROJECT, EPISODE, scenes, 2)


@pytest.fixture
def missing_style_error(tmp_path, scene_context):
    parts = build_queue(tmp_path, style=None)
    with pytest.raises(LookupError) as error:
        parts.queue.queue_scene_image(scene_context)
    return error.value


def test_character_image_uses_the_type_aspect(character_order):
    assert character_order.kind is GenerationKind.CHARACTER_IMAGE
    assert character_order.media_kind is MediaKind.IMAGE
    assert character_order.target_ids == GenerationTargetIds(
        project_id="p1", episode_id="e1", character_id="c2"
    )
    assert character_order.params == {"aspect": "16:9"}


def test_character_edit_sends_the_current_reference(parts, character_edit_order):
    assert character_edit_order.kind is GenerationKind.EDIT_IMAGE
    assert character_edit_order.prompt == "Give her a hat"
    assert character_edit_order.input_paths == {
        "sourceImage": str(parts.root / "characters/c1/reference.png")
    }
    assert character_edit_order.params == {"aspect": "9:16"}


def test_scene_image_sends_done_references_in_cast_order(parts, scene_image_order):
    assert scene_image_order.prompt == "Cinematic still, Mai stands on the pier"
    assert scene_image_order.input_paths == {
        "references": [
            str(parts.root / "characters/c1/reference.png"),
            str(parts.root / "characters/c2/reference.png"),
        ]
    }
    assert scene_image_order.params == {
        "referenceNames": ["Mai", "Old Harbor"],
        "referenceKinds": ["character", "location"],
        "aspect": "16:9",
    }
    assert scene_image_order.target_ids == GenerationTargetIds(
        project_id="p1", episode_id="e1", scene_id="s1"
    )


def test_scene_edit_adds_the_scene_image(parts, scene_edit_order):
    assert scene_edit_order.kind is GenerationKind.EDIT_IMAGE
    assert scene_edit_order.media_kind is MediaKind.EDIT_IMAGE
    assert scene_edit_order.input_paths["sourceImage"] == str(
        parts.root / "projects/p1/episodes/e1/scenes/s1/image.png"
    )
    assert len(scene_edit_order.input_paths["references"]) == 2


def test_clip_uses_the_scene_clip_length_and_voices(parts, clip_order):
    assert clip_order.media_kind is MediaKind.VIDEO
    assert clip_order.prompt.splitlines()[1] == "Character voices: Mai: Soft, quick voice."
    assert clip_order.input_paths == {
        "startFrame": str(parts.root / "projects/p1/episodes/e1/scenes/s1/image.png")
    }
    assert clip_order.params == {"clipLengthS": 12, "aspect": "16:9"}


def test_narration_sends_the_voice_and_its_provider_copy(parts, narration_order):
    assert narration_order.kind is GenerationKind.NARRATION
    assert narration_order.prompt == "The fog never lifts here."
    assert narration_order.input_paths == {
        "voiceSample": str(parts.root / "voices/v1/sample.wav"),
        "consentClip": str(parts.root / "voices/v1/consent.wav"),
    }
    assert narration_order.params == {
        "voiceName": "narrator-en",
        "sampleDurationS": 65.0,
        "sampleText": "The solar warning flashes.",
        "language": "en",
        "providerVoiceId": "voice-x",
    }


def test_narration_without_a_copy_or_consent_sends_the_sample_only(narration_order_without_copy):
    assert set(narration_order_without_copy.input_paths) == {"voiceSample"}
    assert "providerVoiceId" not in narration_order_without_copy.params


def test_music_asks_for_the_film_length(music_order):
    assert music_order.kind is GenerationKind.MUSIC
    assert music_order.prompt == "Slow cello"
    assert music_order.params == {"minLengthS": 63}
    assert music_order.target_ids == GenerationTargetIds(project_id="p1", episode_id="e1")


def test_thumbnail_is_16_9_with_its_candidate(thumbnail_order):
    assert thumbnail_order.prompt == "Cinematic still, Mai holds the compass"
    assert thumbnail_order.params["aspect"] == "16:9"
    assert thumbnail_order.params["candidate"] == 2
    assert thumbnail_order.params["referenceNames"] == ["Old Harbor", "Mai"]


def test_a_missing_style_raises(missing_style_error):
    assert missing_style_error.args == ("film_still",)
