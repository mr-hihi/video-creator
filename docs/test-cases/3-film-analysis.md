## 3. Phân tích phim (Film Analysis) (3-film-analysis.md)

Test cases for [business/3-film-analysis.md](../business/3-film-analysis.md). Acronym `FA`.

## Test environment

- Stack, captcha switch, app labels and reference data (V1, V2, V3, F1): as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- `claude` CLI logged in for every Frontend case.
- Preset `Three scenes`: `POST /prompt-presets` `{"name":"Three scenes"}`, then `PUT` with the default
  prompts except `scene` = the default text followed by `Write exactly 3 scene prompts.` — at v2.
- Claude's answers vary between runs; cases check structure, not wording.

---

## Creation & end to end

### TC-FA-01: Upload a film, end to end
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis
  2. Keep source `Upload file`; drop F1 on the `Film` field
  3. Select `Vietnamese` from `Spoken language`; keep the preselected `Prompt preset`
  4. Fill `Max frames` with `20`
  5. *(captcha on)* Wait for the captcha; click `Analyze`
  6. Wait until the status badge shows `done`
  7. Click `Copy` on the open tab
- **Expected:**
  - URL becomes `/film-analysis/{id}`; the step list shows `Extracting audio`, `Transcribing speech`, `Picking key moments`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown`, `Writing character image prompts`, `Writing character voice prompts`, `Writing scene prompts` in that order
  - Summary: `Language` = `Vietnamese`, `Prompt preset` = `{default preset name} v{n}`, `Frames` = `{d} dialogue + {s} scene changes` with d ≤ 10 and d + s ≤ 20
  - `Result` has the tabs `Character image prompts`, `Character voice prompts`, `Scene prompts`, `Video notes`; `Character image prompts` is open and has ≥ 1 `##` heading
  - Step 7: the button reads `Copied` for 2 s; the clipboard equals `outputs.characterImagePrompts` of `GET /jobs/{id}`
  - `Video notes` shows frames with `##` headings; every `Scene change` heading has an image
  - `GET /jobs/{id}` → `type` = `film_analysis`, `options.maxFrames` = 20, `options.prompts` has the four keys, `markdown` = `null`, all four `outputs` set
  - `api/storage-test/{id}/output/` holds `images/` only — no `.md`; no `result.zip`
  - `curl -i http://localhost:5070/jobs/{id}/download` → `HTTP 409`, `detail` = `Job {id} has no zip download`

### TC-FA-02: YouTube link, end to end
- **App:** Frontend
- **Precondition:** Network up.
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis; click `YouTube link`
  2. Fill `YouTube link` with V1; keep `Max frames` at `1000`
  3. *(captcha on)* Wait for the captcha; click `Analyze`
  4. Wait until the status badge shows `done`
  5. Open the `Video notes` tab; click the timestamp of the second `##` heading
- **Expected:**
  - The button reads `Checking video…` while the request runs
  - Step list: `Fetching YouTube transcript`, `Picking key moments`, `Downloading video`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown`, then the three prompt steps
  - Summary has `Source` = `https://www.youtube.com/watch?v=vfjegxHDOwI` and `Captions` = `Auto-generated`
  - `GET /jobs/{id}` → `type` = `youtube_film_analysis`, `options.maxFrames` = 1000
  - Step 5: a new tab opens `https://www.youtube.com/watch?v=vfjegxHDOwI&t={seconds}s`

### TC-FA-03: Creation validation
- **App:** API
- **Steps:**
  1. `curl -i -X POST http://localhost:5070/jobs/youtube-film-analysis -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","maxFrames":9}'`
  2. Same with `"maxFrames":1001`
  3. Same with `"maxFrames":40,"presetId":"00000000-0000-0000-0000-000000000000"`
  4. Same with `"url":"https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG"`
  5. From `video-tool/`: `curl -i -X POST http://localhost:5070/jobs/film-analysis -F 'file=@notes.txt' -F 'language=auto'`
  6. From `video-tool/`: `curl -i -X POST http://localhost:5070/jobs/film-analysis -F 'file=@downloads/30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4' -F 'language=auto' -F 'maxFrames=5'`
