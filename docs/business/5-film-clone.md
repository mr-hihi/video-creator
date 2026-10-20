# 5. Clone phim (Film Clone)

> One file = one domain. Every section below belongs to the **Film Clone** domain.

Clones a film — an uploaded file or a YouTube link — into a new script with images, optionally moved to
another country. It runs in four stages and waits for the user twice, both in stage 3 — at the localization
choices and at the review of the replacements — unless it was created to run every step automatically
(5.1 § Automatic run):

| # | Stage | Runs | Result |
|---|---|---|---|
| 1 | Video notes | on its own — the job of 5.1 | video notes stored in the DB + frames, as Film Analysis (3.2) |
| 2 | Assets & shots | on its own — the batch worker, right after the job | asset library (culture, period) and one shot per frame (5.2) |
| 3 | Localization | **waits for the user** for the choices, then for the review; on its own with an automatic run | target country, target setting, what to change, a replacement per asset with a new reference image (5.3) |
| 4 | Script & images | on its own, to the end | one scene per original shot: text, original frame, new image (5.4) |

A finished clone can be sent to Film Studio as an episode (4.2, source `film_clone`) to make clips and the film.

- Persona: the same single local user as domain 1. Captcha on the creation routes only, switched off as in
  domain 1.
- Entities: `FilmClone` (table `film_clones`), `CloneAsset` (`film_clone_assets`), `CloneShot`
  (`film_clone_shots`), `CloneScene` (`film_clone_scenes`); stage 1 runs as a `Job` (1.1) of type
  `film_clone` or `youtube_film_clone`, stage 2 in the batch worker after it; images are `GenerationRequest`s of Film Studio (4.3).
- Prompts: `videoToMarkdown`, `cloneAssets`, `cloneShots`, `cloneLocalization`, `cloneScript` of a prompt
  preset (domain 2), copied at creation (2.5).
- AI models: those of the `moments` and, in `whole_video`, `audio` (stage 1) and `filmClone` (stages 2–4)
  step groups, read when each call starts (domain 8). Input mode: the `filmCloneInputMode` setting, copied
  into the stage 1 job at creation.
- Script language: the `Script language` setting of Settings (domain 6) and the target country (5.3).
- External tools: as domain 3, plus the image providers of Film Studio (4 § Media providers).

## 5.1 Clone, job & stages

### Data model — `FilmClone`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `job_id` | string(36) | → `jobs.id`, the stage 1 job; deleted with the clone |
| `status` | enum | `running` \| `waiting` (for the user) \| `done` \| `failed` |
| `step` | enum | `analyzing` \| `extracting_assets` \| `analyzing_shots` \| `choosing_localization` \| `proposing` \| `reviewing` \| `writing_script` \| `generating_scene_images` — the step running, waiting, failed or last finished |
| `error_message` | text \| null | set when `failed` |
| `target_country` | enum \| null | a code of 5.3; `null` = keep the original setting |
| `target_setting` | text \| null | the setting the user wants, free text, e.g. `a modern Western city` (5.3); `null` = none |
| `change_appearance` / `change_costume` / `change_setting` | boolean | default `false` (5.3) |
| `should_run_automatically` | boolean | default `false`; `true` = the five fields above are set at creation and the clone never waits (§ Automatic run) |
| `script_language` | string(3) \| null | ISO code, fixed at stage 3 (5.3) |
| `aspect` | enum \| null | `16:9` \| `9:16` — width ≥ height of the frames → `16:9`; set when the job is `done` |
| `script_title` | string(150) \| null | from the script (5.4) |
| `logline` | text \| null | from the script |
| `preset` | JSON | `{ "id", "name", "version" }` at creation (2.5) |
| `prompts` | JSON | `cloneLocalization` and `cloneScript`, copied at creation (2.5) |
| `ai_used` | JSON | the model each AI step of stages 2–4 used, keyed by step (8.1); `{}` before the first |
| `flow_project_id` | string(36) \| null | the Google Flow project of its images; written and read only by the Google Flow provider |
| `created_at` / `updated_at` / `finished_at` | datetime (UTC) | |

The screens show the job's `source_filename`.

### The job (stage 1)

| Key of `Job.options` | Value |
|---|---|
| `language`, `url`, `videoId`, `captionKind` | as 1.2 / 1.3 |
| `maxFrames` | integer 10–1000, default 1000 |
| `frameCounts` | as 3.1 |
| `preset`, `prompts` | 2.5 — `prompts` = `videoToMarkdown`, `speakersAndSounds`, `cloneAssets`, `cloneShots` |
| `inputMode` | copied from `filmCloneInputMode` (6.1, 8.1) |
| `cloneId` | the clone `id` |

