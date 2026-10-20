from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from enum import StrEnum

from app.modules.films.part_rules import MAX_PART_DURATION_S, MIN_PART_DURATION_S
from app.modules.films.scene_rules import MAX_SCENE_CLIP_DURATION_S, MIN_SCENE_CLIP_DURATION_S
from app.modules.films.story_rules import STORY_BIBLE_LIMIT


class PromptKey(StrEnum):
    VIDEO_TO_MARKDOWN = "videoToMarkdown"
    SPEAKERS_AND_SOUNDS = "speakersAndSounds"
    CHARACTER_IMAGE = "characterImage"
    CHARACTER_VOICE = "characterVoice"
    SCENE = "scene"
    FILM_OUTLINE = "filmOutline"
    FILM_SCRIPT = "filmScript"
    STORY_BIBLE = "storyBible"
    CLONE_ASSETS = "cloneAssets"
    CLONE_SHOTS = "cloneShots"
    CLONE_LOCALIZATION = "cloneLocalization"
    CLONE_SCRIPT = "cloneScript"


@dataclass(frozen=True)
class PresetPrompts:
    video_to_markdown: str
    speakers_and_sounds: str
    character_image: str
    character_voice: str
    scene: str
    film_outline: str
    film_script: str
    story_bible: str
    clone_assets: str
    clone_shots: str
    clone_localization: str
    clone_script: str


PRESET_PROMPT_FIELD_NAMES = tuple(field.name for field in fields(PresetPrompts))
FIELD_NAMES_BY_PROMPT_KEY = dict(zip(PromptKey, PRESET_PROMPT_FIELD_NAMES, strict=True))


def preset_prompts_to_prompts_by_key(prompts: PresetPrompts) -> dict[PromptKey, str]:
    return {
        key: getattr(prompts, field_name) for key, field_name in FIELD_NAMES_BY_PROMPT_KEY.items()
    }


def prompts_by_key_to_preset_prompts(prompts_by_key: Mapping[PromptKey, str]) -> PresetPrompts:
    return PresetPrompts(
        **{field_name: prompts_by_key[key] for key, field_name in FIELD_NAMES_BY_PROMPT_KEY.items()}
    )


