from __future__ import annotations

import json
import math
import re
from typing import Any

from mock_state import AskView

MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
LINE_TIME_PATTERN = re.compile(r"^\[(\d+)ms\]", re.MULTILINE)
FRAME_LABEL_PATTERN = re.compile(r"^\[(\d+)ms\]$")
WINDOW_PATTERN = re.compile(
    r"runs from (\S+) to (\S+)\. Choose at most (\d+) key moments", re.IGNORECASE
)
MAX_MOMENTS_PATTERN = re.compile(r"Choose at most (\d+) key moments", re.IGNORECASE)
TARGET_LENGTH_PATTERN = re.compile(r"add up to about (\d+)s", re.IGNORECASE)
TYPICAL_CLIP_PATTERN = re.compile(r"a typical clip lasts (\d+)s", re.IGNORECASE)
NAMED_LINE_PATTERN = re.compile(r"^(.+?) \(([^)]+)\)")
PART_NUMBER_PATTERN = re.compile(r"Write part (\d+) now\.")
EPISODE_LINE_PATTERN = re.compile(r"^Episode (\d+): ", re.MULTILINE)
NO_ITEMS_LINE = "(none)"
NARRATION_OFF_LINE = "Narration: off"
CHARACTERS_HEADING = "Characters:\n"
MAX_SCENE_PROMPT_HEADINGS = 5
DEFAULT_SCENE_COUNT = 3
DEFAULT_CLIP_LENGTH_S = 8
CUT_HEAD_S = 1
MAX_PART_LENGTH_S = 600
DEFAULT_EPISODE_LENGTH_S = 60


def build_scenario_answer(ask: AskView, rule: dict[str, Any]) -> str:
    if "text" in rule:
        return str(rule["text"])
    if "reply" in rule:
        return json.dumps(rule["reply"], ensure_ascii=False)
    if "chunks" in rule:
        return "".join(rule["chunks"])
    return build_answer(ask)


def build_answer(ask: AskView) -> str:
    if ask.reply_schema is None:
        return build_markdown_answer(ask)
    return json.dumps(build_reply(ask), ensure_ascii=False)


def build_reply(ask: AskView) -> dict[str, Any]:
    properties = ask.reply_schema.get("properties", {})
    item_properties = find_item_properties(properties)
    if "moments" in properties:
        return build_outline(ask)
    if "shots" in properties:
        return build_shots(ask, properties)
    if "assets" in properties and "changed" in item_properties.get("assets", {}):
        return build_localization(ask)
    if "assets" in properties:
        return build_assets(ask, properties)
    if "parts" in properties:
        return build_film_outline(ask)
    if "storyBible" in properties:
        return build_story_bible(ask)
    if "characters" in properties:
        return build_film_script(ask, properties)
    if "shotId" in item_properties.get("scenes", {}):
        return build_clone_script(ask)
    return fill_schema(ask.reply_schema)


def find_item_properties(properties: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        name: schema.get("items", {}).get("properties", {})
        for name, schema in properties.items()
        if schema.get("type") == "array"
    }


def build_outline(ask: AskView) -> dict[str, Any]:
    window = WINDOW_PATTERN.search(ask.message)
    max_moments_match = window or MAX_MOMENTS_PATTERN.search(ask.message)
    max_moments = int(max_moments_match.groups()[-1]) if max_moments_match else 1
    start_ms = clock_to_ms(window.group(1)) if window else 0
    line_times = [int(found) for found in LINE_TIME_PATTERN.findall(ask.message)]
    frame_times = [
        int(found.group(1))
        for found in (FRAME_LABEL_PATTERN.match(label) for label in ask.image_labels)
        if found
    ]
    moment_times = pick_evenly(sorted({*line_times, *frame_times}) or [start_ms], max_moments)
    is_first_part = start_ms == 0
    return {
        "title": "Mock video title"
        if is_first_part
        else f"Mock title of the part from {ms_to_clock(start_ms)}",
        "summary": (
            f"Mock summary written by {ask.ai} from {len(line_times)} transcript lines and "
            f"{len(frame_times)} frames."
        )
        if is_first_part
        else f"Mock summary of the part from {ms_to_clock(start_ms)}.",
        "moments": [
            {"atMs": at_ms, "title": f"Mock moment at {ms_to_clock(at_ms)}"}
            for at_ms in moment_times
        ],
    }