`inputMode` = `subtitles`:

| # | `film_clone` | `youtube_film_clone` |
|---|---|---|
| 1 | `extracting_audio` | `fetching_transcript` |
| 2 | `transcribing` | `picking_moments` |
| 3 | `picking_moments` | `downloading_video` |
| 4 | `detecting_scenes` | `detecting_scenes` |
| 5 | `capturing_frames` | `capturing_frames` |
| 6 | `writing_markdown` | `writing_markdown` |

- Steps 1–6 behave as in Film Analysis (3.1–3.2), failures included: dialogue frames + scene cuts, the
  `video_notes` row in `job_outputs`, frames in `storage/{job-id}/output/images/`.
- `inputMode` = `whole_video` (screen label `Frame image + audio`) adds `listening_to_audio` and
  `sampling_frames`, in that order, right before `picking_moments`, and YouTube downloads, with the audio,
  before them (8.3): the video notes name the speakers, and sound frames join the dialogue frames and scene
  cuts (3.2).
- Worker, single queue and requeue on restart: as 1.1. A requeued job runs from its first step and
  replaces its `video_notes` row, assets and shots.
- Job `done` → one shot per frame saved with empty values (5.2), `aspect` set, clone `running` at
  `extracting_assets`. Job `failed` → clone `failed` at `analyzing` with the job's `error_message`; this is
  final — the user creates a new clone.

### Status workflow

```
running·analyzing ──job done──▶ running·extracting_assets ──▶ running·analyzing_shots
   │                                                                   │
   └──job failed──▶ failed (final)                                     ▼
                       waiting·choosing_localization ──Localize, a flag ticked──▶ running·proposing
                            │                                                           │
                            └──Localize, no flag──▶ running·writing_script ◀──Write script── waiting·reviewing
                                                         │
                                                         ▼
                                          running·generating_scene_images ──▶ done

a step after the job fails ──▶ failed ──Resume──▶ running (same step)
```

| Action | Allowed at | Effect |
|---|---|---|
| `localize` | `waiting` · `choosing_localization` | 5.3 |
| `write-script` | `waiting` · `reviewing` | 5.3 § Write script |
| `resume` | `failed` at `extracting_assets`, `analyzing_shots`, `proposing`, `writing_script` or `generating_scene_images` | runs that step again; `generating_scene_images` queues only images that are `none` or `failed` |
| `relocalize` | `waiting` · `reviewing`; `done`; `failed` at `proposing`, `writing_script` or `generating_scene_images` | 5.4 § Back to localization |

| Rule | Result |
|---|---|
| Action not allowed at the current status and step | 409 `Cannot {action} clone {id} while it is {status} at {step}` |
| Unknown clone | 404 `Film clone {id} not found` |

### Automatic run

A clone created with `shouldRunAutomatically` takes its localization choices at creation and passes both
waits by itself:

| Wait | Instead |
|---|---|
| `waiting` · `choosing_localization`, after `analyzing_shots` | the stored choices are applied as `localize` applies them (5.3), `script_language` fixed at that moment: a flag ticked → `running` · `proposing`, else `running` · `writing_script` |
| `waiting` · `reviewing`, after `proposing` | no asset changed → `running` · `writing_script` at once; else it waits for the references, and the moment every changed asset's reference is `done` → `running` · `writing_script` |

- A failed reference keeps the clone `waiting` · `reviewing` (5.3). Once the user regenerates it and it is
  `done`, the clone goes on by itself; `Write script` and the reviewing actions stay available meanwhile.
- The assets cannot be edited before localization (5.2): the clone never waits at `choosing_localization`.
- `relocalize` (5.4) turns `should_run_automatically` off; from then on the clone waits as any other.

- `extracting_assets`, `analyzing_shots`, `proposing` and `writing_script` run in the batch worker of 1.1,
  between jobs, oldest first — one AI call at a time. An API restart runs an interrupted one again.
- Images run in the Film Studio generation worker (4.3). Each time a clone request becomes final, the
  clone's step is checked (5.3, 5.4).

### AI calls (stages 2–4)

- One call of the `filmClone` model (8.1, 8.2) with a JSON schema — one per batch for `analyzing_shots`
  (5.2) and `writing_script` (5.4); images go in after their paths, as in 3.3. The silence and run limits
  below apply to each call.
- The output streams: every Claude output line, Gemini chunk and OpenAI event is a sign of life. No output
  for `CLONE_AI_SILENCE_SEC`, or a call longer than `CLONE_AI_MAX_RUN_SEC`, is stopped and fails the step —
  never retried.