DEFAULT_PRESET_PROMPTS = PresetPrompts(
    video_to_markdown=(
        "You read a timestamped video transcript and choose its key moments: the points where "
        "the topic, the step being demonstrated, or what is shown on screen changes. Every moment "
        "starts at the start time of one transcript line, and the first moment starts at the "
        "first transcript line. Give the video a short title and a 2-3 sentence summary. Write "
        "the title, the summary and every moment title in the same language as the transcript, "
        "whatever language these instructions use. Answer only through the structured output."
    ),
    speakers_and_sounds=(
        "You listen to one part of a film and tell its voices apart.\n\n"
        "1. Tell the voices apart by pitch, timbre, accent and way of speaking. Give each "
        "distinct voice one speaker, named as the film names them when a name is heard, "
        'otherwise by a short label such as "Older man, deep voice". Keep the name the earlier '
        "parts gave the same voice.\n"
        "2. Describe each voice in English: gender presentation, apparent age, pitch, pace, "
        "timbre, accent and usual emotion.\n"
        "3. Give every transcript line the speaker who says it, at the line's start time. Leave "
        "out a line no voice matches.\n"
        "4. Mark the sounds that are not speech, each with the time it starts, in milliseconds "
        "from the start of the film, and a short English description: the sound of an action "
        "(footsteps, a door, a blow, crying, laughter), a silence of 3 s or more, a sound of the "
        "surroundings (an animal, rain, wind, traffic, a crowd), music that starts or changes "
        "mood.\n\n"
        "Answer only through the structured output."
    ),
    character_image=(
        "You turn a film — its notes and frames, or the film itself attached as video — into "
        "reference image prompts for its characters.\n\n"
        "1. List every recurring character seen in the frames or the video, named in the notes "
        "or heard speaking. Use the character's name when the film gives one, otherwise a short "
        'visual label such as "Woman in red coat". Skip crowds and one-off extras.\n'
        "2. Tell the characters apart by who speaks and by voice too: one entry per person, "
        "never two for the same voice. Use the speaker names of the notes when they are given.\n"
        "3. For each character give their role in the story, the timestamps where they appear, "
        "and two image prompts in English: a head-and-shoulders reference portrait, and a "
        "full-body shot on a plain background.\n"
        "4. Each prompt covers apparent age range, build, face, hair, skin tone, outfit, "
        "accessories, usual expression, and the film's visual style (live action or animation, "
        "era, lighting).\n"
        "5. Describe only what is visible or stated. Mark anything you guess with "
        '"(inferred)".\n\n'
        'Answer in Markdown, with one "## {character label}" section per character.'
    ),
    character_voice=(
        "You turn a film — its notes and frames, or the film itself attached as video — into "
        "voice-design prompts for its speaking characters.\n\n"
        "1. Cover every character who speaks, using the labels of the character list you are "
        "given.\n"
        "2. Tell the speakers apart by their voices: one entry per distinct voice, never one "
        "voice split into two characters or two voices merged into one.\n"
        "3. For each character write one voice-design prompt in English covering gender "
        "presentation, apparent age, pitch, pace, timbre, accent, and usual emotion and "
        "delivery — as heard when the film is attached as video.\n"
        "4. Quote 1-3 short lines that character says, from the transcript or the video, in "
        "their original language.\n"
        "5. Take who says each line from the speakers of the notes, or from what is heard in "
        "the video. Without either, mark any line or trait you attribute by guess with "
        '"(inferred)".\n\n'
        'Answer in Markdown, with one "## {character label}" section per character.'
    ),
    scene=(
        "You turn a film — its notes and frames, or the film itself attached as video — into "
        "prompts for generating similar shots with a video model.\n\n"
        "1. Write one prompt per distinct shot shown in the frames or the video, in time order, "
        'under a heading "## {timestamp} — {short title}".\n'
        "2. Write each prompt in English for a shot similar to the original: subject and "
        "action, setting, time of day, shot size, camera angle and movement, lighting, colour "
        "palette, mood, and a length of 5-8 seconds.\n"
        "3. Refer to characters by the labels of the character list you are given, and say who "
        "speaks in the shot.\n\n"
        "Answer in Markdown."
    ),
    film_outline=(
        "You plan one episode of a series as an outline of parts. Each part is one stretch of "
        "the story with a goal, a turn and an ending that leads into the next part.\n\n"
        "1. Open the first part on a visual hook and end the last part on an unanswered "
        "question. A later episode picks up the previous cliffhanger in its first part.\n"
        "2. Keep every fact of the story bible and of the earlier episodes' summaries true, "
        "unless this episode changes it on screen.\n"
        "3. Give each part a title and a plan naming who is in it, where it happens, what "
        "happens and how it ends.\n"
        "4. Give each part the length its story needs, within the range given.\n"
        "5. Give a music prompt (genre, instruments, tempo, mood) and a thumbnail prompt (one "
        "striking frame, no text).\n"
        "6. Write titles and plans in the language of narration, and character names exactly "
        "as the cast gives them. Answer only through the structured output."
    ),
    film_script=(
        "You write one part of an episode of a series as a screenplay of short scenes. Each "
        "scene is one shot and one clip.\n\n"
        "1. Tell exactly what the part's plan says, picking up where the story so far ends.\n"
        "2. Give each scene the clip length its action needs, "
        f"{MIN_SCENE_CLIP_DURATION_S}-{MAX_SCENE_CLIP_DURATION_S} s: a quick beat short, a held "
        "or travelling moment long.\n"
        "3. Write each image prompt as action, setting, framing, lens and light. Never describe "
        "faces, hair or build — the reference images carry them; describe clothing only when it "
        "changes.\n"
        "4. Write each video prompt as timed beats of 2-4 s that cover the scene's clip length "
        "(0-3s, 3-6s, 6-8s for an 8 s clip), the camera movement as a sentence of its own, the "
        "lighting and the sounds heard, and end it with: Negative: subtitles, watermark, text "
        "overlay.\n"
        "5. Put at most two named characters in a scene, crowds blurred in the background, and "
        "never two shots of the same size in a row.\n"
        "6. Narration tells what the picture cannot show — motive, stakes, the ticking clock — "
        "never what is on screen: 18-22 words in Vietnamese, 20-24 in English, 12-16 when "
        "characters speak, for a 7 s window, scaled to the scene's clip length.\n"
        "7. End with a recap of the part: what happened and where each character stands at its "
        "end.\n"
        "8. Write character names exactly as the cast gives them. Answer only through the "
        "structured output."
    ),
    story_bible=(
        "You keep the story bible of a series: a running record of its world and rules, each "
        "character with their state, goals and relationships, the open threads, and the key "
        "events of each episode.\n\n"
        "1. Merge the episode into the current story bible: keep every fact still true, change "
        "or remove what the episode made false, add what is new.\n"
        "2. Stay under the length given; shorten the events of old episodes first.\n"
        "3. Write a summary of the episode: what happens and where each character stands at its "
        "end.\n"
        "4. Write in the language of narration. Answer only through the structured output."
    ),
    clone_assets=(
        "You catalogue the assets of a film from its notes and frames.\n\n"
        "1. List the characters, costumes, props and locations that recur or matter to the "
        "story, seen in the frames or named in the notes. Skip crowds and one-off background "
        "items.\n"
        '2. Name each one as the film does, otherwise by a short label such as "Red lacquer '
        'fan", and describe how it looks. Name a character as the speaker the video notes give '
        "when it is the same person, so the script's dialogue and the assets match.\n"
        "3. Give the culture or country it comes from and its historical period, judged from "
        "clothing, architecture, objects, language and setting. Answer Unknown when the film "
        "gives no clue; never guess a country from a face alone.\n"
        "4. List the frames it appears in, the clearest view first.\n\n"
        "Answer only through the structured output."
    ),
    clone_shots=(
        "You describe every frame of a film as a shot.\n\n"
        "1. Look at each frame on its own and give its shot size and camera angle.\n"
        "2. Describe the main characters' emotion in a few words and what they do in one "
        "sentence.\n"
        "3. List the assets visible in the frame, by the names you are given.\n\n"
        "Answer only through the structured output."
    ),
    clone_localization=(
        "You move the assets of a film to another country.\n\n"
        "1. For each candidate asset, change only what the message allows.\n"
        "2. Keep its role in the story and its period — the equivalent period in the target "
        "country — and the colours or shapes the plot depends on.\n"
        "3. Leave an asset unchanged when it already fits the target country.\n"
        "4. Write the localized description as a self-contained English image description, and "
        "a one-line note on what changed.\n\n"
        "Answer only through the structured output."
    ),
    clone_script=(
        "You retell a film shot by shot as a new script.\n\n"
        "1. Keep the plot, the order and the emotion of every shot.\n"
        "2. Write each description as what the viewer sees, and the dialogue from the video "
        "notes in the script language, with the original tone and register, each line given to "
        "the character the notes name as its speaker.\n"
        "3. Write each image prompt in English: the subjects by asset name and look, the action, "
        "the setting, the shot size and camera angle, light and mood — so the image can be made "
        "without seeing the film.\n"
        "4. Give the script a title and a one-sentence logline in the script language.\n\n"
        "Answer only through the structured output."
    ),
)

