## 8. Mô hình AI (AI Models) (8-ai-models.md)

Test cases for [business/8-ai-models.md](../business/8-ai-models.md). Acronym `AIM`.

## Test environment

- Stack, captcha switch, app labels and reference data (V1, V2, F1): as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- Start from a fresh test DB, so `app_settings` is empty and neither the `google` nor the `openai` provider
  has a key. `api/.env.test` sets `SETTINGS_SECRET_KEY` as in [7-provider-settings.md](./7-provider-settings.md).
- Shorthand: `S` = `http://localhost:5070/settings`, `PV` = `http://localhost:5070/settings/providers`.
  Model values: `CLI` = `{"provider":"claude_cli","model":"default"}`, `G38` =
  `{"provider":"google","model":"gemini-3.8-flash"}`, `G4` = `{"provider":"google","model":"gemini-4-argon"}`,
  `OA` = `{"provider":"openai","model":"gpt-6-astra"}`.
- Fake keys, refused by their vendors, that make a provider set up without spending credit: Google
  `AIza-test-0000000000wxyz`, OpenAI `sk-test-0000000000wxyz`.
- Only TC-AIM-14 calls a real vendor API and spends credit. It needs a working Google AI key, entered on the
  `Google AI (Gemini, Veo)` sub-tab of `General` before the case and removed afterwards. **API unit** cases fake the Gemini and OpenAI HTTP,
  the `claude` runner and `ffmpeg`.
- `claude` CLI signed in for every Frontend case that runs a job with Claude.
- Answers vary between runs; live cases check structure, not wording.

---

## Settings

### TC-AIM-01: Defaults and the Text group of the AI models tab
- **App:** Frontend + API
- **Steps:**
  1. `curl -s S`
  2. Navigate to http://localhost:5071/settings?tab=ai-models
  3. Select `Gemini 3.8 Flash` from `All steps`; select `GPT-6 Astra` from `Film clone`
  4. Select `Whole video` from `Input mode`; click `Save`
  5. Reload the page; `curl -s S`
  6. Click `General` in the warning under `All steps`
- **Expected:**
  - Step 1: `aiModel` = `CLI`; `aiStepModels` = `{"moments":null,"filmAnalysis":null,"filmScript":null,"filmClone":null}`; `inputMode` = `subtitles`; `filmCloneInputMode` = `subtitles`
  - Step 2: tab `AI models` opens with the group `Text`: `All steps` = `Claude (CLI default)` and its hint `The model of every step set to Same as all steps.`, `Apply to all steps` disabled, rows `Key moments`, `Film analysis`, `Film script`, `Film clone` each = `Same as all steps (Claude (CLI default))` with their hints, then `Input mode` = `Subtitles` with the hint `For Video to Markdown and Film Analysis. Subtitles: the model reads the transcript to pick key moments. Whole video: it also sees one frame per second — slower, with more calls on long videos.`; then the groups `Images`, `Clips`, `Speech`, `Music`; `Save` is disabled
  - Step 3: `Key moments`, `Film analysis` and `Film script` read `Same as all steps (Gemini 3.8 Flash)`, `Film clone` reads `GPT-6 Astra`; warning `Google AI (Gemini, Veo) is not set up — add its key in General.` under `All steps`, `OpenAI is not set up — add its key in General.` under `Film clone`, none under the other rows; `Apply to all steps` and `Save` are enabled
  - Step 4: notice `Saved`
  - Step 5: the same selections; body has `"aiModel":G38`, `"aiStepModels":{"moments":null,"filmAnalysis":null,"filmScript":null,"filmClone":OA}`, `"inputMode":"whole_video"`, `"filmCloneInputMode":"subtitles"`
  - Step 6: URL becomes `/settings?tab=general&provider=google`; tab `General` open with sub-tab `Google AI (Gemini, Veo)` selected

### TC-AIM-02: Setting validation
- **App:** API
- **Steps:**
  1. `curl -i -X PATCH S -H 'Content-Type: application/json' -d '{"aiModel":"gemini"}'`
  2. `PATCH S` `{"aiModel":{"provider":"google","model":"gpt-6-astra"}}`
  3. `PATCH S` `{"aiStepModels":{"subtitles":null}}`
  4. `PATCH S` `{"aiStepModels":{"filmScript":{"provider":"claude_cli","model":"claude-9"}}}`
  5. `PATCH S` `{"inputMode":"frames"}`
  6. `PATCH S` `{"aiModel":G38,"inputMode":"frames"}`
  7. `PATCH S` `{"aiModel":G38}` while the `google` provider has no key
  8. `PATCH S` `{"filmCloneInputMode":"frames"}`
  9. `curl -i -X PATCH S/ai-models -H 'Content-Type: application/json' -d '{"aiModel":{"provider":"google","model":"gpt-6-astra"}}'`
