# 2. Bộ prompt (Prompt Presets)

> One file = one domain. Every section below belongs to the **Prompt Presets** domain.

Named sets of the nine prompts the AI model (domain 8) runs inside the job pipelines, Film Clone and Film
Studio. The user sees the default text, edits it, keeps several presets, and picks one when creating a job;
the job copies the prompts it needs at that moment (2.5). The same prompts serve Claude and Gemini.

| Prompt | Key | Used by | Step |
|---|---|---|---|
| Video → Markdown | `videoToMarkdown` | Video to Markdown (1.5), Film Analysis (3.2), Film Clone (5.1) | `picking_moments` |
| Character image prompts | `characterImage` | Film Analysis (3.3) | `writing_character_image_prompts` |
| Character voice prompts | `characterVoice` | Film Analysis (3.3) | `writing_character_voice_prompts` |
| Scene prompts | `scene` | Film Analysis (3.3) | `writing_scene_prompts` |
| Film script | `filmScript` | Film Studio (4.2) | `writing_script` |
| Clone assets | `cloneAssets` | Film Clone (5.2) | `extracting_assets` |
| Clone shots | `cloneShots` | Film Clone (5.2) | `analyzing_shots` |
| Clone localization | `cloneLocalization` | Film Clone (5.3) | `proposing` |
| Clone script | `cloneScript` | Film Clone (5.4) | `writing_script` |

- Persona: the same single local user as domain 1. No login; no captcha on preset routes.
- Entities: `PromptPreset` (table `prompt_presets`), `PromptPresetVersion` (table `prompt_preset_versions`).
- The user edits only the instructions. The parts the code depends on — output shape, counts, the
  transcript, the video notes — are added by the app and shown read-only (2.2).
- The default text of each prompt lives in the API code, not in the database.

## 2.1 Preset & versions

### Data model — `PromptPreset`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `name` | string(50) | trimmed; unique, case-insensitive |
| `is_system` | boolean | `true` only for `Default` |
| `is_default` | boolean | the preset preselected in every job form; exactly one row is `true` |
| `current_version` | int | `version` of the newest `PromptPresetVersion` |
| `created_at` / `updated_at` | datetime (UTC) | |

### Data model — `PromptPresetVersion`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `preset_id` | string(36) | → `prompt_presets.id`; deleted with the preset |
| `version` | int | 1, 2, 3 … per preset; never reused, even after pruning |
| `change` | enum | `created` \| `saved` \| `restored` \| `duplicated` \| `imported` |
| `change_source` | string(120) \| null | `v{n}` for `restored`, `{name} v{n}` for `duplicated`, the file name for `imported` |
| `video_to_markdown` / `character_image` / `character_voice` / `scene` / `film_script` / `clone_assets` / `clone_shots` / `clone_localization` / `clone_script` | text | the nine prompts |
| `created_at` | datetime (UTC) | |

Unique (`preset_id`, `version`). A preset's current prompts are those of version `current_version`.

### Version rules

- `Save` with prompts different from the current version writes version `current_version + 1`,
  `change = saved`. Prompts identical to the current version write no version.
- Renaming changes `name` only; it writes no version.
- Restoring `v{n}` writes a new version with the prompts of `v{n}`, `change = restored`,
  `change_source = v{n}`. History stays linear; no version is edited.
- Each preset keeps its 20 newest versions. Writing the 21st deletes the oldest.
- Jobs hold copies, never a reference to a version (2.5), so pruning or deleting changes no job.

### `Default` preset

- Created at API start when no `Default` row exists: version 1 = the code defaults (2.2),
  `change = created`, `is_system = true`.
- On API start, no row with `is_default = true` → `Default` gets it.
- Edited, versioned and restored like any preset; cannot be renamed or deleted.

## 2.2 Prompts & what the app adds

Each prompt is the system prompt of one call of the model of its step group (8.1, 8.2). The app writes the user message
from fixed parts the preset cannot change; the editor shows them read-only under `Added by the app`.

### Video → Markdown (`videoToMarkdown`)

Default asks the model to:
- choose the key moments of a timestamped transcript — the points where the topic, the step being
  demonstrated, or what is on screen changes;
