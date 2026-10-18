import json
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest

from app.modules.prompt_presets.errors import InvalidPresetError
from app.modules.prompt_presets.preset_files import (
    PresetDraft,
    export_json_to_preset_draft,
    preset_draft_to_export_json,
    to_export_filename,
)
from app.modules.prompt_presets.preset_rules import build_unique_preset_name
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    CloneLocalizationRequestText,
    CloneScriptRequestText,
    FilmScriptAnalysis,
    FilmScriptRequestText,
    build_clone_localization_message,
    build_clone_script_message,
    build_clone_shots_message,
    build_film_script_message,
    build_moment_request_message,
    build_video_notes_message,
    build_video_notes_message_with_characters,
    describe_app_added_parts,
)

DRAFT = PresetDraft(name="Phim hoạt hình", prompts=DEFAULT_PRESET_PROMPTS)
VALID_PAYLOAD = json.loads(preset_draft_to_export_json(DRAFT))
FIRST_FORMAT_PROMPTS = {
    "videoToMarkdown": "V",
    "characterImage": "I",
    "characterVoice": "C",
    "scene": "S",
}
SECOND_FORMAT_PROMPTS = {**FIRST_FORMAT_PROMPTS, "filmScript": "F"}
OLD_FILE_BASE = {"format": "video-tool-prompt-preset", "name": "Old export"}
FILM_SCRIPT_TEXT = FilmScriptRequestText(
    series_name="Harbor Mysteries",
    premise="A fishing town hides a drowned city.",
    language_name="English",
    frame_label="16:9 landscape",
    style_line="Anime — cel shading",
    target_seconds="60",
    clip_seconds="8",
    allow_dialogue=False,
    allow_narration=False,
    cast_lines=["Mai (character): A girl. Voice: Soft"],
    earlier_episode_lines=["1. The Bell — A bell rings underwater."],
    idea="A storm",
    analysis=None,
)
ANALYSIS = FilmScriptAnalysis(
    character_image_prompts="## Mai",
    character_voice_prompts="## Mai voice",
    scene_prompts="## 00:01 — Pier",
    frame_names=["moment-01-00m00s.jpg"],
)


@dataclass(frozen=True)
class Outcome:
    actual: str
    expected: str


def capture_import_error(payload) -> str:
    with pytest.raises(InvalidPresetError) as caught:
        export_json_to_preset_draft(json.dumps(payload).encode("utf-8"))
    return str(caught.value)


@pytest.fixture
def round_trip_draft():
    return export_json_to_preset_draft(preset_draft_to_export_json(DRAFT).encode("utf-8"))


@pytest.fixture(
    params=[
        [],
        {**VALID_PAYLOAD, "format": "something-else"},
        {**VALID_PAYLOAD, "formatVersion": 4},
        {**VALID_PAYLOAD, "name": 7},
        {**VALID_PAYLOAD, "prompts": "all of them"},
        {**VALID_PAYLOAD, "prompts": {**VALID_PAYLOAD["prompts"], "scene": None}},
        {**OLD_FILE_BASE, "formatVersion": 2, "prompts": FIRST_FORMAT_PROMPTS},
        {
            **VALID_PAYLOAD,
            "prompts": {k: v for k, v in VALID_PAYLOAD["prompts"].items() if k != "cloneScript"},
        },
    ]
)
def invalid_payload_message(request):
    return capture_import_error(request.param)