- **Expected:**
  1. `HTTP 400`, `detail` = `Invalid value for 'aiModel'`
  2. `HTTP 400`, `detail` = `Invalid value for 'aiModel'`
  3. `HTTP 400`, `detail` = `Invalid value for 'aiStepModels'`
  4. `HTTP 400`, `detail` = `Invalid value for 'aiStepModels'`
  5. `HTTP 400`, `detail` = `Invalid value for 'inputMode'`
  6. `HTTP 400`, `detail` = `Invalid value for 'inputMode'`; `aiModel` is not changed
  7. `HTTP 200`, `aiModel` = `G38`
  8. `HTTP 400`, `detail` = `Invalid value for 'filmCloneInputMode'`
  9. `HTTP 400`, `detail` = `Invalid value for 'aiModel'`

### TC-AIM-03: The model is read at each call, the input mode at creation
- **App:** API + API unit
- **Steps:**
  1. `PATCH S` `{"inputMode":"whole_video"}`; `curl -s -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}'`
  2. `PATCH S` `{"inputMode":"subtitles"}`; `curl -s http://localhost:5070/jobs/{id of step 1}`
  3. (API unit) Run a clone whose settings are all `CLI` through `extracting_assets`; set `aiStepModels.filmClone` = `G38`; run `analyzing_shots`
- **Expected:**
  - Step 1: `HTTP 201`; `options.inputMode` = `whole_video`; no `options.aiModel`; `aiUsed` = `{}`
  - Step 2: the job still has `options.inputMode` = `whole_video`
  - Step 3: `extracting_assets` calls the faked `claude`, `analyzing_shots` the faked Gemini; the clone's `ai_used` = `{"extracting_assets":CLI,"analyzing_shots":G38}`

### TC-AIM-04: A provider not set up is refused at creation
- **App:** API
- **Precondition:** Neither `google` nor `openai` has a key. A `done` Film Analysis job A1; Film Studio project P1
  (see [4-film-studio.md](./4-film-studio.md)).
- **Steps:**
  1. `PATCH S` `{"aiModel":G38}`; send each request below:
     - `POST /jobs/video-to-markdown` with F1 and `language=vi`
     - `POST /jobs/youtube-to-markdown` `{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}`
     - `POST /jobs/film-analysis` with F1; `POST /jobs/youtube-film-analysis` with V2
     - `POST /jobs/{A1}/film-analysis-rerun` `{}`
     - `POST /film-clones` with F1; `POST /film-clones/youtube` with V2
     - `POST /films/projects/{P1}/episodes` `{"source":"idea","idea":"A lighthouse keeper finds a message in a bottle."}`
  2. `curl -s 'http://localhost:5070/jobs?limit=200'`
  3. `PATCH S` `{"aiModel":CLI,"aiStepModels":{"filmClone":OA}}`; send `POST /jobs/video-to-markdown` with F1, then `POST /film-clones` with F1
- **Expected:**
  - Step 1: every request `HTTP 409`, `detail` = `Google AI (Gemini, Veo) is not set up — open Settings`
  - Step 2: no new job; no new clone or episode either
  - Step 3: the job `HTTP 201`; the clone `HTTP 409`, `detail` = `OpenAI is not set up — open Settings`

### TC-AIM-05: The AI line on the forms
- **App:** Frontend
- **Precondition:** A1 and P1 as in TC-AIM-04. `PATCH PV/google` `{"apiKey":"AIza-test-0000000000wxyz"}`.
- **Steps:**
  1. `PATCH S` `{"aiModel":CLI,"inputMode":"whole_video"}`; navigate to http://localhost:5071/
  2. `PATCH S` `{"aiStepModels":{"filmAnalysis":G4}}`; navigate to `/film-analysis`, then `/film-clone`, then `/film-analysis/{A1}`, then `/films/{P1}` and open `New episode`
  3. `PATCH S` `{"aiModel":OA,"aiStepModels":{}}` (no OpenAI key); reload `/`; drop F1 on `Video`
  4. Click `Change`