- start each moment at the start of one transcript line, the first at the first line;
- give the video a short title and a 2–3 sentence summary;
- write the title, summary and moment titles in the transcript's language.

Added by the app:
- Output shape (JSON schema): `title`, `summary`, `moments[] { atMs, title }`. Frames are captured at
  `atMs`, so the shape is fixed.
- `inputMode` `subtitles`: `Choose at most {N} key moments. Set atMs to the start time of the line where
  the moment begins.` — `{N}` = `MAX_MOMENTS` for Video to Markdown, ⌊max frames ÷ 2⌋ for Film Analysis
  and Film Clone — then the transcript, one line per segment as `[{start_ms}ms] {text}`.
- `inputMode` `whole_video`: one message per window, as 8.3 — the part's times and moment count, its
  transcript lines, and its frames at one per second.

The reply is normalised as in 1.5 whatever the instructions say.

### Character image prompts (`characterImage`)

Default asks the model to:
- list every recurring character seen in the frames or named in the notes — by name, else by a short
  label such as `Woman in red coat`; skip crowds and one-off extras;
- give each character's role, the timestamps where they appear, and two English image prompts: a
  head-and-shoulders reference portrait and a full-body shot on a plain background;
- cover apparent age range, build, face, hair, skin tone, outfit, accessories, usual expression, and
  the film's visual style (live action or animation, era, lighting);
- describe only what is visible or stated, marking guesses `(inferred)`;
- answer in Markdown, one `##` per character.

### Character voice prompts (`characterVoice`)

Default asks the model to:
- cover every character who speaks, using the labels of the character image prompts;
- write one English voice-design prompt each: gender presentation, apparent age, pitch, pace, timbre,
  accent, usual emotion and delivery;
- quote 1–3 short lines of that character from the transcript, in the original language;
- mark a line or trait attributed by guess `(inferred)` — the transcript has no speaker labels;
- answer in Markdown, one `##` per character.

### Scene prompts (`scene`)

Default asks the model to:
- write one prompt per distinct shot in the frames, in time order, headed `## {timestamp} — {short title}`;
- write each as an English video-generation prompt for a similar shot: subject and action, setting,
  time of day, shot size, camera angle and movement, lighting, colour palette, mood, 5–8 s length;
- refer to characters by the labels of the character image prompts.

Added by the app, for the three prompts above:
- The video notes (3.2) under a `Video notes:` heading.
- `The frames referenced in the notes are attached below as images, each after its file name. Look at
  them to see the characters and scenes.` — followed by the frames of the job, at most the images per call
  of the model (3.3), each image after a text block with its path (`images/moment-01-00m00s.jpg`).
- Voice and scene prompts only: the character image prompts answer of the same job under a
  `Characters:` heading, so the labels match.

### Film script (`filmScript`)

Default asks the model to:
- write one episode of a series as scenes, one shot and one clip each, opening on a visual hook in the
  first 3 s and ending on an unanswered question; a later episode picks up the previous cliffhanger in its
  first scene;
- give each scene the clip length its action needs, 4–30 s: a quick beat short, a held or travelling moment
  long;
- write each image prompt as action, setting, framing, lens and light — never faces, hair or build, which
  the reference images carry; only a change of clothing is described;
- write each video prompt as timed beats of 2–4 s that cover the scene's clip length (`0-3s`, `3-6s`,
  `6-8s` for an 8 s clip), the camera movement as a sentence of its own, the lighting, the sounds heard,
  and end it with `Negative: subtitles, watermark, text overlay`;
- put at most two named characters in a scene, crowds blurred in the background, and never two shots of
  the same size in a row;
- write narration that tells what the picture cannot show — motive, stakes, the ticking clock — never what
  is on screen: 18–22 words in Vietnamese, 20–24 in English, 12–16 when characters speak, for a 7 s window,
  scaled to the scene's clip length;
- give a music prompt (genre, instruments, tempo, mood) and a thumbnail prompt (one striking frame, no
  text);
- write character names exactly as the cast gives them.