- While a call runs, the clone detail carries `aiActivity` (8.2).
- System prompt: the copied prompt of the step; the code default when absent (2.2).
- Failures: 8.2. `Resume` runs the step again on the `filmClone` model read at that moment (8.1).

## 5.2 Assets & shots (stage 2)

### `extracting_assets`

- Prompt `cloneAssets`. Message: the video notes under `Video notes:` and the frames of the job attached — at
  most `W` of them spread evenly, as the Film Analysis passes (3.3); `frames` may still name any frame of
  the job.
- Output shape: `assets[] { kind, name, description, culture, period, frames[] }`.
- Normalising: unknown `kind` or blank `name` → dropped; repeats of (`kind`, `name`) case-insensitive →
  dropped; blank `culture` / `period` → `Unknown`; `frames` keeps only frame files of the job; the first 60
  assets are kept. No asset is not an error.
- The assets replace any earlier ones; the clone moves to `analyzing_shots`.

### Data model — `CloneAsset`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `clone_id` | string(36) | → `film_clones.id`; deleted with the clone |
| `position` | int | order of the reply |
| `kind` | enum | `character` \| `costume` \| `prop` \| `location` |
| `name` | string(100) | unique per clone, case-insensitive |
| `description` | text | what it looks like in the film, 1–2000 characters |
| `culture` | string(100) | country or culture it comes from, e.g. `Korean`; `Unknown` when unclear |
| `period` | string(100) | historical period, e.g. `Joseon dynasty (1392–1897)`, `Present day`; `Unknown` when unclear |
| `frames` | JSON | frame files it appears in |
| `reference_frame` | string \| null | the first of `frames`; its reference image while it is not changed |
| `changed` | boolean | `true` when stage 3 replaces it |
| `localized_name` / `localized_description` | string(100) / text \| null | the replacement, set while `changed` |
| `localization_note` | string(300) \| null | the model's reason for the change |
| `reference_status` | enum | `none` \| `queued` \| `processing` \| `done` \| `failed` — the generated reference, only when `changed` |
| `reference_path` / `reference_error` | string / text \| null | |

### `analyzing_shots`

- Prompt `cloneShots`. Message: the video notes, the assets as `{name} ({kind})`, the frames attached.
- The frames go in batches of at most `W` (3.3), in time order: one call per batch, the same message each
  time. The `shots` of every reply are joined, then normalised as below as one reply.
- Output shape: `shots[] { frame, shotSize, cameraAngle, emotion, action, assetNames[] }`.
- The job saves every frame as exactly one shot, in time order, with empty values; `analyzing_shots` fills
  them: a frame the reply skips, or a repeat, gets the first reply entry for it or empty values. A value outside the lists below → `null`. `assetNames`
  resolve against the assets case-insensitively, with or without the ` ({kind})` the message shows; unknown
  names and repeats are dropped. Then the clone waits at `choosing_localization`.
- A reply that places no shot on any captured frame fails the step and saves nothing:
  `{ai} returned no shots`, or `{ai} named no captured frame: [{up to 5 names}]`. A reply that misses
  only some frames is saved as above.

### Data model — `CloneShot`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `clone_id` | string(36) | → `film_clones.id`; deleted with the clone |
| `position` | int | 0, 1, 2 … in time order |
| `at_ms` | int | time of the frame |
| `frame` | string | `images/moment-…jpg` |
| `frame_kind` | enum | `dialogue` \| `sound` \| `scene` — from the merge of 3.2 |
| `shot_size` | enum \| null | `extreme_wide` \| `wide` \| `full` \| `medium` \| `medium_close` \| `close_up` \| `extreme_close_up` |
| `camera_angle` | enum \| null | `eye_level` \| `high` \| `low` \| `birds_eye` \| `worms_eye` \| `dutch` \| `over_the_shoulder` \| `pov` |
| `emotion` | string(200) \| null | the characters' emotion, free text |
| `action` | text \| null | what the characters do, at most 1000 characters |
| `asset_ids` | JSON | assets seen in the shot |

Shots are read-only.

| `shot_size` | Label | | `camera_angle` | Label |
|---|---|---|---|---|
| `extreme_wide` | Extreme wide | | `eye_level` | Eye level |
| `wide` | Wide | | `high` | High angle |
| `full` | Full | | `low` | Low angle |
| `medium` | Medium | | `birds_eye` | Bird's-eye |
| `medium_close` | Medium close-up | | `worms_eye` | Worm's-eye |
| `close_up` | Close-up | | `dutch` | Dutch angle |
| `extreme_close_up` | Extreme close-up | | `over_the_shoulder` | Over the shoulder |
| | | | `pov` | POV |

### Editing assets before localization