- **Expected:**
  - Step 1: above `Upload and convert`, the line `AI: Claude (CLI default) · Input: Whole video` with the link `Change`
  - Step 2: `New analysis`: `AI: Key moments — Claude (CLI default) · Film analysis — Gemini 4 Argon · Input: Whole video`; `New clone`: `AI: Claude (CLI default) · Input: Subtitles` — its `Input` reads `filmCloneInputMode`; `Rerun with another preset`: `AI: Gemini 4 Argon`; `Make a film` and `New episode`: `AI: Claude (CLI default)`
  - Step 3: the line reads `AI: GPT-6 Astra — not set up · Input: Whole video`; `Upload and convert` is disabled with the hint `Add the OpenAI key in Settings → General.`
  - Step 4: URL becomes `/settings?tab=ai-models`

### TC-AIM-06: Defaults — subtitles and the CLI default model
- **App:** API unit
- **Steps:**
  1. With `app_settings` empty, run a `video_to_markdown` job whose `options` have no `inputMode`, with a faked `claude` runner
  2. Run `writing_script` for an episode with the same empty settings
- **Expected:**
  1. The steps are those of 1.1 for `subtitles`; `picking_moments` calls `claude` once, its arguments have no `--model`; no Gemini or OpenAI request; `ai_used.picking_moments` = `CLI`
  2. The faked `claude` runner is called without `--model`; the episode's `ai_used` = `{"writing_script":CLI}`

## Calling a model

### TC-AIM-07: What a Gemini call sends
- **App:** API unit
- **Precondition:** Faked Gemini HTTP recording every request and answering in SSE chunks; `google` provider
  with key `AIza-test-0000000000wxyz`; `aiStepModels` = `{"moments":G4,"filmAnalysis":G4}`.
- **Steps:**
  1. Run `picking_moments` (`subtitles`) of a job with prompt `Pick P`
  2. Run `writing_character_image_prompts` of a job with prompt `Image P` and three 1280×720 frames
  3. Read the API log of both runs
- **Expected:**
  - Step 1: one `POST` to `…/v1beta/models/gemini-4-argon:streamGenerateContent?alt=sse`, header `x-goog-api-key` = the key; `systemInstruction` text = `Pick P`; `generationConfig.responseMimeType` = `application/json` with a `responseJsonSchema` of `title`, `summary`, `moments`; no `tools`; the user text holds `Choose at most 12 key moments` and the transcript lines
  - Step 2: `systemInstruction` = `Image P`; no `responseJsonSchema`; the user content has the notes text, then for each frame a text part `images/moment-…jpg` followed by an `inlineData` part `image/jpeg` of 480×270; the answer chunks `## Ch` + `aracter A` are stored as `## Character A`
  - Step 3: the key appears nowhere in the log

### TC-AIM-08: Gemini failures
- **App:** API unit
- **Steps:** with every group on `G38`, run a step whose faked Gemini:
  1. answers `HTTP 429` `{"error":{"message":"Resource has been exhausted"}}`
  2. answers `promptFeedback.blockReason` = `SAFETY` with no candidate
  3. answers a structured step with the text `Sure! Here are the moments`
  4. answers a Film Analysis pass with `   `
  5. answers `picking_moments` with a moment whose `atMs` is `"1:20"`
  6. stays silent for 5 s, `FILM_PROMPT_TIMEOUT_SEC` = 1
  7. stays silent for 5 s during `extracting_assets`, `CLONE_AI_SILENCE_SEC` = 0.3
  8. is never called: the `google` key is removed after the clone job is `done` and before `extracting_assets`
- **Expected:**
  1. `failed`, `error_message` = `gemini failed: Resource has been exhausted`; exactly one request sent — no retry
  2. `gemini returned no answer: SAFETY`
  3. `gemini returned output that is not JSON`
  4. `gemini returned an empty answer`
  5. `gemini returned a malformed moment: …`
  6. `gemini timed out after 1s`
  7. `gemini stopped responding for 0.3s`; the clone is `failed` at `extracting_assets`
  8. The clone is `failed` at `extracting_assets` with `Google AI (Gemini, Veo) is not set up — open Settings`; after the key is saved again, `resume` runs the step on Gemini and the clone reaches `choosing_localization`