- **Expected:**
  1. `HTTP 400`, `detail` = `Max frames must be between 10 and 1000`
  2. `HTTP 400`, same `detail`
  3. `HTTP 400`, `detail` = `Prompt preset 00000000-0000-0000-0000-000000000000 not found`
  4. `HTTP 400`, `detail` = `Playlist links are not supported. Open one video and copy its link`
  5. `HTTP 400`, `detail` = `Unsupported file type '.txt'. Use one of: .avi, .m4v, .mkv, .mov, .mp4, .webm`
  6. `HTTP 400`, `detail` = `Max frames must be between 10 and 1000`
  - No job created; no new folder under `api/storage-test/`

### TC-FA-04: Form states
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis
  2. Drop F1 on the `Film` field; *(captcha on)* wait for the captcha
  3. Fill `Max frames` with `5`, then `1001`, then `1000`
  4. Click `Edit presets`
- **Expected:**
  - Step 1: `Max frames` = 1000 with the hint `More frames cover more characters and scenes but take longer.`; the default preset is preselected as `{name} (default)`
  - Step 3: `Analyze` is disabled at `5` and `1001`, enabled at `1000`
  - Step 4: URL becomes `/settings?tab=prompt-override&id={default preset id}`

## Frames

### TC-FA-05: Dialogue frames and scene cuts are merged
- **App:** API unit
- **Precondition:** Duration 600000 ms; dialogue moments at 0, 10000, 60000 ms; cuts at 2000, 11000, 15000, 16000, 30000, 45000, 50000, 70000, 599800 ms.
- **Steps:**
  1. Merge with `maxFrames` = 8
  2. Merge with `maxFrames` = 6
- **Expected:**
  - Dropped in both: 2000 and 11000 (within 3 s of a dialogue frame), 16000 (within 3 s after 15000), 599800 (after duration − 500 ms)
  1. Frames 0, 10000, 15000, 30000, 45000, 50000, 60000, 70000; `frameCounts` = `{ "dialogue": 3, "scene": 5 }`
  2. 3 slots over 5 cuts → indices 0, 1, 3: frames 0, 10000, 15000, 30000, 50000, 60000; `frameCounts` = `{ "dialogue": 3, "scene": 3 }`
  - Scene frames are titled `Scene change`

### TC-FA-06: Half the frames go to dialogue
- **App:** API unit
- **Precondition:** Faked `claude` runner returning 25 valid moments.
- **Steps:**
  1. Run `picking_moments` for a job with `maxFrames` = 41
- **Expected:**
  - The user message contains `Choose at most 20 key moments`
  - 20 dialogue moments are kept

### TC-FA-07: No scene cut, and a failing scene detection
- **App:** API unit
- **Steps:**
  1. Run a job whose faked `ffmpeg` scene detection finds no cut
  2. Run a job whose faked `ffmpeg` scene detection exits with `Invalid data found when processing input`
- **Expected:**
  1. The job continues; `frameCounts.scene` = 0; frames = the dialogue moments only
  2. `failed` at `detecting_scenes`, `error_message` starts with `Scene detection failed:`; `capturing_frames` never starts

## Prompt passes

### TC-FA-08: Inputs of each prompt pass
- **App:** API unit
- **Precondition:** Faked `claude` runner recording args, working directory and stdin; it answers `## Character A` to the first call.
- **Steps:**
  1. Run the three prompt steps for a job whose `options.prompts` are `Image P`, `Voice P`, `Scene P` and whose `video_notes` row is `# Notes`
- **Expected:**
  - Call 1: `--system-prompt` = `Image P`; the message contains `Video notes:`, `# Notes` and the attached-frames line, no `Characters:`
  - Calls 2 and 3: `--system-prompt` = `Voice P` / `Scene P`; the message also contains `Characters:` followed by `## Character A`
  - Every call: `--tools ""` (no tool at all), stream-json input with one user event — the message, then each `images/*.jpg` as a text block with its path followed by a base64 image block; working directory = the system temp folder; no session persistence
  - Rows `character_image_prompts`, `character_voice_prompts`, `scene_prompts` hold the trimmed answers