def build_assets(ask: AskView, properties: dict[str, Any]) -> dict[str, Any]:
    kinds = find_item_enum(properties, "assets", "kind") or [
        "character",
        "costume",
        "prop",
        "location",
    ]
    frames = ask.image_labels or []
    names_by_kind = {
        "character": "Mock Hero",
        "costume": "Mock Red Coat",
        "prop": "Mock Lantern",
        "location": "Mock Harbor",
    }
    return {
        "assets": [
            {
                "kind": kind,
                "name": names_by_kind.get(kind, f"Mock {kind}"),
                "description": f"A {kind} seen in the frames, described by the mock.",
                "culture": "Japan",
                "period": "1990s",
                "frames": frames[: index + 1],
            }
            for index, kind in enumerate(kinds)
        ]
    }


def build_shots(ask: AskView, properties: dict[str, Any]) -> dict[str, Any]:
    shot_sizes = find_item_enum(properties, "shots", "shotSize") or ["medium"]
    camera_angles = find_item_enum(properties, "shots", "cameraAngle") or ["eye_level"]
    asset_names = [name for name, _ in read_named_lines(ask.message, "Assets")]
    return {
        "shots": [
            {
                "frame": label,
                "shotSize": shot_sizes[index % len(shot_sizes)],
                "cameraAngle": camera_angles[index % len(camera_angles)],
                "emotion": "calm",
                "action": f"Mock action seen in {label}.",
                "assetNames": asset_names[: 1 + index % max(1, len(asset_names))],
            }
            for index, label in enumerate(ask.image_labels)
        ]
    }


def build_localization(ask: AskView) -> dict[str, Any]:
    candidates = [name for name, _ in read_named_lines(ask.message, "Candidates")]
    return {
        "assets": [
            {
                "name": name,
                "changed": index == 0,
                "localizedName": f"Local {name}" if index == 0 else "",
                "localizedDescription": f"{name}, moved to the target country by the mock."
                if index == 0
                else "",
                "note": "Changed by the mock." if index == 0 else "",
            }
            for index, name in enumerate(candidates)
        ]
    }


def build_clone_script(ask: AskView) -> dict[str, Any]:
    shot_ids = [line.split(" · ", 1)[0].strip() for line in read_block(ask.message, "Shots")]
    return {
        "title": "Mock clone script",
        "logline": "A mock retelling, shot by shot.",
        "scenes": [
            {
                "shotId": shot_id,
                "description": f"Mock scene for shot {index + 1}.",
                "dialogue": f"Mock Hero: Line {index + 1}.",
                "imagePrompt": f"Mock image prompt for shot {index + 1}, medium shot, soft light.",
            }
            for index, shot_id in enumerate(shot_ids)
        ],
    }


def build_film_script(ask: AskView, properties: dict[str, Any]) -> dict[str, Any]:
    target_match = TARGET_LENGTH_PATTERN.search(ask.message)
    clip_match = TYPICAL_CLIP_PATTERN.search(ask.message)
    clip_length_s = int(clip_match.group(1)) if clip_match else DEFAULT_CLIP_LENGTH_S
    scene_count = (
        math.ceil(int(target_match.group(1)) / (clip_length_s - CUT_HEAD_S))
        if target_match
        else DEFAULT_SCENE_COUNT
    )
    entity_types = find_item_enum(properties, "characters", "entityType") or ["human"]
    cast_names = [name for name, _ in read_named_lines(ask.message, "Cast")]
    reference_frames = read_block(ask.message, "Reference frames")
    character_name = cast_names[0] if cast_names else "Mock Keeper"
    has_narration = NARRATION_OFF_LINE not in ask.message
    part_match = PART_NUMBER_PATTERN.search(ask.message)
    part_number = part_match.group(1) if part_match else "1"
    return {
        "recap": f"Mock recap of part {part_number}: {character_name} reaches the shore.",
        "characters": [
            {
                "name": character_name,
                "entityType": entity_types[0],
                "description": "A weathered keeper in a grey wool coat.",
                "voiceDescription": "Low, calm, slow.",
                "referenceFrame": reference_frames[0] if reference_frames else None,
            }
        ],
        "scenes": [
            {
                "imagePrompt": f"Mock scene {number}: {character_name} on a shore, wide shot.",
                "videoPrompt": f"0-3s waves; 3-6s {character_name} turns; 6-8s push in ({number}).",
                "narratorText": f"Mock narration for scene {number}." if has_narration else None,
                "characterNames": [character_name],
                "durationS": clip_length_s,
            }
            for number in range(1, scene_count + 1)
        ],
    }