Added by the app:
- Output shape (JSON schema): `title`, `logline`, `characters[] { name, entityType, description,
  voiceDescription, referenceFrame }`, `scenes[] { imagePrompt, videoPrompt, narratorText,
  characterNames[], durationS }`, `musicPrompt`, `thumbnailPrompt`. Scenes and characters are built from
  it, so the shape is fixed.
- The user message of 4.2 § `writing_script`: series, premise, language, frame, style, the target length
  with the 4–30 s range and the project's typical clip length, the dialogue and narration lines, the cast,
  earlier episodes, and the idea or the film analysis.

The reply is normalised as in 4.2 whatever the instructions say.

### Clone assets (`cloneAssets`)

Default asks the model to:
- list the characters, costumes, props and locations that recur or matter to the story, seen in the frames
  or named in the notes; skip crowds and one-off background items;
- name each as the film does, else by a short label such as `Red lacquer fan`, and describe how it looks;
- give the culture or country it comes from and its historical period, judged from clothing, architecture,
  objects, language and setting — `Unknown` when the film gives no clue, never a country guessed from a
  face alone;
- list the frames it appears in, the clearest view first.

Added by the app:
- Output shape (JSON schema): `assets[] { kind, name, description, culture, period, frames[] }`, `kind` one
  of `character`, `costume`, `prop`, `location`.
- The video notes and the frames, as for the three Film Analysis prompts above.

### Clone shots (`cloneShots`)

Default asks the model to:
- look at each frame on its own and give its shot size and camera angle;
- describe the main characters' emotion in a few words and what they do in one sentence;
- list the assets visible in the frame.

Added by the app:
- Output shape: `shots[] { frame, shotSize, cameraAngle, emotion, action, assetNames[] }`, `shotSize` and
  `cameraAngle` restricted to the lists of 5.2.
- `Give exactly one entry per frame.`, the assets as `{name} ({kind})`, the video notes and the frames of
  one batch (5.2).

### Clone localization (`cloneLocalization`)

Default asks the model to:
- move each candidate asset to the target country, changing only what the message allows;
- keep its role in the story and its period — the equivalent period in the target country — and the colours
  or shapes the plot depends on;
- leave an asset unchanged when it already fits the target country;
- write the localized description as a self-contained English image description, and a one-line note on
  what changed.

Added by the app:
- Output shape: `assets[] { name, changed, localizedName, localizedDescription, note }`.
- The user message of 5.3 § `proposing`: target country, the target setting when set, the allowed changes,
  the candidates with culture and period, each candidate's reference frame.

### Clone script (`cloneScript`)

Default asks the model to:
- retell the film shot by shot, keeping the plot, the order and the emotion of every shot;
- write each description as what the viewer sees, and the dialogue from the video notes in the script
  language with the original tone and register;
- write each image prompt in English — the subjects by asset name and look, the action, the setting, the
  shot size and camera angle, light and mood — so the image can be made without seeing the film;
- give a title and a one-sentence logline in the script language.

Added by the app:
- Output shape: `title`, `logline`, `scenes[] { shotId, description, dialogue, imagePrompt }`.
- The user message of 5.4 § `writing_script`.

The replies of the four clone prompts are normalised as in 5.2–5.4 whatever the instructions say.

## 2.3 Rules & validation

| Rule | Result |
|---|---|
| Request misses `name` or a prompt | 422 |
| `name` trimmed is 1–50 characters | 400 `Preset name must be 1-50 characters` |
| `name` unique, case-insensitive | 409 `A preset named '{name}' already exists` |
| Each prompt trimmed is 1–20000 characters | 400 `Prompt '{key}' must be 1-20000 characters` |
| Renaming `Default` | 409 `The Default preset cannot be renamed` |
| Deleting `Default` | 409 `The Default preset cannot be deleted` |
| Deleting the default preset | 409 `Set another preset as default before deleting '{name}'` |
| Unknown preset | 404 `Prompt preset {id} not found` |
| Unknown or pruned version | 404 `Version {n} of preset {id} not found` |

- `Set as default` moves `is_default` in one transaction; the previous default loses it.
- Deleting a preset removes its versions; jobs keep their copies.