### TC-FA-24: A pass sends at most the images per call
- **App:** API unit
- **Precondition:** A job with frames `images/moment-0.jpg` … `moment-3.jpg`; the `filmAnalysis` model on
  `google`; `GEMINI_MAX_IMAGES_PER_CALL` = 2.
- **Steps:**
  1. Run the three prompt steps
- **Expected:**
  - Every call attaches `images/moment-0.jpg` and `images/moment-2.jpg` only

### TC-FA-09: A failing pass keeps earlier results
- **App:** API unit
- **Steps:**
  1. Run a job whose faked `claude` answers the voice pass with `{"is_error": true, "result": "Overloaded"}`
  2. Run a job whose faked `claude` answers the image pass with `{"result": "   "}`
- **Expected:**
  1. `failed` at `writing_character_voice_prompts`, `error_message` = `claude failed: Overloaded`; `JobDetail.outputs` has `videoNotes` and `characterImagePrompts`, `characterVoicePrompts` and `scenePrompts` are `null`; the scene pass never runs
  2. `failed` at `writing_character_image_prompts`, `error_message` = `claude returned an empty answer`

### TC-FA-10: Result tabs after a failure
- **App:** Frontend
- **Precondition:** `FILM_PROMPT_TIMEOUT_SEC=1` in `api/.env.test`, test stack restarted; set it back afterwards.
- **Steps:**
  1. Create an upload analysis with F1 and wait until the status badge shows `failed`
- **Expected:**
  - `step` = `writing_character_image_prompts`; the error alert contains `timed out`
  - `Result` shows: `Video notes` with the notes and their images; `Character image prompts`, `Character voice prompts` and `Scene prompts` read `Not generated`
  - The `Rerun with another preset` panel is shown (the job has video notes)

### TC-FA-11: The job keeps the prompts it was created with
- **App:** API
- **Precondition:** Preset `Three scenes` at v2.
- **Steps:**
  1. `curl -s -X POST http://localhost:5070/jobs/youtube-film-analysis -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","presetId":"{Three scenes id}"}'`
  2. `PUT /prompt-presets/{Three scenes id}` changing `scene` to `Changed`
  3. `curl -s http://localhost:5070/jobs/{id}`
- **Expected:**
  - Step 3: `options.preset` = `{ "id": "{Three scenes id}", "name": "Three scenes", "version": 2 }`; `options.prompts` has the four keys and `scene` ends with `Write exactly 3 scene prompts.`

## Rerun

### TC-FA-12: Rerun with another preset
- **App:** Frontend
- **Precondition:** TC-FA-01 is `done`; preset `Three scenes` at v2.
- **Steps:**
  1. Navigate to `/film-analysis/{TC-FA-01 id}`
  2. In `Rerun with another preset`, select `Three scenes`; *(captcha on)* wait for the captcha; click `Rerun`
  3. Wait until the status badge shows `done`
  4. Expand `Prompts used`
- **Expected:**
  - URL becomes `/film-analysis/{new id}`; the step list shows only `Writing character image prompts`, `Writing character voice prompts`, `Writing scene prompts`
  - Summary: `Rerun of` links to `/film-analysis/{TC-FA-01 id}`; `Language` and `Frames` equal those of TC-FA-01; `Prompt preset` = `Three scenes v2`
  - `Video notes` equals that of TC-FA-01 and its images load from `/jobs/{new id}/files/…`
  - `Scene prompts` has 3 `##` headings
  - Step 4: three prompts — character image, character voice, scene — each with `Copy`; no `Video → Markdown`
  - `GET /jobs/{new id}` → `type` = `film_analysis_rerun`, `options.rerunOfJobId` = TC-FA-01's id