@pytest.fixture
def first_format_draft():
    payload = {**OLD_FILE_BASE, "formatVersion": 1, "prompts": FIRST_FORMAT_PROMPTS}
    return export_json_to_preset_draft(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def second_format_draft():
    payload = {**OLD_FILE_BASE, "formatVersion": 2, "prompts": SECOND_FORMAT_PROMPTS}
    return export_json_to_preset_draft(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def idea_film_script_message():
    return build_film_script_message(FILM_SCRIPT_TEXT)


@pytest.fixture
def analysis_film_script_message():
    return build_film_script_message(
        replace(
            FILM_SCRIPT_TEXT,
            premise=None,
            cast_lines=[],
            earlier_episode_lines=[],
            analysis=ANALYSIS,
        )
    )


@pytest.fixture
def analysis_without_direction_message():
    return build_film_script_message(replace(FILM_SCRIPT_TEXT, idea=None, analysis=ANALYSIS))


@pytest.fixture(params=[b"hello", b"\xff\xfe"])
def unreadable_file_message(request):
    with pytest.raises(InvalidPresetError) as caught:
        export_json_to_preset_draft(request.param)
    return str(caught.value)


@pytest.fixture(
    params=[
        ("Anime", "Anime.preset.json"),
        ("Phim / tài liệu?", "Phim _ tài liệu.preset.json"),
        ("***", "preset.preset.json"),
    ]
)
def export_filename(request):
    preset_name, expected = request.param
    return Outcome(actual=to_export_filename(preset_name), expected=expected)


@pytest.fixture(
    params=[
        ("Anime", "copy", [], "Anime (copy)"),
        ("Anime", "copy", ["anime (COPY)"], "Anime (copy 2)"),
        ("Anime", "imported", ["Anime (imported)", "Anime (imported 2)"], "Anime (imported 3)"),
        ("b" * 50, "copy", [], "b" * 43 + " (copy)"),
    ]
)
def unique_name(request):
    base_name, suffix_word, taken_names, expected = request.param
    return Outcome(
        actual=build_unique_preset_name(base_name, suffix_word, taken_names), expected=expected
    )


@pytest.fixture
def app_added_parts():
    return describe_app_added_parts()


def test_export_json_round_trips_name_and_prompts(round_trip_draft):
    assert round_trip_draft == DRAFT


def test_export_json_carries_format_and_camel_case_prompt_keys():
    assert (VALID_PAYLOAD["format"], VALID_PAYLOAD["formatVersion"]) == (
        "video-tool-prompt-preset",
        3,
    )
    assert sorted(VALID_PAYLOAD["prompts"]) == [
        "characterImage",
        "characterVoice",
        "cloneAssets",
        "cloneLocalization",
        "cloneScript",
        "cloneShots",
        "filmScript",
        "scene",
        "videoToMarkdown",
    ]


def test_first_format_file_gets_code_defaults_for_later_prompts(first_format_draft):
    assert first_format_draft.prompts == replace(
        DEFAULT_PRESET_PROMPTS,
        video_to_markdown="V",
        character_image="I",
        character_voice="C",
        scene="S",
    )


def test_second_format_file_gets_code_defaults_for_clone_prompts(second_format_draft):
    assert second_format_draft.prompts == replace(
        DEFAULT_PRESET_PROMPTS,
        video_to_markdown="V",
        character_image="I",
        character_voice="C",
        scene="S",
        film_script="F",
    )


def test_export_json_rejects_anything_but_a_preset(invalid_payload_message):
    assert invalid_payload_message == "Not a prompt preset file"


def test_export_json_rejects_unreadable_bytes(unreadable_file_message):
    assert unreadable_file_message == "Not a prompt preset file"


def test_to_export_filename_uses_a_safe_stem(export_filename):
    assert export_filename.actual == export_filename.expected


def test_build_unique_preset_name_skips_taken_names(unique_name):
    assert unique_name.actual == unique_name.expected


def test_moment_request_message_states_the_limit_and_the_transcript():
    assert build_moment_request_message("7", "[0ms] Hi") == (
        "Choose at most 7 key moments. Set atMs to the start time of the line where the moment "
        "begins.\n\nTranscript, one line per segment as [start time] text:\n[0ms] Hi"
    )


def test_video_notes_message_points_at_the_frames():
    assert build_video_notes_message("# Notes") == (
        "Video notes:\n\n# Notes\n\nThe frames referenced in the notes are attached below as "
        "images, each after its file name. Look at them to see the characters and scenes."
    )


def test_video_notes_message_with_characters_adds_the_character_list():
    assert "Video notes:\n\n# Notes\n\nCharacters:\n\n## Hero\n\nThe frames" in (
        build_video_notes_message_with_characters("# Notes", "## Hero")
    )


def test_describe_app_added_parts_shows_placeholders(app_added_parts):
    assert app_added_parts.video_to_markdown.startswith("Reply shape (JSON schema, fixed)")
    assert "Choose at most {N} key moments" in app_added_parts.video_to_markdown
    assert "This part of the video runs from {start} to {end}" in (
        app_added_parts.video_to_markdown
    )
    assert "Characters:" not in app_added_parts.character_image
    assert "Characters:" in app_added_parts.character_voice
    assert app_added_parts.scene == app_added_parts.character_voice
    assert "add up to about {target_duration_s}s" in app_added_parts.film_script
    assert "a typical clip lasts {clip}s" in app_added_parts.film_script
    assert app_added_parts.clone_assets.startswith("Reply shape (JSON schema, fixed): assets[]")
    assert "Give exactly one entry per frame." in app_added_parts.clone_shots
    assert "Target country: {target country}" in app_added_parts.clone_localization
    assert "Target setting: {target setting, when set}" in app_added_parts.clone_localization
    assert "Setting: {target country, when set}. {target setting, when set}" in (
        app_added_parts.clone_script
    )
    assert "Write exactly one scene per shot" in app_added_parts.clone_script


def test_film_script_message_for_an_idea(idea_film_script_message):
    assert idea_film_script_message == (
        "Series: Harbor Mysteries\n"
        "Premise: A fishing town hides a drowned city.\n"
        "Language of narration and dialogue: English\n"
        "Frame: 16:9 landscape\n"
        "Style: Anime — cel shading\n\n"
        "Write scenes whose clip lengths, each minus its first second, add up to about 60s. "
        "Give each scene the clip length its action needs, 4-30 s; a typical clip lasts 8s. The "
        "first second of every clip is cut, so a scene's narration must fit in its clip length "
        "minus 1 s.\n\n"
        "No character speaks; clips carry ambient sound only.\n"
        "Narration: off — leave narratorText empty.\n\n"
        "Cast:\nMai (character): A girl. Voice: Soft\n"
        "Reuse these names exactly. Add a character only when the story needs one.\n\n"
        "Earlier episodes:\n1. The Bell — A bell rings underwater.\n\n"
        "Episode idea:\nA storm"
    )


def test_film_script_message_for_a_film_analysis(analysis_film_script_message):
    assert "Premise:" not in analysis_film_script_message
    assert "Cast:" not in analysis_film_script_message
    assert "Earlier episodes:" not in analysis_film_script_message
    assert analysis_film_script_message.endswith(
        "Adapt this film analysis:\n\nCharacter image prompts:\n## Mai\n\n"
        "Character voice prompts:\n## Mai voice\n\nScene prompts:\n## 00:01 — Pier\n\n"
        "Reference frames:\nmoment-01-00m00s.jpg\n\nExtra direction:\nA storm"
    )


def test_film_script_message_without_extra_direction(analysis_without_direction_message):
    assert analysis_without_direction_message.endswith("Reference frames:\nmoment-01-00m00s.jpg")


def test_clone_shots_message_lists_assets_then_notes():
    assert build_clone_shots_message("# Notes", []) == (
        "Give exactly one entry per frame.\n\nAssets:\n(none)\n\nVideo notes:\n\n# Notes\n\n"
        "The frames referenced in the notes are attached below as images, each after its file "
        "name. Look at them to see the characters and scenes."
    )


def test_clone_localization_message_joins_the_allowed_changes():
    assert build_clone_localization_message(
        CloneLocalizationRequestText(
            country_name="Japan",
            target_setting=None,
            allowed_changes=["face", "clothing"],
            candidate_lines=["Mai (character) — A girl. Culture: Korean. Period: Present day."],
        )
    ) == (
        "Target country: Japan\n\nChange only: face; clothing\n\n"
        "Candidates:\nMai (character) — A girl. Culture: Korean. Period: Present day.\n\n"
        "Each candidate's reference frame is attached below as an image, after its file name."
    )


def test_clone_localization_message_puts_the_target_setting_after_the_country():
    assert build_clone_localization_message(
        CloneLocalizationRequestText(
            country_name="Japan",
            target_setting="a modern Tokyo office district",
            allowed_changes=["architecture"],
            candidate_lines=["Palace (location) — A palace. Culture: Korean. Period: Joseon."],
        )
    ).startswith(
        "Target country: Japan\n\nTarget setting: a modern Tokyo office district\n"
        "Follow the target setting where it differs from the original period or place.\n\n"
        "Change only: architecture\n\n"
    )


@pytest.fixture
def original_setting_script_message():
    return build_clone_script_message(
        CloneScriptRequestText(
            language_name="Vietnamese",
            country_name=None,
            target_setting=None,
            asset_lines=["Mai (character) — A girl"],
            shot_lines=["shot-1 · 00:00 · Close-up · — · emotion: calm · assets: Mai"],
            video_notes="# Notes",
        )
    )


def test_clone_script_message_keeps_the_original_setting(original_setting_script_message):
    assert original_setting_script_message.startswith(
        "Script language: Vietnamese. Keep the tone and register of the original dialogue."
        "\n\nSetting: keep the original.\n\nWrite exactly one scene per shot"
    )
    assert original_setting_script_message.endswith(
        "Shots:\nshot-1 · 00:00 · Close-up · — · emotion: calm · assets: Mai"
        "\n\nVideo notes:\n\n# Notes"
    )


@pytest.fixture(
    params=[
        ("Japan", "a modern Tokyo street", "Setting: Japan. a modern Tokyo street"),
        ("Japan", None, "Setting: Japan"),
        (None, "a modern Western city", "Setting: a modern Western city"),
        (None, None, "Setting: keep the original."),
    ]
)
def clone_setting_line(request):
    country_name, target_setting, expected = request.param
    message = build_clone_script_message(
        CloneScriptRequestText(
            language_name="English",
            country_name=country_name,
            target_setting=target_setting,
            asset_lines=[],
            shot_lines=[],
            video_notes="# Notes",
        )
    )
    return SimpleNamespace(actual=message.split("\n\n")[1], expected=expected)


def test_clone_script_message_names_the_country_and_the_target_setting(clone_setting_line):
    assert clone_setting_line.actual == clone_setting_line.expected