At `waiting` · `choosing_localization` the user edits `name`, `kind`, `description`, `culture`, `period`,
or deletes an asset — deleting removes it from every shot's `asset_ids`.

| Rule | Result |
|---|---|
| `name` trimmed is 1–100 characters | 400 `Asset name must be 1-100 characters` |
| `name` unique in the clone, case-insensitive | 409 `An asset named '{name}' already exists in this clone` |
| `description` trimmed is 1–2000 characters | 400 `Description must be 1-2000 characters` |
| `culture`, `period` trimmed are 1–100 characters | 400 `Culture and period must be 1-100 characters` |
| Clone at another step | 409 `Assets can be edited only before localization` |
| Unknown asset | 404 `Asset {id} not found` |

## 5.3 Localization (stage 3)

### Choices — `POST /film-clones/{id}/localization`

| Code | Country | Language |
|---|---|---|
| `vn` | Vietnam | `vi` Vietnamese |
| `jp` | Japan | `ja` Japanese |
| `kr` | South Korea | `ko` Korean |
| `cn` | China | `zh` Chinese |
| `us` | United States | `en` English |
| `gb` | United Kingdom | `en` English |
| `fr` | France | `fr` French |
| `th` | Thailand | `th` Thai |
| `in` | India | `hi` Hindi |
| `id` | Indonesia | `id` Indonesian |

| # | Rule | Result |
|---|---|---|
| 1 | Clone `waiting` at `choosing_localization` | 409 as 5.1 |
| 2 | `targetCountry` is `null` or a code above | 400 `Unknown country '{code}'` |
| 3 | A flag is `true` → `targetCountry` set | 400 `Pick a target country to change appearance, costume or setting` |

`targetSetting` is optional free text with no length limit, trimmed; blank → `null`. It needs no target
country and ticks no flag: only the ticked flags decide which assets may change.

`script_language`, fixed now:

| `Script language` setting (domain 6) | Target country set | No target country |
|---|---|---|
| `Follow target country` (default) | the country's language | the transcript's language (1.2 / 1.4) |
| a fixed language | that language | that language |

The tone and register of the dialogue always stay those of the original film.

- No flag ticked → every asset stays unchanged; the clone goes to `running` · `writing_script`.
- A flag ticked → `running` · `proposing`.

### `proposing`

| Flag | Asset kinds it may change | What may change |
|---|---|---|
| `change_appearance` | `character` | face, skin tone, hair, build — the person reads as from the target country |
| `change_costume` | `character`, `costume` | clothing and accessories |
| `change_setting` | `location`, `prop` | architecture, landscape, signs, objects |

- Candidates = assets of a kind a ticked flag covers. No candidate → straight to `waiting` · `reviewing`.
- Prompt `cloneLocalization`. Message: `Target country: {country}`; when `target_setting` is set,
  `Target setting: {target setting}` and `Follow the target setting where it differs from the original
  period or place.`; `Change only: {what may change, per ticked flag}`; every candidate as `{name} ({kind}) — {description}. Culture: {culture}. Period: {period}.`;
  each candidate's `reference_frame` attached.
- Output shape: `assets[] { name, changed, localizedName, localizedDescription, note }`.
- Normalising: `name` matches a candidate case-insensitively, with or without the ` ({kind})` the message
  shows, else dropped, repeats too; `changed` with a blank `localizedDescription` → not changed; a trailing
  ` ({kind})` is dropped from `localizedName`, and a blank one → the original name; cut to 100 / 2000 / 300
  characters; a candidate missing from the reply → not changed.
- Then `waiting` · `reviewing`, and one `clone_reference_image` request (4.3) is queued for every changed
  asset.

### Reference image of a changed asset

| `kind` | Composition and aspect |
|---|---|
| `character` | as `character` in 4.1 § Built `image_prompt` |
| `costume`, `prop` | as `visual_asset` |
| `location` | as `location` |

- Prompt: `Reference image of {localized_description}. {composition}`. No input image. Provider: the
  `filmCloneImageProvider` setting (6.1) when queued.
- A failed reference stays on its card with the error; the clone keeps `waiting` · `reviewing`.
- Each time a reference becomes final, an automatic clone is checked (5.1 § Automatic run).

### Reviewing

At `waiting` · `reviewing` the user, per asset:

| Action | Rule | Result |
|---|---|---|
| Edit `localizedName`, `localizedDescription` | `changed`; lengths as 5.2 | 400 as 5.2 · 409 `Asset '{name}' is not changed` |
| `Keep original` (`changed: false`) | — | localized fields cleared, generated reference deleted, `reference_status = none` |
| `Change this` (`changed: true` + `localizedDescription`) | `localizedDescription` given or stored | 400 `Describe the localized asset first` |
| Generate / regenerate the reference | `changed` | 409 `Asset '{name}' is not changed` · 202 |
| Any of the above | no reference request of the asset `queued` or `processing` | 409 `Asset '{name}' has generation running` |
| Edit at another step | — | 409 `Localized fields can be edited only while reviewing` |