### TC-AIM-09: Film Clone activity and the AI summary
- **App:** API unit + Frontend
- **Precondition:** `aiModel` = `CLI`, `aiStepModels.filmClone` = `G38`. A clone whose job finished on the
  faked `claude` and whose faked Gemini sends one chunk every 2 s during `extracting_assets`.
- **Steps:**
  1. `curl -s http://localhost:5070/film-clones/{id}` while the call runs
  2. Open `/film-clone/{id}`
- **Expected:**
  - Step 1: `aiActivity` = `{"provider":"google","model":"gemini-3.8-flash","label":"Gemini 3.8 Flash","startedAt":…,"lastOutputAt":…}`; `lastOutputAt` moves with each chunk; no `claudeActivity` key; `aiUsed` has `extracting_assets` and `job.aiUsed` has `picking_moments`
  - Step 2: the line reads `Gemini 3.8 Flash is working · {mm:ss} · last output {n}s ago`; the summary `AI` reads `Picking key moments: Claude (CLI default) · Extracting assets: Gemini 3.8 Flash`

## Whole video

### TC-AIM-10: Sampling one frame per second
- **App:** API unit
- **Steps:**
  1. Run `sampling_frames` on a 125.4 s 1920×1080 video
  2. Run it on a 360×640 video
  3. Run it with a faked `ffmpeg` exiting with `Invalid data found when processing input`
- **Expected:**
  1. 125 files `samples/sample-00000.jpg` … `sample-00124.jpg`, each 512×288
  2. Every sample is 360×640 — never upscaled
  3. `failed` at `sampling_frames`, `error_message` starts with `Frame sampling failed:`; `picking_moments` never starts

### TC-AIM-11: Windows and the moments asked of each
- **App:** API unit
- **Precondition:** A 250.0 s video with 250 samples; transcript lines at 5 s, 120 s, 130 s; none after
  200 s; `MAX_MOMENTS` = 12; faked runners recording each message and answering 5 moments per window, window 0
  with `title` `T0` and `summary` `S0`, the others with `T1` / `S1`.
- **Steps:**
  1. Run `picking_moments` (`whole_video`) of a Video to Markdown job with the `moments` model on `CLI`
  2. Run it with the `moments` model on `G38`
  3. Repeat step 2 with a reply naming `atMs` = 260000
  4. Run it with the `moments` model on `OA`
  5. Run it on `CLI` and change `aiStepModels.moments` to `G38` after the first window answers
- **Expected:**
  1. Three calls in time order. Messages: `This part of the video runs from 00:00 to 01:40. Choose at most 5 key moments in it.`, then `01:40 to 03:20 … at most 5`, then `03:20 to 04:10 … at most 3`; window 1 lists only `[5000ms]`, window 2 lists `[120000ms]` and `[130000ms]`, window 3 reads `(no speech in this part)`; each call carries its 100, 100 and 50 frames, each after `[{ms}ms]`. Kept: 12 moments in time order; title `T0`, summary `S0`
  2. One call — `00:00 to 04:10`, `at most 12`, all 250 frames
  3. That moment is kept at 249500 ms
  4. One OpenAI call with all 250 frames
  5. All three windows go to the faked `claude`; `ai_used.picking_moments` = `CLI`

### TC-AIM-12: Step order and clean-up
- **App:** API unit
- **Steps:** with `inputMode` = `whole_video` and faked tools:
  1. Run a `video_to_markdown` job
  2. Run a `youtube_film_analysis` job
  3. Run a `video_to_markdown` job whose second of three windows fails with `claude failed: Overloaded`
  4. Run a `video_to_markdown` job whose whisper output has no segment
  5. Requeue a job stopped during `picking_moments`, then let it run
- **Expected:**
  1. Steps `extracting_audio`, `transcribing`, `sampling_frames`, `picking_moments`, `capturing_frames`, `writing_markdown`; `samples/` gone before `capturing_frames` starts; `output/images/` holds only the captured moments
  2. Steps `fetching_transcript`, `downloading_video`, `sampling_frames`, `picking_moments`, `detecting_scenes`, `capturing_frames`, `writing_markdown`, then the three prompt passes; `downloading_video` runs once
  3. `failed` at `picking_moments`, `error_message` = `claude failed: Overloaded`; no moment saved; the third window is never called; `samples/` gone
  4. `failed` at `transcribing` with `No speech was detected in the video`; `sampling_frames` never starts
  5. Samples left by the stopped run are removed before sampling starts again; the run writes each sample once