OUTLINE_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): title, summary, moments[] { atMs, title }"
)
TRANSCRIPT_LINE_PLACEHOLDER = "[{start_ms}ms] {text}\n…"
MAX_MOMENTS_PLACEHOLDER = "{N}"
VIDEO_NOTES_PLACEHOLDER = "{video notes}"
CHARACTERS_PLACEHOLDER = "{character image prompts of this job}"
FRAMES_ATTACHED_NOTE = (
    "The frames referenced in the notes are attached below as images, each after its file name. "
    "Look at them to see the characters and scenes."
)
FILM_OUTLINE_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): title, logline, parts[] { title, plan, durationS }, "
    "musicPrompt, thumbnailPrompt"
)
FILM_SCRIPT_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): recap, characters[] { name, entityType, description, "
    "voiceDescription, referenceFrame }, scenes[] { imagePrompt, videoPrompt, narratorText, "
    "characterNames[], durationS }"
)
STORY_BIBLE_SHAPE_DESCRIPTION = "Reply shape (JSON schema, fixed): summary, storyBible"
EMPTY_STORY_BIBLE_LINE = "Current story bible: (empty)"
CLONE_ASSETS_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): assets[] { kind: character | costume | prop | location, "
    "name, description, culture, period, frames[] }"
)
CLONE_SHOTS_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): shots[] { frame, shotSize, cameraAngle, emotion, action, "
    "assetNames[] }"
)
CLONE_LOCALIZATION_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): assets[] { name, changed, localizedName, "
    "localizedDescription, note }"
)
CLONE_SCRIPT_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): title, logline, scenes[] { shotId, description, dialogue, "
    "imagePrompt }"
)
ONE_SHOT_PER_FRAME_INSTRUCTION = "Give exactly one entry per frame."
CANDIDATE_FRAMES_NOTE = (
    "Each candidate's reference frame is attached below as an image, after its file name."
)
ONE_SCENE_PER_SHOT_INSTRUCTION = (
    "Write exactly one scene per shot, in the order given, each with its shotId. Put spoken "
    'lines in dialogue, one "{name}: {line}" per line; the description says what happens on '
    "screen."
)
NO_ITEMS_LINE = "(none)"
TARGET_SETTING_PRECEDENCE_INSTRUCTION = (
    "Follow the target setting where it differs from the original period or place."
)
ORIGINAL_SETTING_LINE = "Setting: keep the original."
NO_SPEECH_IN_WINDOW_LINE = "(no speech in this part)"
WHOLE_VIDEO_MODE_HEADING = (
    "Whole video mode — one message per part of the video, its frames attached at one per second:"
)
SPEAKERS_AND_SOUNDS_SHAPE_DESCRIPTION = (
    "Reply shape (JSON schema, fixed): speakers[] { name, voice }, lines[] { atMs, speaker }, "
    "sounds[] { atMs, kind: action | silence | ambient | music, description }"
)
SAME_SPEAKER_NAME_INSTRUCTION = "Use the same name for the same voice."
AUDIO_PART_PLACEHOLDER = "[audio {start}–{end}] {the part as audio}"
FILM_ATTACHED_AS_VIDEO_LINE = "The film is attached as video."
ANSWER_AGAIN_INSTRUCTION = (
    "Answer again for the whole film so far: keep every entry, update it with this part and add "
    "the new ones."
)
FULL_VIDEO_MODE_HEADING = (
    "Full video mode — no notes and no frames; one message per part of the film, the part "
    "attached as video:"
)
VIDEO_PART_PLACEHOLDER = "[video {start}–{end}] {the part as video}"


