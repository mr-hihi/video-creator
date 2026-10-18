import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.films.models import EntityType, Orientation, Scene, Style

LANDSCAPE_ASPECT = "16:9"
PORTRAIT_ASPECT = "9:16"
THUMBNAIL_ASPECT = LANDSCAPE_ASPECT
THUMBNAIL_CHARACTER_LIMIT = 3
CHARACTER_PROMPT_TEMPLATE = "Reference image of {description}."
CHARACTER_VOICES_LABEL = "Character voices:"
DIALOGUE_AUDIO_LINE = (
    "Audio: no background music. Keep character dialogue and natural ambient sounds."
)
AMBIENT_AUDIO_LINE = (
    "Audio: natural ambient sounds only, no background music, no narration, no voiceover."
)
AUDIO_MARKERS = ("Audio:", "Music:")
WHITESPACE = re.compile(r"\s+")
CHARACTER_COMPOSITION = (
    "full body, head to toe, standing straight, centered, front-facing, neutral background"
)
TROOP_COMPOSITION = "tactical pose, full or three-quarter body, centered, neutral background"


@dataclass(frozen=True)
class Composition:
    text: str
    aspect: str


COMPOSITIONS_BY_TYPE = {
    EntityType.CHARACTER: Composition(CHARACTER_COMPOSITION, PORTRAIT_ASPECT),
    EntityType.LOCATION: Composition(
        "establishing shot of the whole place, level horizon, clear focal point, depth",
        LANDSCAPE_ASPECT,
    ),
    EntityType.CREATURE: Composition(
        "full body in its natural stance, centered, neutral background", PORTRAIT_ASPECT
    ),
    EntityType.VISUAL_ASSET: Composition(
        "the whole object, angle showing its features, centered, neutral background",
        PORTRAIT_ASPECT,
    ),
    EntityType.GENERIC_TROOP: Composition(TROOP_COMPOSITION, PORTRAIT_ASPECT),
    EntityType.FACTION: Composition(TROOP_COMPOSITION, PORTRAIT_ASPECT),
}
ASPECTS_BY_ORIENTATION = {
    Orientation.LANDSCAPE: LANDSCAPE_ASPECT,
    Orientation.PORTRAIT: PORTRAIT_ASPECT,
}


@dataclass(frozen=True)
class CharacterVoice:
    name: str
    voice_description: str | None


@dataclass(frozen=True)
class ClipPromptParts:
    video_prompt: str
    allow_dialogue: bool
    voices: Sequence[CharacterVoice]


def to_character_aspect(entity_type: EntityType) -> str:
    return COMPOSITIONS_BY_TYPE[entity_type].aspect


def to_project_aspect(orientation: Orientation) -> str:
    return ASPECTS_BY_ORIENTATION[orientation]


def build_character_image_prompt(description: str, entity_type: EntityType, style: Style) -> str:
    parts = [
        CHARACTER_PROMPT_TEMPLATE.format(description=description.strip()),
        style.style_instruction,
        style.negative_prompt or "",
        COMPOSITIONS_BY_TYPE[entity_type].text,
        style.lighting,
    ]
    return _join_words(parts)


def build_scene_image_prompt(style: Style, image_prompt: str) -> str:
    return _join_words([style.scene_prefix or "", image_prompt])


def build_thumbnail_prompt(style: Style, thumbnail_prompt: str) -> str:
    return _join_words([style.scene_prefix or "", thumbnail_prompt])


def build_clip_prompt(parts: ClipPromptParts) -> str:
    lines = [parts.video_prompt.strip()]
    voice_lines = [
        f"{voice.name}: {voice.voice_description.strip()}."
        for voice in parts.voices
        if voice.voice_description and voice.voice_description.strip()
    ]
    if parts.allow_dialogue and voice_lines:
        lines.append(" ".join([CHARACTER_VOICES_LABEL, *voice_lines]))
    if not any(marker in parts.video_prompt for marker in AUDIO_MARKERS):
        lines.append(DIALOGUE_AUDIO_LINE if parts.allow_dialogue else AMBIENT_AUDIO_LINE)
    return "\n".join(lines)


def pick_thumbnail_character_ids(scenes: Sequence[Scene]) -> list[str]:
    counts = Counter(
        character_id for scene in scenes for character_id in dict.fromkeys(scene.character_ids)
    )
    first_seen = {
        character_id: index
        for index, character_id in reversed(
            list(enumerate(cid for scene in scenes for cid in scene.character_ids))
        )
    }
    ranked = sorted(
        counts, key=lambda character_id: (-counts[character_id], first_seen[character_id])
    )
    return ranked[:THUMBNAIL_CHARACTER_LIMIT]


def _join_words(parts: Sequence[str]) -> str:
    return WHITESPACE.sub(" ", " ".join(part.strip() for part in parts if part.strip())).strip()