### TC-AIM-13: Whole video with Claude, upload end to end
- **App:** Frontend
- **Precondition:** `PATCH S` `{"aiModel":CLI,"aiStepModels":{},"inputMode":"whole_video"}`; whisper model present.
- **Steps:**
  1. Navigate to http://localhost:5071/; drop F1 on `Video`; select `Vietnamese`; click `Upload and convert`
  2. Watch the step list until `done`
  3. List `api/storage-test/{id}/`
- **Expected:**
  - Step 1: URL becomes `/jobs/{id}`; summary `AI` = `—`, `Input` = `Whole video`
  - Step 2: steps in the order of TC-AIM-12 step 1, `Sampling frames` among them; summary `AI` = `Picking key moments: Claude (CLI default)`; the result shows a title, a summary and at most 12 moments, each with its frame and transcript
  - Step 3: no `samples/` folder; `output/` and `result.zip` exist

### TC-AIM-14: Gemini film analysis, end to end (live, spends credit)
- **App:** Frontend
- **Precondition:** A working Google AI key saved on the `Google AI (Gemini, Veo)` sub-tab of `General`; `PATCH S`
  `{"aiModel":G38,"aiStepModels":{},"inputMode":"whole_video"}`. Remove the key after the case.
- **Steps:**
  1. Navigate to http://localhost:5071/film-analysis; switch to `YouTube link`; fill V2's link; select `English`; fill `Max frames` with `20`; click `Analyze`
  2. Wait for `done`
  3. Open each result tab
- **Expected:**
  - Step 1: the form line reads `AI: Gemini 3.8 Flash · Input: Whole video`; URL becomes `/film-analysis/{id}`
  - Step 2: steps `Fetching YouTube transcript`, `Downloading video`, `Sampling frames`, `Picking key moments`, `Detecting scene changes`, `Capturing frames`, `Writing Markdown`, then the three prompt passes; summary `AI` lists `Picking key moments` and the three passes, each `Gemini 3.8 Flash`; `Input` = `Whole video`; `Frames` shows at most 10 dialogue frames
  - Step 3: `Character image prompts`, `Character voice prompts`, `Scene prompts` and `Video notes` all have content, each `##` heading per character or shot

## Model catalog

### TC-AIM-15: The analysis catalog
- **App:** Frontend + API
- **Steps:**
  1. `curl -s PV`
  2. Navigate to http://localhost:5071/settings?tab=ai-models; look at `All steps` and at the Google AI and OpenAI rows of `Images`, `Clips` and `Speech`
  3. Navigate to http://localhost:5071/settings?tab=general&provider=google; click sub-tab `OpenAI`
  4. `curl -i -X PATCH S/ai-models -H 'Content-Type: application/json' -d '{"models":{"google":{"analysis":"gemini-4-argon"}}}'`
  5. `PATCH S/ai-models` `{"models":{"openai":{"analysis":"gpt-6-astra"}}}`
- **Expected:**
  1. `catalog.analysis` — `claude_cli`: `default` (`isDefault`), `fable`, `opus`, `sonnet`, `haiku`; `google`: `gemini-4-argon` (`isDefault`), `gemini-3.8-flash`, `gemini-3.5-flash-lite`; `openai`: `gpt-6-astra` (`isDefault`), `gpt-6.1-sol`, `gpt-6-luna`; `mediaKinds` of `openai` includes `analysis`
  2. `All steps` lists the `analysis` models under `Claude CLI`, `Google AI`, `OpenAI`; the Google AI and OpenAI rows of the media groups offer only `Image model`, `Image edit model`, `Clip model` and `Speech model`, none of them an `analysis` model
  3. Neither sub-tab has a model select; their queue lines count only generation requests
  4. `HTTP 400`, `detail` = `models.analysis does not apply to Google AI (Gemini, Veo)`
  5. `HTTP 400`, `detail` = `models.analysis does not apply to OpenAI`

## Settings — more

### TC-AIM-16: Apply to all steps
- **App:** Frontend + API
- **Precondition:** `PATCH S` `{"aiModel":CLI,"aiStepModels":{"moments":G38,"filmClone":OA}}`.
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=ai-models
  2. Click `Apply to all steps`
  3. Click `Save`; `curl -s S`
  4. Navigate away and back