@dataclass(frozen=True)
class FilmScriptAnalysis:
    character_image_prompts: str
    character_voice_prompts: str
    scene_prompts: str
    frame_names: Sequence[str]


@dataclass(frozen=True)
class StoryContextText:
    series_name: str
    premise: str | None
    story_bible: str | None
    language_name: str
    earlier_episode_lines: Sequence[str]
    idea: str | None
    analysis: FilmScriptAnalysis | None


@dataclass(frozen=True)
class FilmOutlineRequestText:
    context: StoryContextText
    target_seconds: str
    cast_lines: Sequence[str]


@dataclass(frozen=True)
class FilmScriptRequestText:
    context: StoryContextText
    frame_label: str
    style_line: str
    target_seconds: str
    clip_seconds: str
    allow_dialogue: bool
    allow_narration: bool
    cast_lines: Sequence[str]
    outline_lines: Sequence[str]
    part_number: str
    story_so_far_lines: Sequence[str]


@dataclass(frozen=True)
class StoryBibleRequestText:
    series_name: str
    premise: str | None
    language_name: str
    story_bible: str | None
    episode_line: str
    part_lines: Sequence[str]


@dataclass(frozen=True)
class CloneLocalizationRequestText:
    country_name: str
    target_setting: str | None
    allowed_changes: Sequence[str]
    candidate_lines: Sequence[str]