A text change keeps the current reference; the user regenerates it to get the new look.

### Write script — `POST /film-clones/{id}/write-script`

| Rule | Result |
|---|---|
| Clone `waiting` at `reviewing` | 409 as 5.1 |
| Every changed asset has its reference `done` | 409 `Reference images missing for: {names}` |

→ `running` · `writing_script`.

## 5.4 Script & scene images (stage 4)

### `writing_script`

- Prompt `cloneScript`. Message written by the app:
  - `Script language: {language}. Keep the tone and register of the original dialogue.`
  - `Setting: {country}`, `Setting: {country}. {target setting}`, `Setting: {target setting}` — whichever of
    the two is set — or `Setting: keep the original.` when neither is.
  - `Write exactly one scene per shot, in the order given, each with its shotId.`
  - `Assets:` — every asset as `{name} ({kind}) — {description}`, using the localized name and description
    when changed, followed by `(replaces {original name})`.
  - `Shots:` — one line each: `{shotId} · {mm:ss} · {shot size label or —} · {camera angle label or —} ·
    emotion: {emotion} · action: {action} · assets: {names}`.
  - The video notes under `Video notes:` — the source of the dialogue. No image is attached.
- Output shape: `title`, `logline`, `scenes[] { shotId, description, dialogue, imagePrompt }`.
- The shots go in batches of `CLONE_SCRIPT_SHOTS_PER_CALL`, in order: one call per batch, each with the
  whole message but only its own shots. The `scenes` of every reply are joined; `title` and `logline` come
  from the first reply. The rules below apply to the joined reply.

Normalising:

1. Drop scenes whose `shotId` is unknown or repeated, or whose `description` or `imagePrompt` is blank.
2. A shot left without a scene → `failed`, `{ai} returned no scene for {n} of {m} shots`.
3. Trim; blank `dialogue` → `null`; cut `description` and `dialogue` to 2000, `imagePrompt` to 4000.
4. Blank `title` → the `{stem}` of `source_filename` (1.6); cut to 150 characters.

Scenes are saved in shot order with the shot's `asset_ids`, `image_status = none`, then
`running` · `generating_scene_images`.

### Data model — `CloneScene`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `clone_id` | string(36) | → `film_clones.id`; deleted with the clone |
| `shot_id` | string(36) | → `film_clone_shots.id`; one scene per shot |
| `position` | int | the shot's position |
| `description` | text | what happens on screen, in `script_language`, 1–2000 characters |
| `dialogue` | text \| null | one `{name}: {line}` per line, in `script_language`, at most 2000 characters |
| `image_prompt` | text | English, localized, 1–4000 characters |
| `asset_ids` | JSON | the shot's assets |
| `image_status` | enum | `none` \| `queued` \| `processing` \| `done` \| `failed` |
| `image_path` / `image_error` | string / text \| null | |

### `generating_scene_images`

- One `clone_scene_image` request (4.3) per scene whose image is `none` or `failed`.
- Prompt: `{image_prompt} Shot: {shot size label}, {camera angle label}.` — the `Shot:` part only with the
  values set. Input: the original frame of the scene's shot, as the source image — one call makes one
  image, and the prompt carries the localization; asset references are not sent. Aspect: the clone's
  `aspect`. Provider: the `filmCloneImageProvider` setting
  (6.1) when queued.
- When every scene image is final: all `done` → `done`, `finished_at` set; else `failed`,
  `{n} scene image(s) failed — fix them and resume`. The same check runs after a single regenerate, so a
  `failed` clone becomes `done` once every image is.

### Editing scenes

Allowed when the clone is `done` or `failed` at `generating_scene_images`.

| Action | Rule | Result |
|---|---|---|
| Edit `description`, `dialogue`, `imagePrompt` | lengths as the data model | 400 `Description must be 1-2000 characters` / `Dialogue must be at most 2000 characters` / `Image prompt must be 1-4000 characters` |
| Generate / regenerate the image | — | 202 |
| Either | no request of the scene `queued` or `processing` | 409 `Scene {n} has generation running` |
| Either, at another status | — | 409 `Scenes can be edited once the script is written` |
| Unknown scene | — | 404 `Scene {id} not found` |

- A text change keeps the image; the user regenerates it.

### Back to localization — `POST /film-clones/{id}/relocalize`