## 2.4 New, duplicate, export, import

### New preset

- Takes a `name`; version 1 = the code defaults, `change = created`.

### Duplicate

- Name `{name} (copy)`, then `{name} (copy 2)`, `(copy 3)` … while taken; the base name is cut so the
  whole fits 50 characters.
- Version 1 = the source's current prompts, `change = duplicated`, `change_source = {source name} v{n}`.

### Export

Attachment `{safe name}.preset.json` — `{safe name}` built like `{stem}` in 1.6, empty → `preset`:

```json
{
  "format": "video-tool-prompt-preset",
  "formatVersion": 3,
  "name": "Anime",
  "prompts": { "videoToMarkdown": "…", "characterImage": "…", "characterVoice": "…", "scene": "…", "filmScript": "…",
               "cloneAssets": "…", "cloneShots": "…", "cloneLocalization": "…", "cloneScript": "…" }
}
```

Current prompts only — no history, no default flag.

### Import

Multipart `file`.

| # | Rule | Result |
|---|---|---|
| 1 | File ≤ 1 MB | 413 `Preset file exceeds 1 MB` |
| 2 | JSON with `format` = `video-tool-prompt-preset`, `formatVersion` 1, 2 or 3, string `name`, and string prompts — the first four keys for 1, the first five for 2, all nine for 3 | 400 `Not a prompt preset file` |
| 3 | Name and prompt rules of 2.3 | 400 as in 2.3 |

- A `formatVersion` 1 file has no `filmScript` and no clone prompt, a `formatVersion` 2 file no clone prompt;
  the imported preset gets the code default for each missing one.
- Name taken → `{name} (imported)`, then `(imported 2)` …, cut to fit as for duplicates.
- Version 1, `change = imported`, `change_source` = the uploaded file name cut to 120 characters.

## 2.5 Using a preset in a job

- Every job creation route takes an optional `presetId`; absent → the default preset. Unknown →
  400 `Prompt preset {id} not found`.
- At creation the API copies into `Job.options`:

| Key | Value |
|---|---|
| `preset` | `{ "id", "name", "version" }` at that moment |
| `prompts` | `videoToMarkdown` for Video to Markdown; `videoToMarkdown`, `characterImage`, `characterVoice`, `scene` for Film Analysis; `characterImage`, `characterVoice`, `scene` for a rerun (3.4); `videoToMarkdown`, `cloneAssets`, `cloneShots` for a Film Clone job (5.1) |

- Steps read prompts from `options.prompts` only. Editing, restoring or deleting the preset afterwards
  changes no job, pending ones included.
- A job without `options.prompts` uses the code defaults.
- Job screens show `Prompt preset` as `{name} v{n}`, or `—` without `options.preset`.
- A Film Studio episode is not a job: its creation takes the same optional `presetId` and copies `preset`
  and the `filmScript` prompt into the episode (4.2), with the same rules.
- A Film Clone creation also copies `preset` and the `cloneLocalization` and `cloneScript` prompts into the
  clone (5.1), with the same rules.

## 2.6 Tab `Prompt override` of `/settings`

The presets are edited in the `Prompt override` tab of the Settings screen (6.2):
`/settings?tab=prompt-override`. `&id={id}` selects a preset; without it the default preset is selected.
The page `/prompt-presets` and `/settings?tab=prompt-presets` redirect there and keep `id`. The tab opens
with the line `The prompts the AI model follows in every job. Each job copies the prompts of the preset
chosen when it is created.`

**Panel "Presets"**

- `Default` first, then by name. Row: name, badge `Default preset` on the default one, badge `System`
  on `Default`, `v{n}`, updated time.
- `New preset` → `Name` field with `Create` / `Cancel` in the panel → creates, selects it.
- `Import` → `.json` file picker → creates, selects it, notice `Imported as '{name}'`.

**Panel "Editor"** — the selected preset

- `Name` field, disabled on `Default`.
- One section per prompt, in the order of the table above: title, `Used by` line, badge `Default`
  (text equals the code default) or `Customized`, text area with counter `{n} / 20000`,
  `Reset to default` (puts the code default in the text area; unsaved until `Save`), collapsed
  `Added by the app` with the read-only parts of 2.2.