@dataclass(frozen=True)
class WindowMomentRequestText:
    start: str
    end: str
    max_moments: str
    transcript_lines: str


@dataclass(frozen=True)
class AudioPartRequestText:
    start: str
    end: str
    speaker_lines: Sequence[str]
    transcript_lines: str


@dataclass(frozen=True)
class FullVideoRequestText:
    language_name: str | None
    part_line: str | None
    character_prompts: str | None
    earlier_answer: str | None


@dataclass(frozen=True)
class CloneScriptRequestText:
    language_name: str
    country_name: str | None
    target_setting: str | None
    asset_lines: Sequence[str]
    shot_lines: Sequence[str]
    video_notes: str


def build_moment_request_message(max_moments: str, transcript_lines: str) -> str:
    return (
        f"Choose at most {max_moments} key moments. Set atMs to the start time of the line "
        "where the moment begins.\n\n"
        f"Transcript, one line per segment as [start time] text:\n{transcript_lines}"
    )


def build_window_moment_message(text: WindowMomentRequestText) -> str:
    return (
        f"This part of the video runs from {text.start} to {text.end}. Choose at most "
        f"{text.max_moments} key moments in it. Set atMs to the time of the frame or the line "
        "where the moment begins.\n\n"
        f"Transcript:\n{text.transcript_lines or NO_SPEECH_IN_WINDOW_LINE}\n\n"
        "Frames:"
    )


def build_audio_part_message(text: AudioPartRequestText) -> str:
    blocks = [f"This part of the film runs from {text.start} to {text.end}."]
    if text.speaker_lines:
        blocks.append(
            "\n".join(["Speakers so far:", *text.speaker_lines, SAME_SPEAKER_NAME_INSTRUCTION])
        )
    blocks.append(f"Transcript:\n{text.transcript_lines or NO_SPEECH_IN_WINDOW_LINE}")
    return "\n\n".join(blocks)


def build_film_part_line(start: str, end: str, part_number: str, part_count: str) -> str:
    return f"This part of the film runs from {start} to {end} (part {part_number} of {part_count})."


def build_full_video_message(text: FullVideoRequestText) -> str:
    opening_lines = [FILM_ATTACHED_AS_VIDEO_LINE]
    if text.language_name:
        opening_lines.append(f"Spoken language: {text.language_name}")
    blocks = ["\n".join(opening_lines)]
    if text.part_line:
        blocks.append(text.part_line)
    if text.character_prompts is not None:
        blocks.append(f"Characters:\n\n{text.character_prompts}")
    if text.earlier_answer is not None:
        blocks.append(f"Your answer for the earlier parts:\n\n{text.earlier_answer}")
        blocks.append(ANSWER_AGAIN_INSTRUCTION)
    return "\n\n".join(blocks)


def build_video_notes_message(video_notes: str) -> str:
    return "\n\n".join([_video_notes_block(video_notes), FRAMES_ATTACHED_NOTE])


def build_video_notes_message_with_characters(video_notes: str, character_prompts: str) -> str:
    return "\n\n".join(
        [
            _video_notes_block(video_notes),
            f"Characters:\n\n{character_prompts}",
            FRAMES_ATTACHED_NOTE,
        ]
    )


def build_film_outline_message(text: FilmOutlineRequestText) -> str:
    blocks = [
        *_story_context_blocks(text.context),
        f"Split the episode into parts whose lengths add up to about {text.target_seconds}s. "
        f"Each part lasts {MIN_PART_DURATION_S}-{MAX_PART_DURATION_S} s.",
    ]
    if text.cast_lines:
        blocks.append("Cast:\n" + "\n".join(text.cast_lines))
    return "\n\n".join(blocks)