- **Expected:**
  - Step 1: `Key moments` = `Gemini 3.8 Flash`, `Film clone` = `GPT-6 Astra`, the other two `Same as all steps (Claude (CLI default))`; `Apply to all steps` enabled
  - Step 2: all four rows read `Same as all steps (Claude (CLI default))`; `Apply to all steps` disabled; `Save` enabled; nothing saved yet
  - Step 3: notice `Saved`; `aiStepModels` = `{"moments":null,"filmAnalysis":null,"filmScript":null,"filmClone":null}`; `aiModel` unchanged
  - Step 4: the rows keep `Same as all steps`

### TC-AIM-23: Film Clone copies filmCloneInputMode, the other jobs inputMode
- **App:** API
- **Precondition:** `PATCH S` `{"inputMode":"subtitles","filmCloneInputMode":"whole_video"}`.
- **Steps:**
  1. `curl -i -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}'`
  2. `curl -i -X POST http://localhost:5070/jobs/youtube-film-analysis -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}'`
  3. `curl -i -X POST http://localhost:5070/film-clones/youtube -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}'`; `curl -s http://localhost:5070/film-clones/{id}`
  4. `PATCH S` `{"inputMode":"whole_video","filmCloneInputMode":"subtitles"}`; `curl -s http://localhost:5070/jobs/{id}` for the jobs of steps 1 and 2 and the stage 1 job of step 3
- **Expected:**
  - Step 1: `HTTP 201`; `options.inputMode` = `subtitles`
  - Step 2: `HTTP 201`; `options.inputMode` = `subtitles`
  - Step 3: `HTTP 201`; `job.options.inputMode` = `whole_video`
  - Step 4: the jobs keep `subtitles`, `subtitles` and `whole_video`

### TC-AIM-24: The Input line of New clone and its own Change link
- **App:** Frontend + API
- **Precondition:** `PATCH S` `{"aiModel":CLI,"aiStepModels":{},"inputMode":"subtitles","filmCloneInputMode":"whole_video"}`.
- **Steps:**
  1. Navigate to http://localhost:5071/film-clone
  2. Navigate to http://localhost:5071/film-analysis
  3. Navigate to http://localhost:5071/film-clone; click the `Change` right after `Input: Whole video`
  4. Select `Subtitles` from `Input mode`; click `Save`; navigate to http://localhost:5071/film-clone; `curl -s S`
  5. Click the `Change` of the AI models
- **Expected:**
  - Step 1: `New clone` reads `AI: Claude (CLI default) · Input: Whole video`, with a link `Change` for the AI models and its own link `Change` right after `Input: Whole video`
  - Step 2: `New analysis` reads `AI: Claude (CLI default) · Input: Subtitles` with one link `Change`
  - Step 3: URL becomes `/settings?tab=film-clone`; tab `Film Clone` open with `Input mode` = `Whole video`
  - Step 4: notice `Saved`; `New clone` reads `AI: Claude (CLI default) · Input: Subtitles`; body has `"inputMode":"subtitles"`, `"filmCloneInputMode":"subtitles"`
  - Step 5: URL becomes `/settings?tab=ai-models`

## Calling a model — more

### TC-AIM-17: What an OpenAI call sends
- **App:** API unit
- **Precondition:** Faked OpenAI HTTP recording every request and answering in SSE events; `openai` provider
  with key `sk-test-0000000000wxyz`; `aiStepModels` = `{"moments":OA,"filmAnalysis":OA}`.
- **Steps:**
  1. Run `picking_moments` (`subtitles`) of a job with prompt `Pick P`
  2. Run `writing_character_image_prompts` of a job with prompt `Image P` and three 1280×720 frames; the fake sends `response.output_text.delta` `## Ch`, then `aracter A`, then `response.completed`
  3. Read the API log of both runs
- **Expected:**
  - Step 1: one `POST` to `https://api.openai.com/v1/responses`, header `Authorization: Bearer sk-test-0000000000wxyz`; body `model` = `gpt-6-astra`, `stream` = `true`, `store` = `false`, no `tools`, `instructions` = `Pick P`, `text.format` = `{"type":"json_schema","name":"reply","schema":…,"strict":false}` with `title`, `summary`, `moments`; one `user` input whose `input_text` holds `Choose at most 12 key moments`
  - Step 2: no `text.format`; the content has the notes as `input_text`, then for each frame an `input_text` `images/moment-…jpg` and an `input_image` whose `data:image/jpeg;base64,…` URL decodes to 480×270; stored answer `## Character A`
  - Step 3: the key appears nowhere in the log