| Rule | Result |
|---|---|
| Allowed status and step (5.1) | 409 as 5.1 |
| No request of the clone `queued` or `processing` | 409 `Film clone {id} has image generation running` |

Deletes the scenes and their images, `script_title`, `logline`, and every asset's localized fields and
generated reference; sets `should_run_automatically` to `false`; the clone goes to `waiting` ·
`choosing_localization`. Target country, target setting and flags stay, so the form opens with them.

### Files

| Path | Content |
|---|---|
| `storage/{job-id}/output/images/` | the frames (job) |
| `storage/film-clones/{clone-id}/references/{asset-id}.{ext}` | generated references |
| `storage/film-clones/{clone-id}/scenes/{scene-id}.{ext}` | scene images |

A new file replaces the old one.

## 5.5 Delete

`DELETE /film-clones/{id}` removes the clone, its assets, shots, scenes and generation requests, its job with
the `job_outputs` rows and `storage/{job-id}/`, and `storage/film-clones/{id}/`.

| Rule | Result |
|---|---|
| Clone exists | 404 `Film clone {id} not found` |
| Not `running`, and no request of the clone `queued` or `processing` | 409 `Film clone {id} is still running` |

Film Studio episodes made from it keep their copies; their `Source` shows `(deleted)`.

## 5.6 Screens

Header menu as in 1.7; every `/film-clone…` page highlights `Film Clone`. An API error shows an alert with
its `detail` and keeps what the user typed.

### `/film-clone` — Film Clone

**Panel "New clone"** — as the `New analysis` panel of 3.6, with:

- `Max frames` 10–1000, default 1000, hint `One scene per frame in the script.`, always shown.
- Checkbox `Run every step automatically`, unticked, hint `Skips the localization choices and the review,
  using the choices below.` Ticked → below it `Target country`, `Target setting` and `Appearance` /
  `Costume` / `Setting`, as the `Localization` tab at `choosing_localization` (without the script language
  line).
- Above the captcha, after the `AI` line (8.4): the read-only line `Images with: {provider name}` — the
  provider `filmCloneImageProvider` resolves to (6.1) — with a link `Change` → `/settings?tab=film-clone`.
- Submit button `Clone`. Success → `/film-clone/{id}`.

**Panel "Clone history"**

- The 50 newest clones. Row: `source_filename` (link), source badge `Upload` / `YouTube`, target country
  or `Original`, step label · created time, status badge, `View`, `Delete` (not while 5.5 refuses).
- `Delete` → confirm `Delete this clone? The video, frames, assets, script and images are removed.` → the row
  disappears.
- Empty → `No clones yet`. Refreshes every 3 s while any listed clone is `running` or has a request
  `queued` / `processing`.

### `/film-clone/{id}` — Clone

- Header: `source_filename`, status badge, `Send to Film Studio` (enabled only when `done`), `Delete` (as in
  the history; afterwards → `/film-clone`).
- Stage bar: `Video notes` · `Assets & shots` · `Localization` · `Script & images`, each `completed` /
  `current` / `waiting` / `failed` / `upcoming`. While `analyzing`, the job's steps show under it with the
  labels of 1.7 and 3.6 and below. While an AI call runs, a line below reads `{model label} is working ·
  {mm:ss since the call started} · last output {n}s ago` (`no output yet` before the first output).
  `failed` → error alert with `error_message`, and `Resume` when 5.1 allows it.
- Summary: `Language`, `Prompt preset` (`{name} v{n}`), `AI`, `Input` (8.4), `Frames` (as 3.6),
  `Target country`, `Target setting` (only when set), `Script language`, `Created`. YouTube adds `Source` and `Captions` as
  1.7.
- Tabs, the first one with content open, a tab without content reading `Waiting…` while the clone runs;
  `Shots` and `Localization` have content only once `analyzing_shots` is over:

| Tab | Content |
|---|---|
| `Video notes` | as the `Video notes` tab of 3.6, with `Copy` |
| `Assets` | groups `Characters`, `Costumes`, `Props`, `Locations`; card: reference frame, name, culture, period, description, `{n} frames`. At `choosing_localization`: `Edit` (form of 5.2) and `Delete` (confirm `Delete asset '{name}'?`). A changed asset shows `Original` and `Localized` side by side |
| `Shots` | one row per shot in time order: frame (click to enlarge), timestamp (YouTube: link to that second), badge `Dialogue` / `Sound` / `Scene change`, shot size, camera angle, emotion, action, asset chips; filters `Shot size` and `Camera angle` |
| `Localization` | below |
| `Script` | below |

**Tab "Localization"**