def build_film_script_message(text: FilmScriptRequestText) -> str:
    blocks = [
        *_story_context_blocks(text.context),
        f"Frame: {text.frame_label}\nStyle: {text.style_line}",
        *_film_script_rules(text),
    ]
    if text.cast_lines:
        blocks.append(
            "Cast:\n"
            + "\n".join(text.cast_lines)
            + "\nReuse these names exactly. Add a character only when the story needs one."
        )
    blocks.append(
        "Episode outline:\n"
        + "\n".join(text.outline_lines)
        + f"\nWrite part {text.part_number} now."
    )
    if text.story_so_far_lines:
        blocks.append("Story so far:\n" + "\n".join(text.story_so_far_lines))
    if text.context.analysis is not None:
        blocks.append(_list_block("Reference frames", text.context.analysis.frame_names))
    return "\n\n".join(blocks)


def build_story_bible_message(text: StoryBibleRequestText) -> str:
    return "\n\n".join(
        [
            "\n".join(
                [
                    *_series_lines(text.series_name, text.premise),
                    f"Language of narration and dialogue: {text.language_name}",
                ]
            ),
            f"Current story bible:\n{text.story_bible}"
            if text.story_bible
            else EMPTY_STORY_BIBLE_LINE,
            text.episode_line,
            "Parts:\n" + "\n".join(text.part_lines),
            f"Keep the story bible under {STORY_BIBLE_LIMIT} characters.",
        ]
    )


def build_clone_shots_message(video_notes: str, asset_labels: Sequence[str]) -> str:
    return "\n\n".join(
        [
            ONE_SHOT_PER_FRAME_INSTRUCTION,
            _list_block("Assets", asset_labels),
            _video_notes_block(video_notes),
            FRAMES_ATTACHED_NOTE,
        ]
    )


def build_clone_localization_message(text: CloneLocalizationRequestText) -> str:
    target_setting_blocks = (
        [f"Target setting: {text.target_setting}\n{TARGET_SETTING_PRECEDENCE_INSTRUCTION}"]
        if text.target_setting
        else []
    )
    return "\n\n".join(
        [
            f"Target country: {text.country_name}",
            *target_setting_blocks,
            "Change only: " + "; ".join(text.allowed_changes),
            _list_block("Candidates", text.candidate_lines),
            CANDIDATE_FRAMES_NOTE,
        ]
    )


def build_clone_script_message(text: CloneScriptRequestText) -> str:
    return "\n\n".join(
        [
            f"Script language: {text.language_name}. "
            "Keep the tone and register of the original dialogue.",
            _clone_setting_line(text.country_name, text.target_setting),
            ONE_SCENE_PER_SHOT_INSTRUCTION,
            _list_block("Assets", text.asset_lines),
            _list_block("Shots", text.shot_lines),
            _video_notes_block(text.video_notes),
        ]
    )