### TC-AIM-18: OpenAI failures
- **App:** API unit
- **Steps:** with every group on `OA`, run a step whose faked OpenAI:
  1. answers `HTTP 429` `{"error":{"message":"Rate limit reached for gpt-6-astra"}}`
  2. streams a `response.failed` event with error message `The server had an error`
  3. streams `response.incomplete` with `incomplete_details.reason` = `content_filter` and no text
  4. answers a structured step with the text `Here you go`
  5. stays silent for 5 s during `analyzing_shots`, `CLONE_AI_SILENCE_SEC` = 0.3
- **Expected:**
  1. `failed`, `error_message` = `openai failed: Rate limit reached for gpt-6-astra`; exactly one request sent — no retry
  2. `openai failed: The server had an error`
  3. `openai returned no answer: content_filter`
  4. `openai returned output that is not JSON`
  5. `openai stopped responding for 0.3s`; the clone is `failed` at `analyzing_shots`

### TC-AIM-19: Images scaled for every provider; Gemini over 20 MB
- **App:** API unit
- **Steps:**
  1. Run `writing_scene_prompts` on `CLI` with frames of 1280×720, 720×1280 and 300×200
  2. Look at the frames on disk after step 1
  3. Run `analyzing_shots` on `CLI` and on `OA` with the same frames
  4. With `AI_IMAGE_MAX_SIDE_PX` = 4000 and `AI_IMAGE_JPEG_QUALITY` = 100, run `writing_scene_prompts` on `G38` with 100 frames of 3840×2160 random noise
- **Expected:**
  1. The stream-json images decode to 480×270, 270×480 and 300×200, all JPEG
  2. Unchanged — 1280×720, 720×1280 and 300×200
  3. The same three sizes reach `claude` and OpenAI
  4. `failed`, `error_message` = `gemini takes at most 20 MB per call; this call is {n} MB — lower Max frames or pick another model` with `{n}` > 20.0; the faked Gemini receives no request

### TC-AIM-20: The Claude model comes from the settings
- **App:** API unit
- **Steps:**
  1. `aiModel` = `CLI`, `aiStepModels.filmScript` = `{"provider":"claude_cli","model":"opus"}`; run `writing_script` of an episode, then `picking_moments` of a job
  2. `aiModel` = `{"provider":"claude_cli","model":"haiku"}`, `aiStepModels` = `{}`; run `picking_moments` again
- **Expected:**
  1. `writing_script` runs `claude` with `--model opus`; `picking_moments` runs it without `--model`
  2. `claude` runs with `--model haiku`; `ai_used.picking_moments` = `{"provider":"claude_cli","model":"haiku"}`

### TC-AIM-21: Switching the model and resuming
- **App:** API unit
- **Precondition:** `aiStepModels.filmClone` = `G38`; `openai` provider with key `sk-test-0000000000wxyz`.
- **Steps:**
  1. Run a clone to `analyzing_shots`, the faked Gemini answering `HTTP 503` `{"error":{"message":"The model is overloaded"}}`
  2. `PATCH S` `{"aiStepModels":{"filmClone":OA}}`; `POST /film-clones/{id}/resume`
- **Expected:**
  1. The clone is `failed` at `analyzing_shots`, `gemini failed: The model is overloaded`; `ai_used.analyzing_shots` = `G38`
  2. The step runs on the faked OpenAI, the clone reaches `choosing_localization`; `ai_used.analyzing_shots` = `OA`, `ai_used.extracting_assets` still `G38`

### TC-AIM-22: The AI line on detail screens
- **App:** Frontend
- **Precondition:** `PATCH S` `{"aiModel":CLI,"aiStepModels":{},"inputMode":"subtitles"}`. A Film Studio
  project P1 as in TC-AIM-04.
- **Steps:**
  1. Run a Film Analysis on F1 with `Max frames` = `10` until `done`; open `/film-analysis/{id}`
  2. Open `/films/{P1}`; create an episode from the idea `A lighthouse keeper finds a message in a bottle.` with stop point after the script; wait until it pauses
- **Expected:**
  - Step 1: summary `AI` = `Picking key moments: Claude (CLI default) · Writing character image prompts: Claude (CLI default) · Writing character voice prompts: Claude (CLI default) · Writing scene prompts: Claude (CLI default)` — the step labels of 3.6
  - Step 2: the episode's `Script` panel shows `AI` = `Claude (CLI default)`
