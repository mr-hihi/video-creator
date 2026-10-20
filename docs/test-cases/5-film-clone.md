## 5. Clone phim (Film Clone) (5-film-clone.md)

Test cases for [business/5-film-clone.md](../business/5-film-clone.md). Acronym `FC`.

## Test environment

- Stack, captcha switch, app labels and reference data (V1, F1): as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- Shorthand: `C` = `http://localhost:5070/film-clones`.
- `claude` CLI logged in for every Frontend case. Claude's answers vary between runs; cases check structure,
  not wording.
- **Fake provider** and *(real provider)*: as in
  [4-film-studio.md § Test environment](./4-film-studio.md#test-environment).
- `Script language` setting (domain 6) at its default `Follow target country` unless a case says otherwise.
- `Frame image + audio` cases run against the mock AI of `tools/mock-ai`, which must answer the Gemini Files API
  and the `speakersAndSounds` schema, with the fake key `AIza-test-0000000000wxyz` saved on the `google`
  provider and `aiStepModels.audio` = `{"provider":"google","model":"gemini-3.8-flash"}`.
- Reference data, created before the cases that name it:

| Id | How it is made |
|---|---|
| K1 | TC-FC-01 run to `waiting` · `choosing_localization` (upload of F1, `Max frames` 20) |
| K2 | a clone `done` with target `jp`, `change_appearance` + `change_costume`, images made with Google Flow — `filmCloneImageProvider` at its default `null`, the `image` route at its default `google_flow` — at least 3 scenes (TC-FC-11 run to the end) |

---

## Creation & stages 1–2

### TC-FC-01: Upload a film, up to the localization choices
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone
  2. Keep source `Upload file`; drop F1 on the `Film` field
  3. Select `Vietnamese` from `Spoken language`; keep the preselected `Prompt preset`
  4. Fill `Max frames` with `20`
  5. *(captcha on)* Wait for the captcha; click `Clone`
  6. Wait until the stage bar shows `Localization` as `waiting`
  7. Open the tabs `Video notes`, `Assets`, `Shots`; expand `Prompts used`
- **Expected:**
  - URL becomes `/film-clone/{id}`; while analyzing, the job steps show `Extracting audio`, `Transcribing speech`, `Picking key moments`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown` in that order
  - After the job, `Assets & shots` is `current` with `Extracting assets`, then `Analyzing shots`; a line below reads `Claude (CLI default) is working · {mm:ss} · …`
  - Stage bar: `Video notes` and `Assets & shots` `completed`, `Localization` `waiting`, `Script & images` `upcoming`
  - `Video notes` shows frames under `##` headings, with `Copy`
  - `Assets` shows the groups `Characters`, `Costumes`, `Props`, `Locations` with ≥ 1 card; each card has a name, a culture, a period and `{n} frames`
  - `Shots` has one row per frame — as many as `Frames` in the summary, at most 20 — in time order; each row shows a badge `Dialogue` or `Scene change` and a shot size and camera angle label or `—`
  - `Prompts used` lists six prompts: Video → Markdown, Speakers & sounds, Clone assets, Clone shots, Clone localization, Clone script
  - `GET C/{id}` → `status` = `waiting`, `step` = `choosing_localization`, `aspect` = `16:9`, `sourceKind` = `upload`; `job.type` = `film_clone`, `job.options.maxFrames` = 20, `job.options.prompts` has `videoToMarkdown`, `speakersAndSounds`, `cloneAssets`, `cloneShots`; `prompts` has `cloneLocalization`, `cloneScript`
  - `api/storage-test/{job id}/output/` holds `images/` only

### TC-FC-02: YouTube link, up to the localization choices
- **App:** Frontend
- **Precondition:** Network up.
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone; click `YouTube link`
  2. Fill `YouTube link` with V1; keep `Max frames` at `1000`
  3. *(captcha on)* Wait for the captcha; click `Clone`
  4. Wait until `Localization` is `waiting`; open `Shots`; click the timestamp of the second row
- **Expected:**
  - The button reads `Checking video…` while the request runs
  - Job steps: `Fetching YouTube transcript`, `Picking key moments`, `Downloading video`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown`; then the clone steps `Extracting assets`, `Analyzing shots`
  - Summary has `Source` = `https://www.youtube.com/watch?v=vfjegxHDOwI` and `Captions` = `Auto-generated`
  - `GET C/{id}` → `job.type` = `youtube_film_clone`, `sourceKind` = `youtube`
  - Step 4: a new tab opens `https://www.youtube.com/watch?v=vfjegxHDOwI&t={seconds}s`

### TC-FC-03: Creation validation
- **App:** API
- **Steps:**
  1. `curl -i -X POST C/youtube -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","maxFrames":9}'`
  2. Same with `"maxFrames":1001`
  3. Same with `"maxFrames":40,"presetId":"00000000-0000-0000-0000-000000000000"`
  4. Same with `"url":"https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG"`
  5. From `video-tool/`: `curl -i -X POST C -F 'file=@notes.txt' -F 'language=auto'`
  6. *(captcha on)* Step 1 with `"maxFrames":40` and header `X-Captcha-Token:` (empty)
- **Expected:**
  1. `HTTP 400`, `detail` = `Max frames must be between 10 and 1000`
  2. `HTTP 400`, same `detail`
  3. `HTTP 400`, `detail` = `Prompt preset 00000000-0000-0000-0000-000000000000 not found`
  4. `HTTP 400`, `detail` = `Playlist links are not supported. Open one video and copy its link`
  5. `HTTP 400`, `detail` = `Unsupported file type '.txt'. Use one of: .avi, .m4v, .mkv, .mov, .mp4, .webm`
  6. `HTTP 403`, `detail` = `Captcha verification failed`
  - `GET C` gains no row; no new folder under `api/storage-test/`

### TC-FC-04: Form states
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone
  2. Drop F1 on the `Film` field; *(captcha on)* wait for the captcha
  3. Fill `Max frames` with `1001`, then `1000`
  4. Click `Edit presets`
- **Expected:**
  - Step 1: `Max frames` = 1000 with the hint `One scene per frame in the script.`; the default preset is preselected as `{name} (default)`
  - Step 3: `Clone` is disabled at `1001`, enabled at `1000`
  - Step 4: URL becomes `/settings?tab=prompt-override&id={default preset id}`

### TC-FC-05: Assets are normalised
- **App:** API unit
- **Precondition:** Job with frames `images/moment-01-00m00s.jpg` … `moment-04-00m30s.jpg`; faked `claude` answers
  `extracting_assets` with 63 assets: `{"kind":"vehicle","name":"Cart"}`, `{"kind":"prop","name":"  "}`,
  `{"kind":"character","name":"Min-ji"}`, `{"kind":"character","name":"MIN-JI"}`,
  `{"kind":"costume","name":"Hanbok","culture":"","period":" ","frames":["images/moment-09-09m09s.jpg","images/moment-02-00m10s.jpg"]}`,
  then 58 distinct valid props.
- **Steps:**
  1. Run `extracting_assets`
- **Expected:**
  - `Cart`, the blank name and `MIN-JI` are dropped; `Min-ji` is kept
  - `Hanbok`: `culture` = `Unknown`, `period` = `Unknown`, `frames` = `["images/moment-02-00m10s.jpg"]`, `reference_frame` = `images/moment-02-00m10s.jpg`
  - 60 assets kept, in reply order; the message held `Video notes:` and the four frames as images

### TC-FC-06: One shot per frame
- **App:** API unit
- **Precondition:** The four frames of TC-FC-05; assets `Min-ji` (character) and `Hanbok` (costume); faked
  `claude` answers `analyzing_shots` with: frame 1 `close_up` / `low` / `tense` / `She grips the fan` /
  `["min-ji (character)","Ghost"]`; frame 1 again `wide`; frame 2 `macro` / `eye_level`; frame 4 `medium` / `dutch`.
- **Steps:**
  1. Run `analyzing_shots`
- **Expected:**
  - Four shots, positions 0–3 in time order
  - Shot 0: `shot_size` = `close_up`, `camera_angle` = `low`, `emotion` = `tense`, `action` = `She grips the fan`, `asset_ids` = [Min-ji] — `Ghost` dropped, the second frame-1 entry ignored
  - Shot 1: `shot_size` = `null`, `camera_angle` = `eye_level`
  - Shot 2 (frame 3, skipped by the reply): every value `null`, `asset_ids` = `[]`
  - The message held `Give exactly one entry per frame.` and `Min-ji (character)`

### TC-FC-07: A failing job fails the clone for good
- **App:** API unit + API
- **Steps:**
  1. *(API unit)* Run a clone job whose faked `claude` answers `picking_moments` with `{"is_error": true, "result": "Overloaded"}`
  2. `curl -i -X POST C/{id}/resume`
- **Expected:**
  1. Job `failed` at `picking_moments`; clone `status` = `failed`, `step` = `analyzing`, `errorMessage` = the job's; `extracting_assets` never runs
  2. `HTTP 409`, `detail` = `Cannot resume clone {id} while it is failed at analyzing`

### TC-FC-08: Edit and delete assets before localization
- **App:** API
- **Precondition:** K1 with assets A1 (character, in shot S1) and A2.
- **Steps:**
  1. `curl -i -X PATCH C/assets/{A2} -H 'Content-Type: application/json' -d '{"name":"{A1 name in upper case}"}'`
  2. `PATCH C/assets/{A2}` `{"culture":"   "}`
  3. `PATCH C/assets/{A2}` `{"name":"Old Palace","culture":"Korean","period":"Joseon dynasty"}`
  4. `DELETE C/assets/{A1}`; `GET C/{K1}`
- **Expected:**
  1. `HTTP 409`, `detail` = `An asset named '{A1 name in upper case}' already exists in this clone`
  2. `HTTP 400`, `detail` = `Culture and period must be 1-100 characters`
  3. `HTTP 200` with the three values
  4. `HTTP 204`; A1 is gone and S1's `assetIds` no longer holds it

### TC-FC-39: The stage 1 job copies the Film Clone input mode
- **App:** Frontend + API
- **Precondition:** Network up; mock AI, `google` key and `aiStepModels.audio` as in § Test environment.
- **Steps:**
  1. `curl -s -X PATCH http://localhost:5070/settings -H 'Content-Type: application/json' -d '{"inputMode":"subtitles","filmCloneInputMode":"whole_video"}'`
  2. `curl -i -X POST C/youtube -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","maxFrames":20}'`
  3. `curl -s -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto"}'`
  4. `PATCH http://localhost:5070/settings` `{"filmCloneInputMode":"subtitles"}`; `curl -s C/{clone id of step 2}`
  5. Navigate to `/film-clone/{clone id of step 2}`
- **Expected:**
  - Step 2: `HTTP 201`; `GET C/{id}` → `job.options.inputMode` = `whole_video`
  - Step 3: `options.inputMode` = `subtitles`
  - Step 4: `job.options.inputMode` is still `whole_video`
  - Step 5: summary `Input` = `Frame image + audio`; while analyzing, the job steps show `Fetching YouTube transcript`, `Downloading video`, `Listening to the audio`, `Sampling frames`, `Picking key moments`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown` in that order

### TC-FC-47: Frame image + audio — speakers and sound shots
- **App:** Frontend + API
- **Precondition:** Mock AI, `google` key and `aiStepModels.audio` as in § Test environment; the mock answers
  `listening_to_audio` with two speakers and three sounds spread over F1; `PATCH /settings`
  `{"filmCloneInputMode":"whole_video"}`.
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone; drop F1 on `Film`; fill `Max frames` with `20`
  2. *(captcha on)* Wait for the captcha; click `Clone`
  3. Wait until `Localization` is `waiting`; open the tabs `Video notes` and `Shots`
  4. `curl -s C/{id}`
- **Expected:**
  - Step 1: `Max frames` shown; the line reads `AI: Key moments — Claude (CLI default) · Audio — Gemini 3.8 Flash · Film clone — Claude (CLI default) · Input: Frame image + audio`
  - Step 3: job steps `Extracting audio`, `Transcribing speech`, `Listening to the audio`, `Sampling frames`, `Picking key moments`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown`; summary `Frames` = `{d} dialogue + {s} sounds + {c} scene changes`, d + s + c ≤ 20, s ≥ 1
  - `Video notes` starts with `Speakers:` listing the two speakers and has `**{name}:**` lines; each sound frame heads `## {mm:ss} — {Kind}: {description}`
  - `Shots` shows a `Sound` badge on as many rows as `{s}`, next to `Dialogue` and `Scene change` rows
  - Step 4: `shots[].frameKind` takes `dialogue`, `sound` and `scene`; `job.aiUsed` has `listening_to_audio` = Gemini 3.8 Flash and `picking_moments` = Claude (CLI default)

## Localization

### TC-FC-09: Localization validation
- **App:** API
- **Precondition:** K1.
- **Steps:**
  1. `curl -i -X POST C/{K1}/localization -H 'Content-Type: application/json' -d '{"targetCountry":"xx","changeAppearance":false,"changeCostume":false,"changeSetting":false}'`
  2. Same with `"targetCountry":null,"changeSetting":true`
  3. Same with `"targetCountry":"jp","changeAppearance":"maybe"`
  4. Same with `"targetCountry":"jp","changeSetting":true`, twice
  5. `PATCH C/assets/{an asset of K1}` `{"name":"Late edit"}` after step 4
- **Expected:**
  1. `HTTP 400`, `detail` = `Unknown country 'xx'`
  2. `HTTP 400`, `detail` = `Pick a target country to change appearance, costume or setting`
  3. `HTTP 422`
  4. First `HTTP 200`, `status` = `running`, `step` = `proposing`; second `HTTP 409`, `detail` = `Cannot localize clone {K1} while it is {status} at {step}`
  5. `HTTP 409`, `detail` = `Assets can be edited only before localization`

### TC-FC-10: Keep the original — straight to the script
- **App:** API unit
- **Precondition:** Clone at `waiting` · `choosing_localization` whose transcript language is `vi`.
- **Steps:**
  1. `localize` with `targetCountry` = `null`, no flag
- **Expected:**
  - `status` = `running`, `step` = `writing_script` — `proposing` never runs, no `clone_reference_image` request
  - `scriptLanguage` = `vi`; every asset `changed` = `false`

### TC-FC-11: Localize to Japan, end to end
- **App:** Frontend *(real provider)*
- **Precondition:** A fresh clone like K1 at `choosing_localization`.
- **Steps:**
  1. Open `Localization`
  2. Select `Japan` from `Target country`; tick `Appearance` and `Costume`
  3. Click `Localize`; wait until the stage bar shows `Localization` as `waiting` again
  4. Wait until every reference image shows; click `Write script`
  5. Wait until the status badge shows `done`; open `Script`
- **Expected:**
  - Step 1: `Keep original` is selected and the three checkboxes are disabled with the hint `Pick a country to change how the film looks.`; the line reads `Script language: … follows the target country`; the line `Images with: Google Flow` with a link `Change` → `/settings?tab=film-clone` and no `Images with` select
  - Step 2: the button reads `Localize`; the line reads `Script language: Japanese`
  - Step 3: step label `Proposing replacements`, then `Waiting for your review`; one card per changed asset, every one a `character` or `costume`, each with `Localized name`, `Localized description`, a note and a reference status; `Write script` is disabled while a reference is not ready
  - Step 5: stage bar all `completed`; `Script` shows a title, a logline and one card per shot, each with an `Original` frame and a `New` image
  - `GET C/{id}` → `targetCountry` = `jp`, `scriptLanguage` = `ja`, every scene `imageStatus` = `done`; dialogue in Japanese

### TC-FC-12: Proposals — candidates, message and normalising
- **App:** API unit
- **Precondition:** Clone at `choosing_localization` with assets `Min-ji` (character), `Hanbok` (costume),
  `Fan` (prop), `Palace` (location, `reference_frame` set); faked `claude` answers `proposing` with
  `Palace (location)` changed (`localizedName` blank, `localizedDescription` = `A Kyoto temple courtyard`), `Fan` changed
  with a blank `localizedDescription`, and `Ghost` changed.
- **Steps:**
  1. `localize` with `targetCountry` = `jp`, only `changeSetting`
- **Expected:**
  - The message holds `Target country: Japan`, `Change only: architecture, landscape, signs, objects`, the lines of `Fan` and `Palace` only, and `Palace`'s reference frame as an image
  - `Palace`: `changed` = `true`, `localizedName` = `Palace`; `Fan`, `Min-ji`, `Hanbok` unchanged; `Ghost` ignored
  - `status` = `waiting`, `step` = `reviewing`; one `clone_reference_image` request for `Palace`: prompt starts with `Reference image of A Kyoto temple courtyard.`, `params.aspect` = 16:9, `cloneId` set, `projectId` = `null`, `provider` = `google_flow` — `filmCloneImageProvider` at its default `null` follows the `image` route

### TC-FC-13: Script language from the setting
- **App:** API unit
- **Steps:**
  1. Setting `Follow target country`; `localize` with `targetCountry` = `kr`
  2. Setting fixed to `en`; `localize` with `targetCountry` = `jp`
  3. Setting fixed to `en`; `localize` with `targetCountry` = `null`
  4. Setting `Follow target country`; `localize` with `targetCountry` = `null` on a clone whose transcript language is `ja`
- **Expected:**
  1. `scriptLanguage` = `ko`
  2. `scriptLanguage` = `en`
  3. `scriptLanguage` = `en`
  4. `scriptLanguage` = `ja`

### TC-FC-14: Reviewing actions and Write script rules
- **App:** API
- **Precondition:** Clone R at `reviewing` with `Palace` changed and its reference `done`, `Fan` unchanged.
- **Steps:**
  1. `curl -i -X PATCH C/assets/{Fan} -H 'Content-Type: application/json' -d '{"changed":true}'`
  2. `PATCH C/assets/{Fan}` `{"changed":true,"localizedDescription":"A paper uchiwa fan"}`
  3. `POST C/{R}/write-script`
  4. `POST C/assets/{Fan}/generate-reference`; at once `PATCH C/assets/{Fan}` `{"localizedName":"Uchiwa"}`
  5. `PATCH C/assets/{Palace}` `{"changed":false}`
  6. `POST C/assets/{Palace}/generate-reference`
- **Expected:**
  1. `HTTP 400`, `detail` = `Describe the localized asset first`
  2. `HTTP 200`, `changed` = `true`, `referenceStatus` = `none`
  3. `HTTP 409`, `detail` = `Reference images missing for: Fan`
  4. `HTTP 202`; then `HTTP 409`, `detail` = `Asset 'Fan' has generation running`
  5. `HTTP 200`, localized fields `null`, `referenceStatus` = `none`; the reference file is gone
  6. `HTTP 409`, `detail` = `Asset 'Palace' is not changed`

### TC-FC-15: A failed reference stays on its card
- **App:** API unit
- **Precondition:** Clone at `reviewing` with one changed asset; Fake provider fails its reference with `Blocked by the content filter`.
- **Steps:**
  1. Run the worker until idle
  2. Let the provider answer; generate the reference again; run the worker until idle; `write-script`
- **Expected:**
  1. `referenceStatus` = `failed`, `referenceError` = `Blocked by the content filter`; clone stays `waiting` · `reviewing`
  2. `referenceStatus` = `done`; `write-script` → `running` · `writing_script`

## Script & images

### TC-FC-16: Script message and normalising
- **App:** API unit
- **Precondition:** Clone with 3 shots (S0 `close_up` / `low`, S1 no values, S2 `wide` / `high`), `Palace` changed
  to `Kyoto Temple`, `scriptLanguage` = `ja`, `targetCountry` = `jp`; faked `claude` answers with a blank
  `title`, scenes for S2, S0, S1, a second S0, and one for an unknown `shotId`.
- **Steps:**
  1. Run `writing_script`
- **Expected:**
  - The message holds `Script language: Japanese. Keep the tone and register of the original dialogue.`, `Setting: Japan`, `Write exactly one scene per shot, in the order given, each with its shotId.`, `Kyoto Temple (location) — … (replaces Palace)`, a shot line `{S1 id} · {mm:ss} · — · — · emotion: …`, and `Video notes:`; no image is attached
  - Three scenes in shot order S0, S1, S2; the second S0 and the unknown one are dropped
  - `scriptTitle` = the `{stem}` of `source_filename`; `status` = `running`, `step` = `generating_scene_images`

### TC-FC-17: A shot without a scene, then Resume
- **App:** API unit
- **Precondition:** Clone with 5 shots; faked `claude` answers the first call with 3 valid scenes, the second with 5.
- **Steps:**
  1. Run `writing_script`
  2. `resume`; run it again
- **Expected:**
  1. `status` = `failed`, `step` = `writing_script`, `errorMessage` = `claude returned no scene for 2 of 5 shots`; no scene saved
  2. Five scenes; `step` = `generating_scene_images`

### TC-FC-18: Scene images — prompt, inputs, failure and recovery
- **App:** API unit
- **Precondition:** `filmCloneImageProvider` setting `sd_webui`, `filmStudioImageProvider` setting `fal`. Clone at `generating_scene_images`, `aspect` = `9:16`; scene 1 =
  shot `close_up` / `low` with changed asset `Kyoto Temple` (reference `done`); scene 2 = shot without values
  with unchanged asset `Min-ji` (`reference_frame` set); scene 3 with an unchanged asset that has no frame.
  Fake provider fails scene 3 with `Blocked by the content filter`.
- **Steps:**
  1. Run the worker until idle
  2. Let the provider answer; `POST C/scenes/{scene 3}/generate-image`; run the worker until idle
- **Expected:**
  1. Scene 1 prompt ends with `Shot: Close-up, Low angle.`; scene 2 has no `Shot:` part; each request has exactly one input — its shot's original frame — and no asset reference (not `Kyoto Temple`'s generated reference, not Min-ji's frame); every request `provider` = `sd_webui`, `params.aspect` = 9:16; each is sent as `img2img` with its frame as init image. Clone `failed` at `generating_scene_images`, `errorMessage` = `1 scene image(s) failed — fix them and resume`
  2. Scene 3 `done`; clone `status` = `done`, `finishedAt` set

### TC-FC-19: Edit scenes
- **App:** API
- **Precondition:** K2 with scene X.
- **Steps:**
  1. `curl -i -X PATCH C/scenes/{X} -H 'Content-Type: application/json' -d '{"description":"  "}'`
  2. `PATCH C/scenes/{X}` with a `dialogue` of 2001 characters
  3. `PATCH C/scenes/{X}` `{"description":"She opens the shoji door.","dialogue":"Mai: Okaeri."}`
  4. `POST C/scenes/{X}/generate-image`; at once `PATCH C/scenes/{X}` `{"imagePrompt":"Wide shot"}`
  5. `PATCH C/{K2}` `{"filmCloneImageProvider":"sd_webui"}`
  6. *(API unit)* `PATCH` a scene of a clone `running` at `generating_scene_images`
- **Expected:**
  1. `HTTP 400`, `detail` = `Description must be 1-2000 characters`
  2. `HTTP 400`, `detail` = `Dialogue must be at most 2000 characters`
  3. `HTTP 200`; `imageStatus` stays `done` and the image file is unchanged
  4. `HTTP 202`; then `HTTP 409`, `detail` = `Scene {n} has generation running`
  5. `HTTP 405`
  6. 409 `Scenes can be edited once the script is written`

### TC-FC-20: Back to localization
- **App:** Frontend
- **Precondition:** K2.
- **Steps:**
  1. Navigate to `/film-clone/{K2}`; open `Script`; click `Back to localization`
  2. Click `Cancel`; click it again; click `OK`
  3. Open `Localization`
- **Expected:**
  - Dialog `Discard the localization and start again?`; after `Cancel` nothing changes
  - After `OK`: stage bar `Localization` `waiting`, `Script & images` `upcoming`; `Script` reads `Waiting for localization choices` with a button `Open Localization`
  - Step 3: `Target country` = `Japan`, `Appearance` and `Costume` ticked; the line `Images with: Google Flow` with a link `Change` → `/settings?tab=film-clone`
  - `GET C/{K2}` → `scenes` = `[]`, `scriptTitle` = `null`, every asset `changed` = `false`; `api/storage-test/film-clones/{K2}/` holds no reference or scene file

### TC-FC-21: Relocalize refused while generating
- **App:** API unit
- **Steps:**
  1. `relocalize` a `done` clone with a `clone_scene_image` request `queued`
- **Expected:**
  1. 409 `Film clone {id} has image generation running`; scenes kept

### TC-FC-22: Copy script
- **App:** Frontend
- **Precondition:** K2.
- **Steps:**
  1. Navigate to `/film-clone/{K2}`; open `Script`; click `Copy script`
- **Expected:**
  - The button reads `Copied` for 2 s
  - The clipboard starts with `# {scriptTitle}`, then the logline, then one `## Scene {k} — {mm:ss}` per scene followed by its description and dialogue

### TC-FC-46: Script tab while the clone waits for the user
- **App:** Frontend
- **Precondition:** K1; a clone R at `waiting` · `reviewing` (TC-FC-11 run to step 3).
- **Steps:**
  1. Navigate to `/film-clone/{K1}`; open `Script`
  2. Click `Open Localization`
  3. Navigate to `/film-clone/{R}`; open `Script`
  4. Click `Open Localization`
- **Expected:**
  1. `Script` reads `Waiting for localization choices` with a button `Open Localization`; no `Waiting…`
  2. The `Localization` tab is selected and shows `Target country` and the `Localize` button
  3. `Script` reads `Waiting for your review` with `Open Localization` and `Back to localization`
  4. The `Localization` tab is selected and shows one card per changed asset and `Write script`

## History, delete & lifecycle

### TC-FC-23: Clone history
- **App:** Frontend
- **Precondition:** TC-FC-01 (K1), TC-FC-02 and K2 exist; TC-FA-01 has run.
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone
- **Expected:**
  - `Clone history` has the three clones and no film analysis row
  - K1: badge `Upload`, `Original`, `Waiting for localization choices · {created time}`, status badge, `View`, `Delete`; K2: `Japan`; TC-FC-02: badge `YouTube`
  - A `running` row has no `Delete`; the list refreshes every 3 s while one exists

### TC-FC-24: Delete a clone
- **App:** Frontend + API
- **Precondition:** TC-FC-02's clone (D) at `choosing_localization`; its job id J.
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone; click `Delete` on the D row
  2. Click `Cancel`; click `Delete` again; click `OK`
  3. `curl -s -o /dev/null -w '%{http_code}' C/{D}`; same for `http://localhost:5070/jobs/{J}`
- **Expected:**
  - Dialog `Delete this clone? The video, frames, assets, script and images are removed.`
  - After `Cancel` the row stays; after `OK` it disappears
  - Step 3: `404` and `404`; `api/storage-test/{J}/` and `api/storage-test/film-clones/{D}/` no longer exist

### TC-FC-25: Delete rules
- **App:** API + API unit
- **Steps:**
  1. `DELETE` a clone while it is `running` at `analyzing`
  2. *(API unit)* `DELETE` a `done` clone with a `clone_scene_image` request `processing`
  3. `curl -i -X DELETE C/00000000-0000-0000-0000-000000000000`
- **Expected:**
  1. `HTTP 409`, `detail` = `Film clone {id} is still running`; the job continues
  2. 409, same `detail`
  3. `HTTP 404`, `detail` = `Film clone 00000000-0000-0000-0000-000000000000 not found`

### TC-FC-26: API restarted during `writing_script`
- **App:** Frontend
- **Steps:**
  1. Run a clone to `writing_script` (keep original, no flag)
  2. While the step shows `Writing script`, ask the user to stop the test stack (Ctrl+C) and start `sh run.sh start_test` again
  3. Open `/film-clone/{id}` again and wait until `done`
- **Expected:**
  - Right after the restart `GET C/{id}` shows `status` = `running`, `step` = `writing_script`
  - It ends `done` with exactly one scene per shot

### TC-FC-27: Unknown clone page
- **App:** Frontend
- **Steps:**
  1. Navigate to `/film-clone/00000000-0000-0000-0000-000000000000`
- **Expected:**
  - `Clone not found` with a link to `/film-clone`

## Send to Film Studio

### TC-FC-28: The `Send to Film Studio` button and dialog
- **App:** Frontend
- **Precondition:** K1; K2 (`scriptLanguage` = `ja`, `aspect` = `16:9`); a `done` clone L with `scriptLanguage` = `ko`;
  Film Studio project P1 active and P5 archived; `filmStudioImageProvider` and `filmStudioClipProvider` at their
  default `null`, the `image` and `video` routes at their default `google_flow`.
- **Steps:**
  1. Navigate to `/film-clone/{K1}`
  2. Navigate to `/film-clone/{K2}`; click `Send to Film Studio` in the header
  3. Untick `Narration`
  4. Select `Test Series` from `Project`
  5. Click `Cancel`, then click `Send to Film Studio` in the header
  6. Navigate to `/film-clone/{L}`; click `Send to Film Studio` in the header
- **Expected:**
  1. The header shows the status badge, `Send to Film Studio` (disabled) and `Delete`, in that order
  2. The header shows the status badge, `Send to Film Studio` (enabled) and `Delete`, in that order; the page has no `Send to Film Studio` panel. Dialog `Send to Film Studio` opens: `Project` = `New project`, list has `Test Series` and no `Old Series`; `Project name` = K2's `scriptTitle`; `Frame` = `Landscape 16:9` and `Language` = `Japanese`, both read-only; `Style` = `Photorealistic`; `Default clip length` = `8 s`; `Narration` ticked, `Narrator voice` = `—` with a link `Add a voice` → `/films/library?tab=voices`; the line `Images with: Google Flow · Clips with: Google Flow` with a link `Change` → `/settings?tab=film-studio`; buttons `Send to Film Studio` (disabled) and `Cancel`
  3. `Narrator voice` is disabled; *(captcha off)* the dialog's `Send to Film Studio` is enabled
  4. `Project name`, `Frame`, `Style`, `Default clip length`, `Language`, `Narration` and `Narrator voice` are hidden; the media line stays
  5. The dialog closes; reopened, it shows `Project` = `New project` and `Narration` ticked
  6. The dialog reads `Film Studio narrates only Vietnamese, English or Japanese.`; its `Send to Film Studio` is disabled

### TC-FC-29: Send to a new project
- **App:** Frontend *(real provider)*
- **Precondition:** K2; VT1 of [4-film-studio.md § Test environment](./4-film-studio.md#test-environment).
- **Steps:**
  1. Navigate to `/film-clone/{K2}`
  2. Click `Send to Film Studio` in the header; in the dialog keep `New project`; fill `Project name` with `Clone Test`; select `4 s` from `Default clip length`; select `narrator-en` from `Narrator voice`
  3. *(captcha on)* Wait for the captcha; click `Send to Film Studio` in the dialog
- **Expected:**
  - URL becomes `/films/{new project id}/episodes/1`; the stage list shows `Writing script` and `Generating reference images` `completed` and `Generating scene images` `paused`, with `Paused after Generating scene images — check the work, then Continue.`; the counters read `Images {n}/{n}`, `n` = K2's scenes
  - `Scenes` shows one card per K2 scene, in order, each with K2's image; `Script` shows `Source` linking to `/film-clone/{K2}`
  - `GET /films/episodes/{id}` → `source` = `film_clone`, `sourceCloneId` = K2's id, `targetDurationS` = scenes × 3
  - `GET /films/projects/{new project id}` → `language` = `ja`, `orientation` = `landscape`, `clipDurationS` = 4, `allowNarration` = `true`, `narratorVoiceId` = VT1's id
  - `/films` lists `Clone Test` with badge `16:9`

### TC-FC-45: Send to an existing project in another language
- **App:** Frontend
- **Precondition:** K2 (`scriptLanguage` = `ja`); Film Studio project P1 (`Test Series`, `language` = `en`).
- **Steps:**
  1. `GET /films/projects/{P1}` and note the number of `episodes`
  2. Navigate to `/film-clone/{K2}`
  3. Click `Send to Film Studio` in the header; select `Test Series` from `Project`
  4. *(captcha on)* Wait for the captcha; click `Send to Film Studio` in the dialog
  5. `GET /films/projects/{P1}`
- **Expected:**
  - Step 4: alert `The clone is written in ja; the project narrates in en` in the dialog; the dialog stays open; URL stays `/film-clone/{K2}`; `Project` still shows `Test Series`
  - Step 5: the same number of `episodes` as step 1

## Claude calls

### TC-FC-30: A failed Claude analysis step, then Resume
- **App:** API unit + API
- **Steps:**
  1. *(API unit)* A clone whose job is `done`; faked `claude` answers `extracting_assets` with `{"is_error": true, "result": "Overloaded"}`
  2. `curl -i -X POST C/{id}/relocalize`
  3. `curl -i -X POST C/{id}/resume`; the faked `claude` now answers both steps
- **Expected:**
  1. After the job the clone is `running` at `extracting_assets`, one empty shot per frame saved; then `status` = `failed`, `step` = `extracting_assets`, `errorMessage` = `claude failed: Overloaded`
  2. `HTTP 409`, `detail` = `Cannot relocalize clone {id} while it is failed at extracting_assets`
  3. `HTTP 200`, `status` = `running`; the job is not run again; `extracting_assets`, then `analyzing_shots` run; the clone ends `waiting` at `choosing_localization`

### TC-FC-31: Claude silent past the limit, the activity line, then Resume
- **App:** Frontend
- **Precondition:** `CLONE_AI_SILENCE_SEC=5` in `api/.env.test`; test stack restarted.
- **Steps:**
  1. Clone V1 with `Max frames` 40 (TC-FC-02 steps 1–3)
  2. When the stage bar shows `Extracting assets`, watch the line below it and open the `Shots` tab
  3. Wait until the clone is `failed`, at `extracting_assets` or `analyzing_shots`, whichever goes silent first
  4. Set `CLONE_AI_SILENCE_SEC` back to `900`, restart the stack, click `Resume`
- **Expected:**
  2. The line reads `Claude (CLI default) is working · {mm:ss} · no output yet`, later `last output {n}s ago`; the elapsed time grows on each refresh; `Shots` reads `Waiting…`
  3. Error alert `claude stopped responding for 5s`; `Resume` is shown; `Back to localization` is not
  4. The clone runs the failed step again from the start and reaches `waiting` at `choosing_localization`; the job is not run again; `Shots` lists every shot with its size, angle, emotion and action

### TC-FC-32: Claude output limits and errors
- **App:** API unit
- **Steps:**
  1. A `claude` call that writes a line every 0.1 s for 0.8 s, silence limit 0.5 s
  2. A call silent for 5 s, silence limit 0.3 s
  3. A call that never stops writing, run limit 0.5 s
  4. A call ending with `{"type":"result","is_error":true,"result":"API Error: 500 Internal server error"}` and exit code 1
  5. A call exiting with code 1, no result event, stderr `boom`
  6. The arguments of the `claude` calls of 1.5, 3.3, 4.2 and stages 2–4
- **Expected:**
  1. Finishes; all 8 lines returned
  2. Killed within 3 s: `… stopped responding for 0.3s`
  3. Killed: `… timed out after 0.5s`
  4. `claude failed: API Error: 500 Internal server error`
  5. `claude exited with 1: boom`
  6. Each has `--setting-sources ""`; a probe call answers that it has no instruction about the reply
     language, how to address the user or a terse style, and runs no hook

### TC-FC-33: Claude places no shot on a captured frame
- **App:** API unit + Frontend
- **Precondition:** A clone at `analyzing_shots`; a faked `claude` answers that step.
- **Steps:**
  1. The reply is `{"shots": []}`
  2. The reply names only `Frame 9` and `moment-99.jpg`
  3. The reply names six unknown frames
  4. The reply names one captured frame and one unknown frame
  5. *(Frontend)* Open the failed clone, then click `Resume` with the real `claude`
- **Expected:**
  1. `failed` at `analyzing_shots`, `errorMessage` = `claude returned no shots`; no shot value saved
  2. `errorMessage` = `claude named no captured frame: ['Frame 9', 'moment-99.jpg']`
  3. The message lists the first five names only
  4. Saved: the captured frame gets its values; a warning lists the unknown name; the clone waits at
     `choosing_localization`
  5. Error alert with the message, `Resume` shown; after `Resume` the step runs again and the clone waits at
     `choosing_localization`


## Automatic run

### TC-FC-34: Automatic run, Japan, end to end
- **App:** Frontend *(real provider)*
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone; drop F1 on the `Film` field; `Max frames` 20
  2. Tick `Run every step automatically`
  3. Select `Japan` from `Target country`; tick `Appearance` and `Costume`
  4. Click `Clone`; wait without clicking anything until the status badge shows `done`
- **Expected:**
  - Step 1: the checkbox is unticked with the hint `Skips the localization choices and the review, using the choices below.`; no `Target country` field is shown; the line `Images with: Google Flow` with a link `Change` → `/settings?tab=film-clone` sits under the `AI` line
  - Step 2: `Target country` (`Keep original`) and the three checkboxes (disabled with the hint `Pick a country to change how the film looks.`) appear below it; no `Images with` select
  - Step 4: the step label goes `Analyzing shots` → `Proposing replacements` → `Waiting for your review` while the references generate → `Writing script` → `Generating scene images`, never `Waiting for localization choices`; stage bar all `completed`
  - `GET C/{id}` → `shouldRunAutomatically` = `true`, `targetCountry` = `jp`, `changeAppearance` and `changeCostume` = `true`, `scriptLanguage` = `ja`, every changed asset `referenceStatus` = `done`, every scene `imageStatus` = `done`

### TC-FC-35: Automatic run choices are checked at creation
- **App:** API
- **Steps:**
  1. `curl -i -X POST C/youtube -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","shouldRunAutomatically":true,"targetCountry":"xx"}'`
  2. Same with `"targetCountry":null,"changeSetting":true`
  3. Same with `"targetCountry":"jp","changeCostume":"maybe"`
  4. Step 1 with `"shouldRunAutomatically":false`
- **Expected:**
  1. `HTTP 400`, `detail` = `Unknown country 'xx'`
  2. `HTTP 400`, `detail` = `Pick a target country to change appearance, costume or setting`
  3. `HTTP 422`
  4. `HTTP 201`, `shouldRunAutomatically` = `false`, `targetCountry` = `null` — the choices are not read
  - Steps 1–3: `GET C` gains no row

### TC-FC-36: Automatic run passes both waits
- **App:** API unit
- **Precondition:** Clones created with `shouldRunAutomatically` = `true`; faked `claude`.
- **Steps:**
  1. `analyzing_shots` ends on a clone with `targetCountry` = `vn` and `changeAppearance`
  2. `analyzing_shots` ends on a clone with `targetCountry` = `null`, no flag, transcript language `ko`
  3. `proposing` ends with no asset changed
  4. `proposing` ends with one asset changed
  5. The last reference of a clone at `waiting` · `reviewing` becomes `done`; another one stays `failed`
  6. The last reference becomes `done` while every changed asset's reference is `done`
- **Expected:**
  1. `running` · `proposing`, `scriptLanguage` = `vi`; `waiting` · `choosing_localization` is never written
  2. `running` · `writing_script`, `scriptLanguage` = `ko`
  3. `running` · `writing_script`; no `clone_reference_image` request
  4. `waiting` · `reviewing`; one `clone_reference_image` request
  5. The clone stays `waiting` · `reviewing`
  6. `running` · `writing_script`, and the batch worker is woken up
  - The same reference events on a clone with `shouldRunAutomatically` = `false` change nothing

### TC-FC-37: Back to localization turns the automatic run off
- **App:** API
- **Precondition:** A clone of TC-FC-34 at `done`.
- **Steps:**
  1. `curl -i -X POST C/{id}/relocalize`
  2. `POST C/{id}/localization` with `targetCountry` = `jp`, `changeAppearance`; wait until every reference is `done`
- **Expected:**
  1. `HTTP 200`, `shouldRunAutomatically` = `false`, `status` = `waiting`, `step` = `choosing_localization`
  2. The clone stays `waiting` · `reviewing` until `Write script` is clicked

## Target setting

### TC-FC-40: Target setting is optional free text
- **App:** API
- **Precondition:** Two fresh clones like K1, K3 and K4, at `choosing_localization`.
- **Steps:**
  1. `curl -i -X POST C/{K3}/localization -H 'Content-Type: application/json' -d '{"targetCountry":null,"targetSetting":"  a modern Western city  ","changeAppearance":false,"changeCostume":false,"changeSetting":false}'`
  2. `curl -i -X POST C/{K4}/localization -H 'Content-Type: application/json' -d '{"targetCountry":"us","targetSetting":"   ","changeAppearance":false,"changeCostume":false,"changeSetting":true}'`
  3. `GET C/{K3}`
- **Expected:**
  1. `HTTP 200`, `targetSetting` = `a modern Western city`, `targetCountry` = `null`, `status` = `running`, `step` = `writing_script` — a setting with no country is accepted and ticks no flag
  2. `HTTP 200`, `targetSetting` = `null`, `step` = `proposing`
  3. `targetSetting` = `a modern Western city`; `scriptLanguage` = the transcript's language

### TC-FC-41: Target setting in the proposing message
- **App:** API unit
- **Precondition:** The clone of TC-FC-12.
- **Steps:**
  1. `localize` with `targetCountry` = `jp`, only `changeSetting`, `targetSetting` = `a modern Tokyo office district`
  2. `localize` as step 1 without `targetSetting`
  3. `localize` as step 1 with a `targetSetting` of 20,000 characters
- **Expected:**
  1. The message holds `Target country: Japan`, then `Target setting: a modern Tokyo office district` and `Follow the target setting where it differs from the original period or place.`, then `Change only: architecture, landscape, signs, objects`
  2. The message holds no `Target setting:` line and no `Follow the target setting` line
  3. The stored `targetSetting` and the line in the message hold all 20,000 characters

### TC-FC-42: Setting line of the script message
- **App:** API unit
- **Precondition:** The clone of TC-FC-16.
- **Steps:**
  1. Run `writing_script` with `targetCountry` = `jp`, `targetSetting` = `a modern Tokyo office district`
  2. Same with `targetCountry` = `jp`, no `targetSetting`
  3. Same with `targetCountry` = `null`, `targetSetting` = `a modern Western city`
  4. Same with `targetCountry` = `null`, no `targetSetting`
- **Expected:**
  1. The message holds `Setting: Japan. a modern Tokyo office district`
  2. `Setting: Japan`
  3. `Setting: a modern Western city`
  4. `Setting: keep the original.`
  - Every message still holds `Script language: … Keep the tone and register of the original dialogue.`

### TC-FC-43: Automatic run and relocalize keep the target setting
- **App:** API
- **Steps:**
  1. `curl -i -X POST C/youtube -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","shouldRunAutomatically":true,"targetCountry":"us","targetSetting":"a modern Western city","changeSetting":true}'`
  2. Step 1 with `"shouldRunAutomatically":false`
  3. When the clone of step 1 is `done`: `curl -i -X POST C/{id}/relocalize`
- **Expected:**
  1. `HTTP 201`, `shouldRunAutomatically` = `true`, `targetSetting` = `a modern Western city`
  2. `HTTP 201`, `targetSetting` = `null` — the choices are not read
  3. `HTTP 200`, `step` = `choosing_localization`, `targetCountry` = `us`, `targetSetting` = `a modern Western city`, `changeSetting` = `true`

### TC-FC-44: Target setting on the screens
- **App:** Frontend
- **Precondition:** A fresh clone like K1 at `choosing_localization`.
- **Steps:**
  1. Open `Localization`
  2. Keep `Keep original`; fill `Target setting` with `a modern Western city`
  3. Click `Write script`; wait until the stage bar shows `Script & images` as `current` or `completed`
  4. Open `Localization`; look at the summary
  5. Navigate to http://localhost:5071/film-clone; tick `Run every step automatically`
- **Expected:**
  - Step 1: `Target setting` is an empty text area under `Target country`, with the hint `Optional. e.g. a modern Western city instead of an ancient Chinese court`; it is enabled while the three checkboxes are disabled
  - Step 2: the button still reads `Write script`
  - Step 4: the read-only choices list `Target setting` = `a modern Western city`; the summary shows `Target setting` = `a modern Western city`
  - Step 5: `Target setting` shows under `Target country`, enabled with `Keep original`
  - A clone with no target setting shows no `Target setting` row in the summary

## Batches

### TC-FC-38: Frames and shots go in batches
- **App:** API unit
- **Precondition:** A clone with two shots on frames `images/moment-01-00m05s.jpg` and
  `images/moment-02-00m40s.jpg`; the `filmClone` model on `claude_cli`; `CLAUDE_MAX_IMAGES_PER_CALL` = 1;
  `CLONE_SCRIPT_SHOTS_PER_CALL` = 1; faked `claude`.
- **Steps:**
  1. Run `extracting_assets`; the reply names an asset on the second frame
  2. Run `analyzing_shots`; the first call answers `close_up` for frame 1, the second `wide` for frame 2
  3. Run `writing_script`; the first call answers title `Palace Escape` with the scene of shot 1, the second
     another title with the scene of shot 2
- **Expected:**
  1. One call with the first frame only; the asset keeps the second frame as its `reference_frame`
  2. Two calls, one frame each, in time order; shot 1 = `close_up`, shot 2 = `wide`
  3. Two calls, each listing only its own shot; scenes saved for both shots; `scriptTitle` = `Palace Escape`