- At `choosing_localization`: `Target country` (`Keep original` first, then the countries of 5.3); text area
  `Target setting`, empty, hint `Optional. e.g. a modern Western city instead of an ancient Chinese court`,
  enabled with `Keep original` too; checkboxes `Appearance`, `Costume`, `Setting`, disabled with `Keep
  original` and the hint `Pick a country to change how the film looks.`; line `Script language: {language}` with `from Settings` or `follows the target
  country`, link `Change in Settings` → `/settings`; the `Images with` line of the `New clone` panel; button
  `Localize` — reading `Write script` when no flag is ticked.
- At `reviewing`: one card per changed asset — original frame and text on the left; on the right
  `Localized name`, `Localized description` with `Save`, the model's note, the reference image or its status
  (`Queued`, `Generating…`, `Failed: {error}`), `Regenerate`, `Keep original`. Unchanged candidates are
  listed collapsed with `Change this`, which opens the right side empty. Buttons `Write script` (enabled
  when every changed asset's reference is `done`) and `Back to localization` (confirm `Discard the
  localization and start again?`).
- Later steps: the choices, read-only, and the changed assets with their references.

**Tab "Script"**

- No scenes while the clone is `waiting` → the step label (`Waiting for localization choices` /
  `Waiting for your review`, § Labels) and a button `Open Localization` that opens the `Localization` tab.
- `script_title`, `logline`, `Copy script` — copies Markdown: `# {title}`, the logline, then per scene
  `## Scene {k} — {mm:ss}`, the description and the dialogue — and reads `Copied` for 2 s.
- One card per scene, in order: `Scene {k}` · timestamp · shot size · camera angle · asset chips; images
  `Original` (the frame) and `New` (the image or its status, `Generate` / `Regenerate`); `Description`,
  `Dialogue`, `Image prompt` text areas with `Save`, enabled with unsaved changes. Controls are disabled
  unless 5.4 § Editing scenes allows them.
- `Back to localization` when 5.1 allows it, with the same confirm.

**Dialog "Send to Film Studio"**, opened by the header button; it shows errors and closes as the
`Send to Film Studio` dialog of 3.6:

| Element | Detail |
|---|---|
| `Project` | `New project` (default), then every active Film Studio project by name |
| `Project name` | `New project` only; prefilled with `script_title` cut to 100 characters |
| `Style`, `Default clip length`, `Narration` with `Narrator voice` | `New project` only; as the `New project` panel of 4.5 |
| `Frame`, `Language` | `New project` only; fixed to the clone's `aspect` and `script_language`, read-only |
| Media line | as the `New project` panel of 4.5 |
| Buttons | `Send to Film Studio`, with a captcha (when the captcha is on), and `Cancel` |

- `script_language` not `vi`, `en` or `ja` → the dialog reads `Film Studio narrates only Vietnamese, English
  or Japanese.` and its `Send to Film Studio` is disabled.
- The dialog's `Send to Film Studio` is enabled with a non-blank `Project name` (`New project`), `Narration`
  off or a narrator voice picked, a captcha token (when the captcha is on) and no request in flight. The
  captcha resets after every attempt.
- A new project takes the dialog's values; its other fields take the defaults of the `New project` panel (4.5).
- The dialog's `Send to Film Studio` creates the project first when `New project` is chosen (4.1), then the
  episode with source `film_clone` (4.2), then starts it, and opens `/films/{project id}/episodes/{number}`. A
  project created before a refused episode stays.

**Panel "Prompts used"**, collapsed: the job's `options.prompts` and the clone's `prompts`, read-only, each
with `Copy`.

- Refreshes every 3 s while the clone is `running` or one of its requests is `queued` / `processing`.
- Unknown id → `Clone not found` with a link to `/film-clone`.

### Labels

| Step | Label |
|---|---|
| `analyzing` | Analyzing the film |
| `extracting_assets` | Extracting assets |
| `analyzing_shots` | Analyzing shots |
| `choosing_localization` | Waiting for localization choices |
| `proposing` | Proposing replacements |
| `reviewing` | Waiting for your review |
| `writing_script` | Writing script |
| `generating_scene_images` | Generating scene images |

---

## API endpoints

Same JSON and error conventions as domain 1. Only the two creation routes need `X-Captcha-Token` (skipped
when `CAPTCHA_ENABLED=false`). Generation routes answer `202` with the `GenerationRequest` they queued.

```
POST   /film-clones                                — multipart `file` + `language` + `presetId?` + `maxFrames?` + automatic run fields → 201 FilmClone
POST   /film-clones/youtube                        — JSON { "url", "language", "presetId"?, "maxFrames"?, automatic run fields } → 201 FilmClone
GET    /film-clones?limit=1..200                   — FilmClone[] newest first (default 50)
GET    /film-clones/{id}                           — FilmCloneDetail
DELETE /film-clones/{id}                           — 204
POST   /film-clones/{id}/localization              — { "targetCountry"?, "targetSetting"?, "changeAppearance", "changeCostume", "changeSetting" } → FilmClone
POST   /film-clones/{id}/write-script | resume | relocalize — FilmClone
PATCH  /film-clones/assets/{id}                    — original fields (5.2) or `changed` + localized fields (5.3) → CloneAsset
DELETE /film-clones/assets/{id}                    — 204
POST   /film-clones/assets/{id}/generate-reference — 202
PATCH  /film-clones/scenes/{id}                    — { "description", "dialogue", "imagePrompt" } → CloneScene
POST   /film-clones/scenes/{id}/generate-image     — 202
GET    /film-clones/files/{path}                   — one file under storage/film-clones/
```

- Automatic run fields, all optional: `shouldRunAutomatically` (default `false`), then — read only when it is
  `true` — `targetCountry`, `targetSetting`, `changeAppearance`, `changeCostume` and `changeSetting` (default
  `false`), as in `POST …/localization`.
- Creation runs every check of 1.2 (upload) or 1.3 (YouTube) in its order, then `maxFrames` is an integer
  10–1000 → 400 `Max frames must be between 10 and 1000`, then with `shouldRunAutomatically` rules 2–3 of 5.3
  (400), and `presetId` as 2.5. The AI provider check covers the `moments` and `filmClone` models, and in
  `whole_video` the `audio` model, which must be Google AI (8.1). The job and the clone are created together.
- Frames are served by `GET /jobs/{job id}/files/{path}` once the `video_notes` row exists, as for Film
  Analysis (3).
- `FilmClone`: the fields of 5.1 in camelCase, plus `sourceFilename`, `sourceKind` (`upload` \| `youtube`),
  `jobStep` and `hasOpenRequests` (one of its `GenerationRequest`s is `queued` or `processing`).
  `FilmCloneDetail` = `FilmClone` + `job` (`Job` of 1.1) + `videoNotes` + `assets` + `shots`
  + `scenes` + `generationRequests` (its `GenerationRequest`s that are `queued` or `processing`)
  + `aiActivity` (`{ "provider", "model", "label", "startedAt", "lastOutputAt" }` while an AI call runs, else `null`;
  8.2).

| Route | Errors |
|---|---|
| `POST /film-clones` | as `POST /jobs/video-to-markdown` + 400 max frames / country / flag without country · 409 needs Google AI · 422 |
| `POST /film-clones/youtube` | as `POST /jobs/youtube-to-markdown` + 400 max frames / country / flag without country · 409 needs Google AI · 422 |
| `DELETE /film-clones/{id}` | 404 · 409 still running |
| `POST …/localization` | 400 country / flag without country · 404 · 409 step · 422 |
| `POST …/write-script`, `resume`, `relocalize` | 404 · 409 step / references missing / generation running |
| `PATCH`, `DELETE /film-clones/assets/{id}` | 400 fields · 404 · 409 name / step / not changed / generation running |
| `POST …/generate-reference` | 404 · 409 step / not changed / generation running |
| `PATCH /film-clones/scenes/{id}`, `POST …/generate-image` | 400 fields · 404 · 409 status / generation running |
| `GET /film-clones/files/{path}` | 404 missing file / path outside `storage/film-clones/` |

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `CLONE_AI_SILENCE_SEC` | `900` | 5.1 — no output for this long stops an AI call, every provider |
| `CLONE_AI_MAX_RUN_SEC` | `3600` | 5.1 — the longest an AI call may run, every provider |
| `CLONE_SCRIPT_SHOTS_PER_CALL` | `100` | 5.4 — the shots one `writing_script` call writes scenes for |

Shared: as domain 3 (`FILM_SCENE_THRESHOLD`, `FILM_SCENE_TIMEOUT_SEC`, …), the AI model keys of domain 8, and Film Studio's
`FILM_WORKER_POLL_INTERVAL_SEC`, `FILM_REQUEST_MAX_ATTEMPTS`. Fixed: 60 assets, 1000 frames. Provider keys,
models and pacing: Provider Settings (domain 7).

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- Clips, narration, music and the assembled film — Film Studio does them after `Send to Film Studio`.
- Changing the tone or register of the dialogue; a target country outside the list.
- Adding assets or shots by hand; editing shots.
- A version history of replacements, references or scene images — a new one replaces the old.
- Cutting a character out of a frame for its reference.
- Starting a clone from an existing Film Analysis job; rerunning a clone with another preset.
- A film with no speech or no usable captions — it fails as in domain 1.