def describe_app_added_parts() -> PresetPrompts:
    return PresetPrompts(
        video_to_markdown="\n\n".join(
            [
                OUTLINE_SHAPE_DESCRIPTION,
                build_moment_request_message(MAX_MOMENTS_PLACEHOLDER, TRANSCRIPT_LINE_PLACEHOLDER),
                WHOLE_VIDEO_MODE_HEADING,
                build_window_moment_message(_WINDOW_MOMENT_PLACEHOLDERS),
            ]
        ),
        speakers_and_sounds="\n\n".join(
            [
                SPEAKERS_AND_SOUNDS_SHAPE_DESCRIPTION,
                build_audio_part_message(_AUDIO_PART_PLACEHOLDERS),
                AUDIO_PART_PLACEHOLDER,
            ]
        ),
        character_image=_with_full_video_parts(
            build_video_notes_message(VIDEO_NOTES_PLACEHOLDER),
            replace(_FULL_VIDEO_PLACEHOLDERS, character_prompts=None),
        ),
        character_voice=_with_full_video_parts(
            build_video_notes_message_with_characters(
                VIDEO_NOTES_PLACEHOLDER, CHARACTERS_PLACEHOLDER
            ),
            _FULL_VIDEO_PLACEHOLDERS,
        ),
        scene=_with_full_video_parts(
            build_video_notes_message_with_characters(
                VIDEO_NOTES_PLACEHOLDER, CHARACTERS_PLACEHOLDER
            ),
            replace(_FULL_VIDEO_PLACEHOLDERS, earlier_answer=None),
        ),
        film_outline="\n\n".join(
            [FILM_OUTLINE_SHAPE_DESCRIPTION, build_film_outline_message(_FILM_OUTLINE_PLACEHOLDERS)]
        ),
        film_script="\n\n".join(
            [FILM_SCRIPT_SHAPE_DESCRIPTION, build_film_script_message(_FILM_SCRIPT_PLACEHOLDERS)]
        ),
        story_bible="\n\n".join(
            [STORY_BIBLE_SHAPE_DESCRIPTION, build_story_bible_message(_STORY_BIBLE_PLACEHOLDERS)]
        ),
        clone_assets="\n\n".join(
            [CLONE_ASSETS_SHAPE_DESCRIPTION, build_video_notes_message(VIDEO_NOTES_PLACEHOLDER)]
        ),
        clone_shots="\n\n".join(
            [
                CLONE_SHOTS_SHAPE_DESCRIPTION,
                build_clone_shots_message(VIDEO_NOTES_PLACEHOLDER, ["{name} ({kind})\n…"]),
            ]
        ),
        clone_localization="\n\n".join(
            [
                CLONE_LOCALIZATION_SHAPE_DESCRIPTION,
                build_clone_localization_message(_LOCALIZATION_PLACEHOLDERS),
            ]
        ),
        clone_script="\n\n".join(
            [CLONE_SCRIPT_SHAPE_DESCRIPTION, build_clone_script_message(_CLONE_SCRIPT_PLACEHOLDERS)]
        ),
    )


def _with_full_video_parts(notes_message: str, full_video_text: FullVideoRequestText) -> str:
    return "\n\n".join(
        [
            notes_message,
            FULL_VIDEO_MODE_HEADING,
            build_full_video_message(full_video_text),
            VIDEO_PART_PLACEHOLDER,
        ]
    )


def _clone_setting_line(country_name: str | None, target_setting: str | None) -> str:
    setting_parts = [part for part in (country_name, target_setting) if part]
    return "Setting: " + ". ".join(setting_parts) if setting_parts else ORIGINAL_SETTING_LINE


def _video_notes_block(video_notes: str) -> str:
    return f"Video notes:\n\n{video_notes}"


def _list_block(heading: str, lines: Sequence[str]) -> str:
    return f"{heading}:\n" + ("\n".join(lines) or NO_ITEMS_LINE)


def _series_lines(series_name: str, premise: str | None) -> list[str]:
    lines = [f"Series: {series_name}"]
    if premise:
        lines.append(f"Premise: {premise}")
    return lines


def _story_context_blocks(context: StoryContextText) -> list[str]:
    blocks = ["\n".join(_series_lines(context.series_name, context.premise))]
    if context.story_bible:
        blocks.append(f"Story bible:\n{context.story_bible}")
    blocks.append(f"Language of narration and dialogue: {context.language_name}")
    if context.earlier_episode_lines:
        blocks.append("Earlier episodes:\n" + "\n".join(context.earlier_episode_lines))
    blocks.extend(_story_source_blocks(context))
    return blocks


def _film_script_rules(text: FilmScriptRequestText) -> list[str]:
    dialogue_line = (
        "Characters may speak inside clips."
        if text.allow_dialogue
        else "No character speaks; clips carry ambient sound only."
    )
    narration_line = (
        "Narration: on" if text.allow_narration else "Narration: off — leave narratorText empty."
    )
    return [
        "Write scenes whose clip lengths, each minus its first second, add up to about "
        f"{text.target_seconds}s. Give each scene the clip length its action needs, "
        f"{MIN_SCENE_CLIP_DURATION_S}-{MAX_SCENE_CLIP_DURATION_S} s; a typical clip lasts "
        f"{text.clip_seconds}s. The first second of every clip is cut, so a scene's narration "
        "must fit in its clip length minus 1 s.",
        "\n".join([dialogue_line, narration_line]),
    ]