def build_film_outline(ask: AskView) -> dict[str, Any]:
    target_match = TARGET_LENGTH_PATTERN.search(ask.message)
    target_s = int(target_match.group(1)) if target_match else DEFAULT_EPISODE_LENGTH_S
    part_count = math.ceil(target_s / MAX_PART_LENGTH_S)
    return {
        "title": "Mock episode",
        "logline": "A mock episode written for the test stack.",
        "parts": [
            {
                "title": f"Mock part {number}",
                "plan": f"Mock plan for part {number}.",
                "durationS": round(target_s / part_count),
            }
            for number in range(1, part_count + 1)
        ],
        "musicPrompt": "Slow ambient strings, 70 bpm, wistful.",
        "thumbnailPrompt": "A lighthouse at dusk, one lit window.",
    }


def build_story_bible(ask: AskView) -> dict[str, Any]:
    episode_match = EPISODE_LINE_PATTERN.search(ask.message)
    episode_number = episode_match.group(1) if episode_match else "1"
    entry = f"E{episode_number} — the mock cast moves the story on."
    return {
        "summary": f"Mock summary of episode {episode_number}.",
        "storyBible": "\n".join([*read_block(ask.message, "Current story bible"), entry]),
    }


def build_markdown_answer(ask: AskView) -> str:
    if CHARACTERS_HEADING not in ask.message:
        return "\n\n".join(
            f"## Mock character {number}\n\nRole: seen in {len(ask.images)} frames.\n\n"
            f"Portrait prompt: head and shoulders, plain background. Written by {ask.ai}."
            for number in (1, 2)
        )
    if "voice" in ask.instructions.casefold():
        return "\n\n".join(
            f"## Mock character {number}\n\nVoice: calm, mid pitch, slow pace.\n\n"
            f'> "Mock line {number}."'
            for number in (1, 2)
        )
    labels = ask.image_labels[:MAX_SCENE_PROMPT_HEADINGS] or ["the video"]
    return "\n\n".join(
        f"## Mock shot {number} — {label}\n\nMock prompt: medium shot, soft light, 6 seconds."
        for number, label in enumerate(labels, start=1)
    )


def fill_schema(schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((kind for kind in schema_type if kind != "null"), "null")
    if schema.get("enum"):
        return schema["enum"][0]
    if schema_type == "object":
        return {name: fill_schema(child) for name, child in schema.get("properties", {}).items()}
    if schema_type == "array":
        return [fill_schema(schema.get("items", {}))]
    if schema_type in ("integer", "number"):
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    return "mock"


def find_item_enum(properties: dict[str, Any], array_name: str, field_name: str) -> list[str]:
    item_schema = properties.get(array_name, {}).get("items", {})
    return list(item_schema.get("properties", {}).get(field_name, {}).get("enum", []))


def read_block(message: str, heading: str) -> list[str]:
    marker = f"{heading}:\n"
    start = message.find(marker)
    if start < 0:
        return []
    block = message[start + len(marker) :].split("\n\n", 1)[0]
    return [
        line.strip()
        for line in block.splitlines()
        if line.strip() and line.strip() != NO_ITEMS_LINE
    ]


def read_named_lines(message: str, heading: str) -> list[tuple[str, str]]:
    named_lines = []
    for line in read_block(message, heading):
        found = NAMED_LINE_PATTERN.match(line)
        if found:
            named_lines.append((found.group(1).strip(), found.group(2).strip()))
    return named_lines


def pick_evenly(times: list[int], count: int) -> list[int]:
    if count <= 0:
        return []
    if len(times) <= count:
        return times
    step = len(times) / count
    return [times[int(index * step)] for index in range(count)]


def clock_to_ms(clock: str) -> int:
    seconds = 0
    for part in clock.split(":"):
        seconds = seconds * SECONDS_PER_MINUTE + int(part)
    return seconds * MS_PER_SECOND


def ms_to_clock(position_ms: int) -> str:
    minutes, seconds = divmod(position_ms // MS_PER_SECOND, SECONDS_PER_MINUTE)
    return f"{minutes:02d}:{seconds:02d}"
