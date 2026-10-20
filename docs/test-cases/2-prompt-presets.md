## 2. Bộ prompt (Prompt Presets) (2-prompt-presets.md)

Test cases for [business/2-prompt-presets.md](../business/2-prompt-presets.md). Acronym `PP`.

## Test environment

- Stack, captcha switch and app labels: as in [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- Start from a fresh test DB (`sh run.sh migrate test` on an empty `video_tool_test`), so `Default` is at v1.
- Shorthand: `P` = `http://localhost:5070/prompt-presets`; `{default text}` = the text from `GET P/defaults`.

---

## Presets screen

### TC-PP-01: Default preset on first visit
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=prompt-override
  2. Expand `Added by the app` under `Video → Markdown`
  3. Expand `Added by the app` under `Scene prompts`
  4. Expand `Added by the app` under `Film script`
  5. Expand `Added by the app` under `Clone shots`
  6. Expand `Added by the app` under `Film outline`
  7. Expand `Added by the app` under `Story bible`
- **Expected:**
  - `Presets` lists one row `Default` with badges `Default preset` and `System` and `v1`; it is selected
  - Editor: `Name` = `Default` and disabled; twelve sections in the order `Video → Markdown`, `Speakers & sounds`, `Character image prompts`, `Character voice prompts`, `Scene prompts`, `Film outline`, `Film script`, `Story bible`, `Clone assets`, `Clone shots`, `Clone localization`, `Clone script`, each with badge `Default` and a counter `{n} / 20000`
  - `Video → Markdown` shows `Used by` Video to Markdown, Film Analysis and Film Clone; `Speakers & sounds` shows Film Analysis and Film Clone; the next three show Film Analysis; `Film outline`, `Film script` and `Story bible` show Film Studio; the four clone sections show Film Clone
  - No `Delete` and no `Set as default` button; `Save` is disabled
  - Step 2 shows the output shape `title`, `summary`, `moments[] { atMs, title }`, the line `Choose at most {N} key moments. Set atMs to the start time of the line where the moment begins.` and the transcript format `[{start_ms}ms] {text}`; below them the heading `Whole video mode — one message per part of the video, its frames attached at one per second:`, the line `This part of the video runs from {start} to {end}. Choose at most {m} key moments in it. Set atMs to the time of the frame or the line where the moment begins.`, `Transcript:` and `Frames:`
  - Step 3 shows the `Video notes:` heading, the `Characters:` heading and the line `The frames referenced in the notes are attached below as images, each after its file name. Look at them to see the characters and scenes.`
  - Step 4 shows the output shape `recap`, `characters[] { name, entityType, description, voiceDescription, referenceFrame }`, `scenes[] { imagePrompt, videoPrompt, narratorText, characterNames[], durationS }`, the line `Write scenes whose clip lengths, each minus its first second, add up to about {target_duration_s}s. Give each scene the clip length its action needs, 4-30 s; a typical clip lasts {clip}s. The first second of every clip is cut, so a scene's narration must fit in its clip length minus 1 s.` and the headings `Story bible:`, `Earlier episodes:`, `Episode outline:`, `Story so far:`
  - Step 5 shows the output shape `shots[] { frame, shotSize, cameraAngle, emotion, action, assetNames[] }` and the line `Give exactly one entry per frame.`
  - Step 6 shows the output shape `title`, `logline`, `parts[] { title, plan, durationS }`, `musicPrompt`, `thumbnailPrompt` and the line `Split the episode into parts whose lengths add up to about {target_duration_s}s. Each part lasts 8-600 s.`
  - Step 7 shows the output shape `summary`, `storyBible`, the headings `Current story bible:` and `Parts:`, and the line `Keep the story bible under 20000 characters.`

### TC-PP-02: Create, edit and save a preset
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=prompt-override
  2. Click `New preset`, fill `Name` with `Uppercase titles`, click `Create`
  3. In `Video → Markdown`, add a new last line `Write every moment title in uppercase letters.`
  4. Click `Save`
  5. Reload the page
- **Expected:**
  - Step 2: URL becomes `/settings?tab=prompt-override&id={id}`; row `Uppercase titles` `v1` selected; every section badge `Default`
  - Step 3: `Video → Markdown` badge becomes `Customized`; `Save` is enabled
  - Step 4: notice `Saved as v2`; the row shows `v2`; `Save` is disabled again
  - Step 5: `Uppercase titles` is still selected and the added line is still there

### TC-PP-03: Reset to default and discard
- **App:** Frontend
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`
  2. Click `Reset to default` in `Video → Markdown`
  3. Click `Discard changes`
- **Expected:**
  - Step 2: the text area equals `{default text}` of `videoToMarkdown`; badge `Default`; `Save` enabled; the row still shows `v2`
  - Step 3: the text ends with `Write every moment title in uppercase letters.` again; badge `Customized`; `Save` disabled

### TC-PP-04: Unsaved changes guard
- **App:** Frontend
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`, type `x` at the end of `Scene prompts`
  2. Click the `Default` row; click `Cancel` in the dialog
  3. Click the `Default` row; click `OK` in the dialog
- **Expected:**
  - Steps 2 and 3 show the dialog `Discard unsaved changes?`
  - Step 2: `Uppercase titles` stays selected with the `x`
  - Step 3: `Default` is selected; reopening `Uppercase titles` shows no `x` and `v2`

### TC-PP-18: Presets live in the `Prompt override` tab of Settings
- **App:** Frontend
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. Navigate to http://localhost:5071/settings
  2. Navigate to http://localhost:5071/prompt-presets?id={Uppercase titles id}
  3. Type `x` at the end of `Scene prompts`; click tab `General`; click `Cancel`
  4. Click tab `General`; click `OK`
  5. Click tab `AI models`
  6. Navigate to http://localhost:5071/settings?tab=prompt-presets&id={Uppercase titles id}
- **Expected:**
  - Step 1: the header has no `Prompt presets` item; tabs `General` · `AI models` · `Prompt override` · `Film Clone` · `Film Studio`, `General` open
  - Step 2: URL becomes `/settings` with the query `tab=prompt-override` and `id={Uppercase titles id}`; `Settings` is highlighted in the header; tab `Prompt override` is open with the line `The prompts the AI model follows in every job. Each job copies the prompts of the preset chosen when it is created.`, the panels `Presets` and `Editor`, and `Uppercase titles` selected
  - Steps 3 and 4 show the dialog `Discard unsaved changes?`; after `Cancel` the tab stays open with the `x`
  - Step 4: URL becomes `/settings?tab=general`
  - Step 5: no dialog; URL becomes `/settings?tab=ai-models`
  - Step 6: URL becomes `/settings` with the query `tab=prompt-override` and `id={Uppercase titles id}`; tab `Prompt override` is open with `Uppercase titles` selected

## Rules & validation

### TC-PP-05: Name and prompt validation
- **App:** API
- **Precondition:** TC-PP-02 has run; `{body}` = the twelve prompts of `GET P/{Default id}`.
- **Steps:**
  1. `curl -i -X POST P -H 'Content-Type: application/json' -d '{"name":"   "}'`
  2. `POST P` with a `name` of 51 `a` characters
  3. `POST P` with `{"name":"uppercase TITLES"}`
  4. `PUT P/{Uppercase titles id}` with `{body}` but `"scene": "  "`
  5. `PUT P/{Uppercase titles id}` with `{body}` but `scene` of 20001 characters
  6. `PUT P/{Uppercase titles id}` with `{body}` without `scene`
  7. `PUT P/{Default id}` with `{body}` and `"name":"Main"`
  8. `POST P` with `{}`
- **Expected:**
  1. `HTTP 400`, `detail` = `Preset name must be 1-50 characters`
  2. `HTTP 400`, same `detail`
  3. `HTTP 409`, `detail` = `A preset named 'uppercase TITLES' already exists`
  4. `HTTP 400`, `detail` = `Prompt 'scene' must be 1-20000 characters`
  5. `HTTP 400`, same `detail`
  6. `HTTP 422`, `detail` names `scene`
  7. `HTTP 409`, `detail` = `The Default preset cannot be renamed`
  8. `HTTP 422`, `detail` names `name`
  - `GET P` still lists exactly `Default` and `Uppercase titles`; `Uppercase titles` is still `currentVersion` 2

### TC-PP-06: Same prompts write no version; rename only
- **App:** API
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. `PUT P/{Uppercase titles id}` with its current prompts and `"name":"Uppercase titles"`
  2. `PUT P/{Uppercase titles id}` with its current prompts and `"name":"Caps titles"`
  3. `PUT P/{Uppercase titles id}` with its current prompts and `"name":"Uppercase titles"`
  4. `GET P/{Uppercase titles id}/versions`
- **Expected:**
  - Every call → `HTTP 200`, `currentVersion` = 2
  - Step 2: `name` = `Caps titles`; step 3: back to `Uppercase titles`
  - Step 4: exactly two rows, `v2` (`saved`) and `v1` (`created`)

## Versions

### TC-PP-07: History and restore
- **App:** Frontend
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`; replace `Scene prompts` with `Scene v3`; click `Save`
  2. Click `History`
  3. Click row `v1`
  4. Click `Restore` on `v1`
- **Expected:**
  - Step 1: notice `Saved as v3`
  - Step 2: rows `v3` (`Saved`, tagged `Current`), `v2` (`Saved`), `v1` (`Created`), newest first
  - Step 3: the twelve prompts of v1 shown read-only — all equal `{default text}`
  - Step 4: notice `Restored v1 as v4`; new top row `v4` · `Restored from v1` tagged `Current`; the editor shows the default text in all twelve sections, every badge `Default`; the row shows `v4`

### TC-PP-08: Only the 20 newest versions are kept
- **App:** API
- **Steps:**
  1. `POST P` with `{"name":"Many versions"}`
  2. 22 times, `PUT P/{id}` with the default prompts but `"scene":"Scene {i}"` for i = 1 … 22
  3. `GET P/{id}/versions`
  4. `GET P/{id}/versions/1` and `POST P/{id}/versions/3/restore`
  5. `GET P/{id}/versions/4`
- **Expected:**
  - After step 2: `currentVersion` = 23
  - Step 3: 20 rows, `v23` down to `v4`
  - Step 4: both `HTTP 404`, `detail` = `Version 1 of preset {id} not found` / `Version 3 of preset {id} not found`
  - Step 5: `HTTP 200`, `prompts.scene` = `Scene 3`

## Default mark & delete

### TC-PP-09: Set as default moves the mark
- **App:** Frontend + API
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`; click `Set as default`
  2. `curl -s P`
  3. Navigate to http://localhost:5071/ and open the `Prompt preset` dropdown
  4. Back on tab `Prompt override` of `/settings`, select `Default`, click `Set as default`
- **Expected:**
  - Step 1: badge `Default preset` moves to `Uppercase titles`; `Set as default` disappears for it; its `Delete` is disabled with the hint `Set another preset as default first`
  - Step 2: exactly one item has `isDefault` = `true` — `Uppercase titles`
  - Step 3: `Uppercase titles (default)` is preselected
  - Step 4: the mark is back on `Default`

### TC-PP-10: Delete rules
- **App:** API
- **Precondition:** TC-PP-02 has run.
- **Steps:**
  1. `curl -i -X DELETE P/{Default id}`
  2. `POST P/{Uppercase titles id}/default`, then `DELETE P/{Uppercase titles id}`
  3. `DELETE P/00000000-0000-0000-0000-000000000000`
  4. `POST P/{Default id}/default`
- **Expected:**
  1. `HTTP 409`, `detail` = `The Default preset cannot be deleted`
  2. `HTTP 409`, `detail` = `Set another preset as default before deleting 'Uppercase titles'`
  3. `HTTP 404`, `detail` = `Prompt preset 00000000-0000-0000-0000-000000000000 not found`
  4. `HTTP 200`; both presets still exist

### TC-PP-11: Deleting a preset keeps its jobs
- **App:** Frontend + API
- **Precondition:** `claude` CLI logged in.
- **Steps:**
  1. Create preset `Temp` (`POST P`)
  2. `curl -s -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","presetId":"{Temp id}"}'`
  3. Navigate to `/settings?tab=prompt-override&id={Temp id}`; click `Delete`; confirm
  4. `curl -s http://localhost:5070/jobs/{job id}`; open `/jobs/{job id}`
- **Expected:**
  - Step 3: dialog `Delete preset 'Temp'? Jobs that used it keep their prompts.`; afterwards `Temp` is gone and `Default` is selected
  - Step 4: `options.preset` = `{ "id": "{Temp id}", "name": "Temp", "version": 1 }`, `options.prompts.videoToMarkdown` still set; the job runs to `done`; summary shows `Prompt preset` = `Temp v1`

## Duplicate, export, import

### TC-PP-12: Duplicate
- **App:** Frontend + API
- **Precondition:** TC-PP-07 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`; click `Duplicate`; select `Uppercase titles` again; click `Duplicate`
  2. Open `History` of `Uppercase titles (copy)`
  3. `POST P` with a `name` of 50 `b` characters, then `POST P/{its id}/duplicate`
- **Expected:**
  - Step 1: rows `Uppercase titles (copy)` and `Uppercase titles (copy 2)`, each `v1`, neither default nor system; their prompts equal those of `Uppercase titles`
  - Step 2: one row `v1` · `Duplicated from Uppercase titles v4`
  - Step 3: `HTTP 201`, `name` = 43 `b` characters + ` (copy)` — 50 characters

### TC-PP-13: Export and import round trip
- **App:** Frontend
- **Precondition:** TC-PP-07 has run.
- **Steps:**
  1. Navigate to `/settings?tab=prompt-override&id={Uppercase titles id}`; click `Export`
  2. Open the downloaded file
  3. Click `Import`; choose the downloaded file
  4. Open `History` of the new preset
  5. Import the same file again
- **Expected:**
  - Step 1: download `Uppercase titles.preset.json`
  - Step 2: `format` = `video-tool-prompt-preset`, `formatVersion` = 5, `name` = `Uppercase titles`, `prompts` with the twelve keys equal to the editor; no version or default field
  - Step 3: notice `Imported as 'Uppercase titles (imported)'`; that row is selected, `v1`
  - Step 4: one row `v1` · `Imported from Uppercase titles.preset.json`
  - Step 5: `Uppercase titles (imported 2)`

### TC-PP-14: Import rejects bad files
- **App:** API
- **Steps:** `curl -i -X POST P/import -F 'file=@{file}'` with:
  1. `bad.json` = `{"foo":1}`
  2. a valid export with `"formatVersion": 6`
  3. a valid export with `"characterVoice": ""`
  4. `notes.txt` with the text `hello`
  5. a valid export padded to 1.1 MB
  6. no `file` part
- **Expected:**
  1. `HTTP 400`, `detail` = `Not a prompt preset file`
  2. `HTTP 400`, same `detail`
  3. `HTTP 400`, `detail` = `Prompt 'characterVoice' must be 1-20000 characters`
  4. `HTTP 400`, `detail` = `Not a prompt preset file`
  5. `HTTP 413`, `detail` = `Preset file exceeds 1 MB`
  6. `HTTP 422`
  - `GET P` gains no row

### TC-PP-16: Import a file exported before Film Studio
- **App:** API
- **Precondition:** `old.preset.json` = `{"format":"video-tool-prompt-preset","formatVersion":1,"name":"Old export","prompts":{"videoToMarkdown":"V","characterImage":"I","characterVoice":"C","scene":"S"}}`.
- **Steps:**
  1. `curl -s -X POST P/import -F 'file=@old.preset.json'`
  2. The same file with `"formatVersion":2` and no `filmScript`
- **Expected:**
  1. `HTTP 201`, `name` = `Old export`, `prompts.videoToMarkdown` = `V` … `prompts.scene` = `S`; `prompts.filmOutline`, `prompts.filmScript`, `prompts.storyBible` and the four clone prompts = their `{default text}`
  2. `HTTP 400`, `detail` = `Not a prompt preset file`

### TC-PP-17: Import a file exported before Film Clone
- **App:** API
- **Precondition:** `v2.preset.json` = `{"format":"video-tool-prompt-preset","formatVersion":2,"name":"V2 export","prompts":{"videoToMarkdown":"V","characterImage":"I","characterVoice":"C","scene":"S","filmScript":"F"}}`.
- **Steps:**
  1. `curl -s -X POST P/import -F 'file=@v2.preset.json'`
  2. A `formatVersion` 3 file with the five keys above plus `cloneAssets`, `cloneShots`, `cloneLocalization` and no `cloneScript`
  3. A `formatVersion` 3 file with the five keys above plus the four clone prompts `A`, `B`, `L`, `T`
  4. A `formatVersion` 4 file with the nine keys of step 3 plus `filmOutline` and no `storyBible`
- **Expected:**
  1. `HTTP 201`, `prompts.filmScript` = `F`; `filmOutline`, `storyBible`, `speakersAndSounds`, `cloneAssets`, `cloneShots`, `cloneLocalization`, `cloneScript` = their `{default text}`
  2. `HTTP 400`, `detail` = `Not a prompt preset file`
  3. `HTTP 201`, `prompts.filmScript` = `F`, `prompts.cloneScript` = `T`; `filmOutline`, `storyBible` and `speakersAndSounds` = their `{default text}`
  4. `HTTP 400`, `detail` = `Not a prompt preset file`

### TC-PP-19: Speakers & sounds — editor, export and older files
- **App:** Frontend + API
- **Precondition:** `v4.preset.json` = a `formatVersion` 4 file with the eleven keys of 2.4 rule 2, each `X`, name
  `V4 export`.
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=prompt-override; expand `Added by the app` under `Speakers & sounds`, then under `Character voice prompts`
  2. `curl -s P/defaults`
  3. `curl -s -X POST P/import -F 'file=@v4.preset.json'`
  4. The same file with `"formatVersion":5`
- **Expected:**
  - Step 1: `Speakers & sounds` shows the output shape `speakers[] { name, voice }`, `lines[] { atMs, speaker }`, `sounds[] { atMs, kind, description }` with the kinds `action`, `silence`, `ambient`, `music`, and the parts `Speakers so far:`, `Use the same name for the same voice.`, `Transcript:`; `Character voice prompts` also shows the `full_video` line `The film is attached as video.`
  - Step 2: `prompts.speakersAndSounds` asks to tell the voices apart and to mark sounds; `prompts.characterVoice` asks for one entry per distinct voice and no longer says the transcript has no speaker labels
  - Step 3: `HTTP 201`, every imported prompt = `X`; `prompts.speakersAndSounds` = its `{default text}`
  - Step 4: `HTTP 400`, `detail` = `Not a prompt preset file` — version 5 needs all twelve

## Startup

### TC-PP-15: Default preset restored at API start
- **App:** API unit
- **Steps:**
  1. Start the app with an empty `prompt_presets` table
  2. Start the app with presets `A` and `B`, neither default, and no `Default`
  3. Start the app with `Default` and `A`, `A` being the default
- **Expected:**
  1. `Default` exists, `is_system`, `is_default`, `current_version` = 1, its v1 prompts equal the code defaults, `change` = `created`
  2. `Default` is created as in 1 and is the only default
  3. Nothing changes — `A` stays the default