### TC-FA-13: Rerun rules
- **App:** API
- **Precondition:** TC-VTM-01 job `done`; a film analysis job `pending` or `processing` before `writing_markdown` (J).
- **Steps:**
  1. `curl -i -X POST http://localhost:5070/jobs/{TC-VTM-01 id}/film-analysis-rerun -H 'Content-Type: application/json' -d '{}'`
  2. Same for J
  3. Same for `00000000-0000-0000-0000-000000000000`
  4. Same for TC-FA-01 with `{"presetId":"00000000-0000-0000-0000-000000000000"}`
  5. *(captcha on)* Same for TC-FA-01 with header `X-Captcha-Token:` (empty)
- **Expected:**
  1. `HTTP 409`, `detail` = `Job {TC-VTM-01 id} is not a film analysis`
  2. `HTTP 409`, `detail` = `Job {J id} has no video notes to reuse`
  3. `HTTP 404`, `detail` = `Job 00000000-0000-0000-0000-000000000000 not found`
  4. `HTTP 400`, `detail` = `Prompt preset 00000000-0000-0000-0000-000000000000 not found`
  5. `HTTP 403`, `detail` = `Captcha verification failed`
  - No job created

### TC-FA-14: A rerun survives deleting its source
- **App:** Frontend + API
- **Precondition:** TC-FA-12 has run.
- **Steps:**
  1. Delete TC-FA-01 from `Analysis history`
  2. Navigate to `/film-analysis/{TC-FA-12 id}`
  3. `curl -s -o /dev/null -w '%{http_code}' http://localhost:5070/jobs/{TC-FA-12 id}/files/images/{first frame file}`
- **Expected:**
  - Step 2: `Rerun of` reads `(deleted)`; every tab keeps its content and the `Video notes` images load
  - Step 3: `200`

## History & delete

### TC-FA-15: Analysis history
- **App:** Frontend
- **Precondition:** TC-FA-01, TC-FA-02 and TC-FA-12 have run; TC-VTM-01 has run.
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis
- **Expected:**
  - `Analysis history` has the three film analysis rows and no TC-VTM-01 row
  - Badges: TC-FA-01 `Upload`, TC-FA-02 `YouTube`, TC-FA-12 `Rerun`; each row shows `{preset name} v{n}`, `{step label} · {created time}`, a status badge, `View`, `Delete`
  - A `pending` / `processing` row has no `Delete`; the list refreshes every 3 s while one exists

### TC-FA-16: Delete an analysis
- **App:** Frontend + API
- **Precondition:** TC-FA-02 is `done`.
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis; click `Delete` on the TC-FA-02 row
  2. Click `Cancel`; click `Delete` again; click `OK`
  3. `curl -s -o /dev/null -w '%{http_code}' http://localhost:5070/jobs/{TC-FA-02 id}`
- **Expected:**
  - Dialog `Delete this analysis? The video, frames and prompts are removed.`
  - After `Cancel` the row stays; after `OK` the row disappears
  - Step 3: `404`; `api/storage-test/{TC-FA-02 id}/` no longer exists

### TC-FA-17: Delete rules
- **App:** API + API unit
- **Steps:**
  1. `curl -i -X DELETE http://localhost:5070/jobs/{TC-VTM-01 id}`
  2. `DELETE` a film analysis job while it is `processing`
  3. `DELETE http://localhost:5070/jobs/00000000-0000-0000-0000-000000000000`
  4. *(API unit)* Delete a `done` film analysis job with four `job_outputs` rows
- **Expected:**
  1. `HTTP 409`, `detail` = `Only film analysis jobs can be deleted`
  2. `HTTP 409`, `detail` = `Job {id} is still running`; the job continues
  3. `HTTP 404`, `detail` = `Job 00000000-0000-0000-0000-000000000000 not found`
  4. No `job_outputs` row and no storage folder left for that job

## Screens & lifecycle

### TC-FA-18: Detail page of a job that is not an analysis
- **App:** Frontend
- **Precondition:** TC-VTM-01 has run.
- **Steps:**
  1. Navigate to `/film-analysis/{TC-VTM-01 id}`
  2. Navigate to `/film-analysis/00000000-0000-0000-0000-000000000000`