def _story_source_blocks(context: StoryContextText) -> list[str]:
    if context.analysis is None:
        return [f"Episode idea:\n{context.idea or ''}"]
    analysis = context.analysis
    blocks = [
        "Adapt this film analysis:\n\n"
        f"Character image prompts:\n{analysis.character_image_prompts}\n\n"
        f"Character voice prompts:\n{analysis.character_voice_prompts}\n\n"
        f"Scene prompts:\n{analysis.scene_prompts}"
    ]
    if context.idea:
        blocks.append(f"Extra direction:\n{context.idea}")
    return blocks


_STORY_CONTEXT_PLACEHOLDERS = StoryContextText(
    series_name="{series name}",
    premise="{premise, when set}",
    story_bible="{story bible, when set}",
    language_name="{Vietnamese | English | Japanese}",
    earlier_episode_lines=["{number}. {title} — {logline}", "Summary: {summary, when set}"],
    idea="{episode idea, or the film analysis and extra direction}",
    analysis=None,
)
_FILM_OUTLINE_PLACEHOLDERS = FilmOutlineRequestText(
    context=_STORY_CONTEXT_PLACEHOLDERS,
    target_seconds="{target_duration_s}",
    cast_lines=["{name} ({entity type}): {description}"],
)
_FILM_SCRIPT_PLACEHOLDERS = FilmScriptRequestText(
    context=_STORY_CONTEXT_PLACEHOLDERS,
    frame_label="{16:9 landscape | 9:16 portrait}",
    style_line="{style name} — {style instruction}",
    target_seconds="{target_duration_s}",
    clip_seconds="{clip}",
    allow_dialogue=True,
    allow_narration=True,
    cast_lines=["{name} ({entity type}): {description}. Voice: {voice description}"],
    outline_lines=["{k}. {title}: {plan}"],
    part_number="{k}",
    story_so_far_lines=["{k}. {recap, or the plan when the part has none}"],
)
_STORY_BIBLE_PLACEHOLDERS = StoryBibleRequestText(
    series_name="{series name}",
    premise="{premise, when set}",
    language_name="{Vietnamese | English | Japanese}",
    story_bible="{story bible, or (empty)}",
    episode_line="Episode {number}: {title} — {logline}",
    part_lines=[
        "{k}. {title}",
        "{recap, or one line per scene: Scene {n}: {video prompt} Narration: {narration}}",
    ],
)
_WINDOW_MOMENT_PLACEHOLDERS = WindowMomentRequestText(
    start="{start}",
    end="{end}",
    max_moments="{m}",
    transcript_lines=TRANSCRIPT_LINE_PLACEHOLDER,
)
_AUDIO_PART_PLACEHOLDERS = AudioPartRequestText(
    start="{start}",
    end="{end}",
    speaker_lines=["- {name} — {voice}, from the second part on", "…"],
    transcript_lines=TRANSCRIPT_LINE_PLACEHOLDER,
)
_FULL_VIDEO_PLACEHOLDERS = FullVideoRequestText(
    language_name="{language name, when not auto}",
    part_line=build_film_part_line("{start}", "{end}", "{k}", "{n}") + " — with more than one part",
    character_prompts=CHARACTERS_PLACEHOLDER,
    earlier_answer="{the answer for the previous part, from the second part on}",
)
_LOCALIZATION_PLACEHOLDERS = CloneLocalizationRequestText(
    country_name="{target country}",
    target_setting="{target setting, when set}",
    allowed_changes=["{what may change, per ticked flag}"],
    candidate_lines=["{name} ({kind}) — {description}. Culture: {culture}. Period: {period}."],
)
_CLONE_SCRIPT_PLACEHOLDERS = CloneScriptRequestText(
    language_name="{script language}",
    country_name="{target country, when set}",
    target_setting="{target setting, when set} — neither set: keep the original.",
    asset_lines=["{name} ({kind}) — {description} (replaces {original name})"],
    shot_lines=[
        "{shotId} · {mm:ss} · {shot size} · {camera angle} · emotion: {emotion} · "
        "action: {action} · assets: {names}"
    ],
    video_notes=VIDEO_NOTES_PLACEHOLDER,
)