- Actions: `Save` (enabled only with unsaved changes), `Discard changes`, `Set as default` (hidden on the
  default preset), `Duplicate`, `Export`, `History`, `Delete` (hidden on `Default`; disabled on the
  default preset with the hint `Set another preset as default first`).
- `Save` → notice `Saved as v{n}` when a prompt changed, `Renamed to '{name}'` when only the name did.
- `Set as default` → notice `'{name}' is now the default`. `Duplicate` → the copy is selected.
- `Delete` → confirm `Delete preset '{name}'? Jobs that used it keep their prompts.` → the default
  preset is selected.
- Selecting another preset, `Duplicate` or opening `History` with unsaved changes → confirm
  `Discard unsaved changes?`. Switching Settings tab or leaving the page follows 6.2.
- An error shows an alert with the API `detail` and keeps the edits.

**Panel "History"**

- The kept versions, newest first: `v{n}` · created time · change — `Created`, `Saved`,
  `Restored from v{n}`, `Duplicated from {name} v{n}`, `Imported from {file}`; the current one tagged
  `Current`.
- Clicking a row shows its prompts read-only.
- `Restore` on any row except `Current` → new version → notice `Restored v{n} as v{m}`; the editor
  shows it.

---

## API endpoints

Same JSON and error conventions as domain 1. Prompt keys in JSON: `videoToMarkdown`,
`characterImage`, `characterVoice`, `scene`, `filmScript`, `cloneAssets`, `cloneShots`,
`cloneLocalization`, `cloneScript`.

```
GET    /prompt-presets                              — PromptPreset[] (Default first, then by name)
POST   /prompt-presets                              — { "name" } → 201 PromptPresetDetail
GET    /prompt-presets/defaults                     — code defaults of the nine prompts + the app-added parts (2.2)
GET    /prompt-presets/{id}                         — PromptPresetDetail
PUT    /prompt-presets/{id}                         — { "name", "prompts" } → PromptPresetDetail
DELETE /prompt-presets/{id}                         — 204
POST   /prompt-presets/{id}/default                 — make it the default preset → PromptPreset
POST   /prompt-presets/{id}/duplicate               — 201 PromptPresetDetail
GET    /prompt-presets/{id}/versions                — PromptPresetVersion[] newest first, without prompts
GET    /prompt-presets/{id}/versions/{n}            — one version with prompts
POST   /prompt-presets/{id}/versions/{n}/restore    — PromptPresetDetail
GET    /prompt-presets/{id}/export                  — application/json attachment `{safe name}.preset.json`
POST   /prompt-presets/import                       — multipart `file` → 201 PromptPresetDetail
```

| Route | Errors |
|---|---|
| `POST /prompt-presets` | 400 name · 409 duplicate name · 422 no `name` |
| `PUT /prompt-presets/{id}` | 400 name / prompt · 404 · 409 duplicate name / rename `Default` · 422 missing field |
| `DELETE /prompt-presets/{id}` | 404 · 409 `Default` / default preset |
| `POST …/default`, `…/duplicate`, `GET …/export`, `GET …/versions` | 404 |
| `GET …/versions/{n}`, `POST …/versions/{n}/restore` | 404 preset / version |
| `POST /prompt-presets/import` | 400 not a preset / name / prompt · 413 too large · 422 no `file` |

`PromptPreset`: `id`, `name`, `isSystem`, `isDefault`, `currentVersion`, `createdAt`, `updatedAt`.
`PromptPresetDetail` = `PromptPreset` + `prompts`. `PromptPresetVersion`: `version`, `change`,
`changeSource`, `createdAt` (+ `prompts` on the single-version route).

## Configuration

No new keys. Fixed limits: 20 versions per preset, name 50 characters, prompt 20000 characters,
import file 1 MB.

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- History per prompt; a diff view between versions.
- Placeholders or templating inside a prompt; editing the output shape of `videoToMarkdown`.
- An AI model or timeout per preset, or a prompt per model.
- Sharing presets other than through export / import.