- **Expected:**
  - Both show `Analysis not found` with a link to `/film-analysis`

### TC-FA-19: Prompts used
- **App:** Frontend
- **Precondition:** TC-FA-01 is `done`.
- **Steps:**
  1. Navigate to `/film-analysis/{TC-FA-01 id}`; expand `Prompts used`
  2. Click `Copy` under the scene prompt
- **Expected:**
  - Four read-only prompts equal to `options.prompts` of `GET /jobs/{id}`
  - Step 2: the clipboard equals `options.prompts.scene`

### TC-FA-20: API restarted during a prompt pass
- **App:** Frontend
- **Steps:**
  1. Create an upload analysis with F1
  2. When the step shows `Writing character voice prompts`, ask the user to stop the test stack (Ctrl+C) and start `sh run.sh start_test` again
  3. Open `/film-analysis/{id}` again
- **Expected:**
  - Right after the restart `GET /jobs/{id}` shows `status` = `pending` or `processing` with `step` = `extracting_audio`
  - The job re-runs every step and ends `done` with exactly one output per tab

## Make a film

### TC-FA-21: The `Make a film` panel
- **App:** Frontend
- **Precondition:** TC-FA-01 is `done` (`options.language` = `vi`); a film analysis job J `failed`; Film Studio
  project P1 active and project P5 archived. Settings `filmStudioImageProvider` and `filmStudioClipProvider` at
  their default `null`, the `image` and `video` routes at their default `google_flow`.
- **Steps:**
  1. Navigate to `/film-analysis/{J id}`
  2. Navigate to `/film-analysis/{TC-FA-01 id}`
  3. Select `Test Series` from `Project`
  4. Click `Change` on the media line
- **Expected:**
  1. No `Make a film` panel
  2. The panel shows `Project` = `New project`, with `Test Series` in the list and no `Old Series`;
     `Project name` = `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này_ _vfjegxHDOwI`; `Language` = `Vietnamese`;
     `Frame` = `Landscape 16:9`, `Style` = `Photorealistic`; no `Images with` or `Clips with` field — the line
     `Images with: Google Flow · Clips with: Google Flow` with a link `Change` → `/settings?tab=film-studio`;
     `Target length` = 60
  3. `Project name`, `Frame`, `Style` and `Language` are hidden; the media line stays
  4. URL becomes `/settings?tab=film-studio`; tab `Film Studio` is open

### TC-FA-22: Make a film in a new project
- **App:** Frontend *(real provider)*
- **Precondition:** TC-FA-01 is `done`.
- **Steps:**
  1. Navigate to `/film-analysis/{TC-FA-01 id}`
  2. In `Make a film`, keep `New project`; fill `Project name` with `Sequel Test`; fill `Target length` with `16`;
     fill `Extra direction` with `Set it in winter`
  3. *(captcha on)* Wait for the captcha; click `Make a film`
  4. As soon as the episode page opens, click `Stop`
- **Expected:**
  - URL becomes `/films/{new project id}/episodes/1`; the status was `running` before step 4
  - `Script` shows `Source` linking to `/film-analysis/{TC-FA-01 id}`
  - `GET /films/episodes/{id}` → `source` = `film_analysis`, `sourceJobId` = TC-FA-01's id, `idea` = `Set it in winter`
  - `/films` lists `Sequel Test`

### TC-FA-23: Make a film in an existing project
- **App:** Frontend *(real provider)*
- **Precondition:** TC-FA-01 is `done`; P1 has episodes with `lastEpisodeNumber` = 2.
- **Steps:**
  1. Navigate to `/film-analysis/{TC-FA-01 id}`
  2. Select `Test Series` from `Project`; fill `Target length` with `16`
  3. *(captcha on)* Wait for the captcha; click `Make a film`; click `Stop` as soon as the episode page opens
- **Expected:**
  - URL becomes `/films/{P1}/episodes/3`
  - No new Film Studio project exists
