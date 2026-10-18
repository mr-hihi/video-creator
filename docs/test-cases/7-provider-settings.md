## 7. Nhà cung cấp media (Provider Settings) (7-provider-settings.md)

Test cases for [business/7-provider-settings.md](../business/7-provider-settings.md). Acronym `PS`.

## Test environment

- Stack, captcha switch and app labels: as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- Start from a fresh test DB. `api/.env.test` sets `SETTINGS_SECRET_KEY` to a fixed test key and
  `FLOW_WS_PORT=5074` unless a case says otherwise; restart the test stack after changing them.
- Shorthand: `S` = `http://localhost:5070/settings`, `PV` = `http://localhost:5070/settings/providers`.
- No case spends credit: **API unit** cases fake every provider's HTTP, the extension and the local servers;
  API and Frontend cases use test keys that the providers refuse.
- Fixtures: those of [4-film-studio.md § Test environment](./4-film-studio.md#test-environment).

---

## Providers & keys

### TC-PS-01: Provider sub-tabs of the General tab on a fresh install
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=general
  2. Click each sub-tab of the panel `Providers` in turn
  3. Click sub-tab `Google Flow`; click `AI models` in the line `Pick its models in AI models.`
  4. Navigate to http://localhost:5071/settings?tab=general&provider=claude_cli
- **Expected:**
  - Step 1: below `Script language` and its `Save`, the panel `Providers` with eleven sub-tabs in the order Google Flow, Google AI (Gemini, Veo), fal.ai, Replicate, OpenAI, ElevenLabs, Stable Diffusion WebUI / Forge, OmniVoice, ACE-Step, YuE, Claude CLI; `Google Flow` selected: badge `Extension`, status `Connected` or `Not connected`, the line `Queued 0 · Running 0 · Failed (24 h) 0`, a `Fallback Flow project id` field, `Open Flow tab`, `Concurrent requests` = 5, `Seconds between requests` = 10, the line `Pick its models in AI models.`, `Save` disabled and `Test connection`; no key or URL field
  - Step 2: no sub-tab has a model select; each shows the line `Pick its models in AI models.`
  - Step 2, the five `API` sub-tabs: badge `API`, `Not set up`, an `API key` field, the line `Queued 0 · Running 0 · Failed (24 h) 0`, `Concurrent requests` = 2, `Seconds between requests` = 0
  - Step 2, the four `Local` sub-tabs: badge `Local`, `Not set up`, a `Base URL` field, the line `Queued 0 · Running 0 · Failed (24 h) 0`, `Concurrent requests` = 1, `Seconds between requests` = 0; OmniVoice, ACE-Step and YuE show the hint `Run the adapter of tools/local-servers/ and enter its address.`
  - Step 2, Claude CLI: badge `CLI`, status `Signed in` (the test machine's CLI is signed in), only the `Test connection` button — no key, URL, queue or pacing field and no `Save`
  - Step 3: URL becomes `/settings?tab=ai-models`; tab `AI models` open
  - Step 4: tab `General` open with sub-tab `Claude CLI` selected

### TC-PS-02: Save and remove an API key
- **App:** Frontend + API
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=general&provider=openai; fill `API key` with `sk-test-0000000000abcd`; click `Save`
  2. `curl -s PV`
  3. Query `SELECT api_key_encrypted, api_key_last4 FROM providers WHERE id = 'openai'` on `video_tool_test`
  4. Click `Remove key`; click `OK`
- **Expected:**
  - Step 1: notice `Saved`; status `Ready`; the field is empty with placeholder `••••abcd`
  - Step 2: OpenAI has `hasKey` = `true`, `apiKeyLast4` = `abcd`, `setUp` = `true`; the body contains no `sk-test-0000000000abcd`
  - Step 3: `api_key_encrypted` is not the plain key and does not contain it; `api_key_last4` = `abcd`
  - Step 4: dialog `Remove the API key of OpenAI?`; status `Not set up`; `hasKey` = `false`

### TC-PS-03: Field validation
- **App:** API
- **Steps:** `curl -i -X PATCH {url} -H 'Content-Type: application/json' -d '{body}'`, `{url}` = `PV/{id}`, or
  `S/ai-models` where the step names it:
  1. `sd_webui`, `{"apiKey":"abc"}`
  2. `sd_webui`, `{"baseUrl":"localhost:7860"}`
  3. `S/ai-models`, `{"models":{"openai":{"video":"sora-2"}}}`
  4. `fal`, `{"apiKey":"   "}`
  5. `fal`, `{"maxConcurrent":0}`, then `{"maxConcurrent":11}`
  6. `fal`, `{"minIntervalS":601}`
  7. `S/ai-models`, `{"models":{"openai":{"image":"gpt-image-9"}}}`
  8. `midjourney`, `{"apiKey":"abc"}`
  9. `S/ai-models`, `{"models":{"sd_webui":{"image":"flux1-dev"}}}`
  10. `google_flow`, `{"flowProjectId":"not-a-uuid"}`; then `fal`, `{"flowProjectId":"594758cc-0000-4000-8000-000000000000"}`
  11. `sd_webui`, `{"baseUrl":"http://127.0.0.1:7860","maxConcurrent":1}`
  12. `S/ai-models`, `{"models":{"replicate":{"video":"minimax/hailuo-2.3"}}}`
  13. `S/ai-models`, `{"models":{"midjourney":{"image":"mj-7"}}}`
- **Expected:**
  1. `HTTP 400`, `detail` = `apiKey does not apply to Stable Diffusion WebUI / Forge`
  2. `HTTP 400`, `detail` = `Base URL must start with http:// or https://`
  3. `HTTP 400`, `detail` = `models.video does not apply to OpenAI`
  4. `HTTP 400`, `detail` = `API key must be 1-500 characters`
  5. `HTTP 400`, `detail` = `Concurrent requests must be between 1 and 10`, both
  6. `HTTP 400`, `detail` = `Interval must be between 0 and 600 seconds`
  7. `HTTP 400`, `detail` = `Unknown model 'gpt-image-9' for OpenAI image`
  8. `HTTP 404`, `detail` = `Provider midjourney not found`
  9. `HTTP 400`, `detail` = `models does not apply to Stable Diffusion WebUI / Forge`
  10. `HTTP 400`, `detail` = `Flow project id must be a UUID`; then `HTTP 400`, `detail` = `flowProjectId does not apply to fal.ai`
  11. `HTTP 200`, `setUp` = `true`
  12. `HTTP 200`; in `providers.providers`, `replicate` has `models.video` = `minimax/hailuo-2.3`
  13. `HTTP 404`, `detail` = `Provider midjourney not found`

### TC-PS-04: No secret key
- **App:** Frontend + API
- **Precondition:** `SETTINGS_SECRET_KEY=` (empty) in `api/.env.test`; test stack restarted. Set it back afterwards.
- **Steps:**
  1. `curl -i -X PATCH PV/openai -H 'Content-Type: application/json' -d '{"apiKey":"sk-test-0000000000abcd"}'`
  2. `curl -s PV`
  3. Navigate to http://localhost:5071/settings?tab=general
  4. Click in turn the sub-tabs `Google AI (Gemini, Veo)`, `fal.ai`, `Replicate`, `OpenAI`, `ElevenLabs`, then `Stable Diffusion WebUI / Forge`
- **Expected:**
  1. `HTTP 409`, `detail` = `Set SETTINGS_SECRET_KEY in api/.env before saving API keys`
  2. `secretKeySet` = `false`
  3. Notice `Set SETTINGS_SECRET_KEY in api/.env to save API keys.` above the sub-tabs
  4. The notice stays above the sub-tabs; the `API key` field is disabled on each of the five `API` sub-tabs; the `Base URL` field of Stable Diffusion WebUI / Forge is enabled

### TC-PS-05: A key the new secret cannot read
- **App:** API unit
- **Steps:**
  1. Save a key for `fal` with secret A; switch to secret B; read the providers
  2. Save a new key for `fal` with secret B
- **Expected:**
  1. `fal`: `keyUnreadable` = `true`, `setUp` = `false`; a `fal` request at submit is `failed` with `fal.ai is not set up — open Settings`
  2. `keyUnreadable` = `false`, `setUp` = `true`

### TC-PS-26: Unsaved changes when switching sub-tab
- **App:** Frontend + API
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=general&provider=fal; fill `Concurrent requests` with `4`
  2. Click sub-tab `Replicate`; click `Cancel`
  3. Click sub-tab `Replicate`; click `OK`
  4. Click sub-tab `fal.ai`; `curl -s PV`
  5. Click sub-tab `OpenAI`
- **Expected:**
  - Step 1: sub-tab `fal.ai` selected; `Save` enabled
  - Steps 2 and 3: dialog `Discard unsaved changes?`; after `Cancel` sub-tab `fal.ai` stays selected with `Concurrent requests` = 4
  - Step 3: sub-tab `Replicate` opens
  - Step 4: `Concurrent requests` = 2; `Save` disabled; `fal` has `maxConcurrent` = 2
  - Step 5: no dialog; sub-tab `OpenAI` opens

## Routing

### TC-PS-06: Routing choices
- **App:** API + Frontend
- **Steps:**
  1. `curl -i -X PATCH S/ai-models -H 'Content-Type: application/json' -d '{"routes":{"image":"sd_webui","speech":"elevenlabs","music":"yue"}}'`
  2. `PATCH S/ai-models` `{"routes":{"video":"openai"}}`
  3. `PATCH S/ai-models` `{"routes":{"speech":"fal"}}`
  4. `PATCH S/ai-models` `{"routes":{"analysis":"google"}}`
  5. `PATCH S/ai-models` `{"routes":{"video":"sd_webui"}}`
  6. Navigate to http://localhost:5071/settings?tab=ai-models
- **Expected:**
  1. `HTTP 200`, `providers.routes` = `{"image":"sd_webui","video":"google_flow","speech":"elevenlabs","music":"yue"}`
  2. `HTTP 400`, `detail` = `OpenAI cannot serve video`
  3. `HTTP 400`, `detail` = `fal.ai cannot serve speech`
  4. `HTTP 400`, `detail` = `Unknown route 'analysis'`
  5. `HTTP 400`, `detail` = `Stable Diffusion WebUI / Forge cannot serve video`
  6. `Images` = `Stable Diffusion WebUI / Forge`, `Clips` = `Google Flow`, `Speech` = `ElevenLabs`, `Music` = `YuE`

### TC-PS-07: Which provider a request gets
- **App:** API unit
- **Precondition:** Routes `image` = `fal`, `video` = `google_flow`, `speech` = `omnivoice`, `music` = `ace_step`;
  settings `filmStudioImageProvider`, `filmStudioClipProvider` and `filmCloneImageProvider` = `null`; a project A
  and a film clone.
- **Steps:**
  1. Queue a `scene_image` in A, a `clone_scene_image` for the clone, a `scene_clip`, a `narration` and a `music` request
  2. Set `filmStudioImageProvider` = `sd_webui`; queue another `scene_image` in A and another `clone_scene_image`
  3. Set `filmStudioImageProvider` = `null`, `filmStudioClipProvider` = `replicate`, `filmCloneImageProvider` =
     `google`, the `image` route = `openai` and the `speech` route = `google`; queue another `scene_image` in A,
     `clone_scene_image`, `scene_clip` and `narration`
- **Expected:**
  1. `provider` = `fal`, `fal`, `google_flow`, `omnivoice`, `ace_step`
  2. The new `scene_image` gets `sd_webui`, the new `clone_scene_image` `fal`; the earlier ones keep theirs
  3. The new requests get `openai`, `google`, `replicate` and `google`; every request of steps 1 and 2 keeps its provider

### TC-PS-27: Media groups of the AI models tab on a fresh install
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=ai-models
  2. Click `General` in the line `Not set up — set it up in General.` of the fal.ai row of `Images`
- **Expected:**
  - Step 1: after the group `Text`, the groups `Images`, `Clips`, `Speech`, `Music`; `Save` disabled
  - Step 1, `Images`: select `Images` = `Google Flow`, options `Google Flow`, `Google AI`, `fal.ai`, `Replicate`, `OpenAI`, `Stable Diffusion WebUI / Forge`, hint `Film Clone and Film Studio use it unless they pick their own.`; rows in that order: Google Flow `Image model` = `Nano Banana Pro`, `Image edit model` = `Nano Banana Pro`; Google AI `Nano Banana 2.1`, `Nano Banana 2.1`; fal.ai `Nano Banana Pro`, `Nano Banana Pro edit`; Replicate `Nano Banana Pro`, `Nano Banana Pro`; OpenAI `GPT Image 2.5`, `GPT Image 2.5`; Stable Diffusion WebUI / Forge the line `Uses the model loaded in the server.` and no select
  - Step 1, `Clips`: select `Clips` = `Google Flow`, options `Google Flow`, `Google AI`, `fal.ai`, `Replicate`, hint `Film Studio uses it unless it picks its own.`; rows: Google Flow `Clip model` = `Veo 3.1 Lite`, Google AI `Veo 3.1 Lite`, fal.ai `Kling 3 Pro`, Replicate `Kling 3`
  - Step 1, `Speech`: select `Speech` = `OmniVoice`, options `OmniVoice`, `ElevenLabs`, `Google AI`; rows: OmniVoice the line `Uses the model loaded in the server.`, ElevenLabs `Speech model` = `Eleven v4`, Google AI `Speech model` = `Gemini 3.8 Flash TTS`
  - Step 1, `Music`: select `Music` = `ACE-Step`, options `ACE-Step`, `ElevenLabs`, `YuE`; rows: ACE-Step the line `Uses the model loaded in the server.`, ElevenLabs `Music model` = `Music v2.5`, YuE the line `Uses the model loaded in the server.`
  - Step 1: badge `In use` only on Google Flow in `Images`, Google Flow in `Clips`, OmniVoice in `Speech` and ACE-Step in `Music`; every row but the two Google Flow rows shows `Not set up — set it up in General.`
  - Step 2: URL becomes `/settings?tab=general&provider=fal`; tab `General` open with sub-tab `fal.ai` selected

### TC-PS-28: The In use badge follows the saved route and the Film Clone and Film Studio picks
- **App:** Frontend + API
- **Steps:**
  1. `curl -i -X PATCH S -H 'Content-Type: application/json' -d '{"filmStudioImageProvider":"sd_webui","filmCloneImageProvider":"openai","filmStudioClipProvider":"replicate"}'`; navigate to http://localhost:5071/settings?tab=ai-models
  2. `PATCH S` `{"filmStudioImageProvider":"google_flow","filmCloneImageProvider":null,"filmStudioClipProvider":null}`; reload the page
- **Expected:**
  - Step 1: `HTTP 200`; selects `Images` = `Google Flow`, `Clips` = `Google Flow`; badge `In use` on Google Flow, OpenAI and Stable Diffusion WebUI / Forge in `Images`, on Google Flow and Replicate in `Clips`, on OmniVoice in `Speech`, on ACE-Step in `Music`, and on no other row
  - Step 2: `In use` on Google Flow only in `Images` and in `Clips`

### TC-PS-29: One Save for routes and models
- **App:** Frontend + API
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=ai-models
  2. Select `Replicate` from `Clips`; on the Replicate row of `Clips` select `Wan 3` from `Clip model`; on the Google Flow row of `Images` select `Nano Banana 2` from `Image model`; select `ElevenLabs` from `Speech`
  3. Click `Save`
  4. Reload the page; `curl -s PV`
- **Expected:**
  - Step 2: `Save` enabled; `In use` still on Google Flow in `Clips` and OmniVoice in `Speech`
  - Step 3: notice `Saved`; the browser sends one `PATCH /settings/ai-models` and no `PATCH /settings/providers/…`; `Save` disabled; `In use` on Replicate in `Clips` and ElevenLabs in `Speech`
  - Step 4: the selections of step 2; `routes` = `{"image":"google_flow","video":"replicate","speech":"elevenlabs","music":"ace_step"}`; `replicate` has `models.video` = `alibaba/wan-3`, `google_flow` has `models.image` = `NARWHAL`

## Submit

### TC-PS-08: Values read at submit
- **App:** API unit
- **Precondition:** `replicate` set up with model `image` = `google/nano-banana-pro`, `max_concurrent` = 2, `min_interval_s` = 5; two `replicate` requests R1, R2 queued.
- **Steps:**
  1. Before the worker runs, set `replicate` model `image` = `bytedance/seedream-4.5`
  2. Run the worker
- **Expected:**
  - Both submits use `bytedance/seedream-4.5`
  - R2 is submitted at least 5 s after R1, although a second slot is free

### TC-PS-09: Provider not set up at submit
- **App:** API unit
- **Steps:**
  1. Queue a `scene_image` request for `openai` with no key; run the worker
  2. Queue a `narration` request with `omnivoice` `base_url` empty; run the worker
- **Expected:**
  1. `failed` at once, `error_message` = `OpenAI is not set up — open Settings`; no HTTP call made
  2. `failed` at once, `error_message` = `OmniVoice is not set up — open Settings`

## Test & keys

### TC-PS-10: Test connection
- **App:** API unit + API
- **Steps:**
  1. *(API unit)* `test` `google` whose faked model list answers 401 `API key not valid`
  2. *(API unit)* `test` `sd_webui` whose `/sdapi/v1/sd-models` answers 200
  3. `curl -s -X POST PV/elevenlabs/test` with no key
  4. *(API unit)* `test` `google_flow` with the extension disconnected
- **Expected:**
  1. `{ "ok": false, "error": "API key not valid", "testedAt": … }`; `lastTest` stored; no generation call made
  2. `ok` = `true`
  3. `HTTP 200`, `ok` = `false`, `error` = `Not set up`
  4. `ok` = `false`

### TC-PS-11: Keys never leak
- **App:** API unit
- **Precondition:** `fal` key `fal-test-SECRET-9999`; faked `fal` answers a submit with an error body that echoes the request headers.
- **Steps:**
  1. Run a `fal` request until it is `failed`; read its row, the API log and `GET PV`
- **Expected:**
  - `fal-test-SECRET-9999` appears in none of `error_message`, `prompt`, `params`, `input_paths`, the log lines or the response body

## Model checks

### TC-PS-12: Clip length planned from the model's lengths
- **App:** API unit
- **Precondition:** `filmStudioClipProvider` = `null`; the `video` route = `google_flow` unless a row names
  another; Google Flow connected; every faked provider answers a clip with a test pattern as long as it was
  asked for.
- **Steps:** for each row, queue a `scene_clip` of a scene whose `clip_duration_s` is L; run the worker:
  1. L 6, Google Flow `veo_3_1_i2v_lite`
  2. L 6, Google Flow Omni Flash
  3. L 30, Google Flow `veo_3_1_i2v_lite`
  4. L 30, the `video` route = `google`, model `veo-3.1-generate-preview`
  5. L 30, Google Flow Omni Flash
  6. L 10, the `video` route = `google`, model `veo-3.1-fast-generate-preview`
  7. L 9, the `video` route = `replicate`, model `minimax/hailuo-2.3`
- **Expected:**
  1. One submit of 8 s; `clip.mp4` cut to 6 s (`clipDurationMs` 6000); `params` has no `segments`
  2. One submit with the Flow model `abra_i2v_6s`; the clip is not cut
  3. `params.segmentLengths` = `[8, 8, 8, 8, 8]`, `params.segments` = 5; `clipDurationMs` 30000
  4. `params.segmentLengths` = `[8, 8, 8, 8, 4]`; `clipDurationMs` 30000
  5. Flow models `abra_i2v_10s` three times, then `abra_i2v_4s`; `params.segmentLengths` = `[10, 10, 10, 4]`
  6. `params.segmentLengths` = `[8, 4]`; `clipDurationMs` 10000
  7. One submit of 10 s; cut to 9 s
  - No request is refused for its length

### TC-PS-13: More references than the model takes
- **App:** API unit
- **Precondition:** A scene listing six characters A–F, each reference `done`.
- **Steps:**
  1. `generate-image` with `filmStudioImageProvider` = `openai`; run the worker
  2. `generate-image` with `filmStudioImageProvider` = `sd_webui`; run the worker
  3. `generate-image` with `filmStudioImageProvider` = `sd_webui` on a scene listing no character
  4. Step 1 again, the provider failing pass 3 once
- **Expected:**
  1. Six OpenAI calls in order: pass 1 an image call with A's reference only; passes 2–6 edit calls on the previous result, each with one reference (B, C, D, E, F) and the prompt `Keep the scene, the framing and everyone else unchanged. Make {name} look like the reference image.`; `params.passes` = 6; the scene image is the result of pass 6
  2. One `POST /sdapi/v1/img2img`: init image = a 1344×768 composite (grey base — no location in the scene — with A–F side by side), `denoising_strength` = 0.75; no pass
  3. `POST /sdapi/v1/txt2img`
  4. Pass 3 fails with `Internal error` once: the retry starts again at pass 3, with the result of pass 2

### TC-PS-23: Segments start from the last frame of the one before
- **App:** API unit
- **Precondition:** Google Flow video model `veo_3_1_i2v_lite`, `max_concurrent` 1; scene S1 of
  `clip_duration_s` 22 with its image `done`; the faked extension stamps each clip's frames with a frame
  counter. R1 = `generate-clip` on S1; R2 = a `scene_clip` of another scene, queued after R1.
- **Steps:**
  1. Run the worker until R1 is `done`, reading R1 after each segment
- **Expected:**
  - Three submits for R1: segment 1 with S1's image as start frame; segments 2 and 3 with
    `clip-segments/1-last.png` and `clip-segments/2-last.png`, each the last frame of the segment before
  - Their prompts start with `Part 1 of 3. Show 0-8s of this shot.`, then `Part 2 of 3. Show 8-15s of this
    shot. Continue from the start image.`, then `Part 3 of 3. Show 15-22s of this shot. Continue from the
    start image.`; each goes on with the clip prompt of 4.3
  - `params.segment` reads 1, 2, 3; `params.segments` = 3; `externalId` changes with each segment
  - R2 is not submitted before R1 is `done`; the three submits are at least 3 s apart (7.7)
  - `clip.mp4` is 22 s (`clipDurationMs` 22000); segments 2 and 3 enter it from their frame at 1 s;
    `clip-segments/` is deleted

### TC-PS-24: A failure keeps the segments made
- **App:** API unit
- **Precondition:** S1 of TC-PS-23 without a clip; `FILM_REQUEST_MAX_ATTEMPTS` 5. Steps 1 and 2 start from S1
  without a clip; steps 3–5 each follow step 2.
- **Steps:**
  1. `generate-clip`; segment 2 answers `503` once; run the worker
  2. `generate-clip`; segment 3 is blocked by the content filter; run the worker
  3. `generate-clip` again with nothing changed; run the worker
  4. `PATCH F/scenes/{S1}` `{"clipDurationS":15}`; `generate-clip`; run the worker
  5. Set the Google Flow video model to Omni Flash; `generate-clip`; run the worker
- **Expected:**
  1. Segment 1 is submitted once, segment 2 twice; the request ends `done`
  2. `failed` with the content-filter message; `clipStatus` = `failed`; `clip-segments/` holds `1.mp4`,
     `1-last.png`, `2.mp4` and `2-last.png`
  3. One submit — segment 3, from `2-last.png`; `done`, `clipDurationMs` 22000
  4. `clip-segments/` is deleted first; submits start at segment 1; `params.segmentLengths` = `[8, 8]`
  5. Submits start at segment 1; `params.segmentLengths` = `[10, 10, 4]`

### TC-PS-25: API restart and a failed join
- **App:** API unit
- **Steps:**
  1. R1 of TC-PS-23 `processing` at segment 2 with its `externalId`; restart the film worker
  2. Every segment of R1 is made; the join `ffmpeg` exits with an error
- **Expected:**
  1. Segment 2 keeps polling and is never submitted again; segment 1 is not made again; R1 ends `done`
  2. `failed`, `error_message` starts with `Joining the clip segments failed:`; `clip-segments/` is kept

## Speech & local servers

### TC-PS-14: Speech providers and the voice they need
- **App:** API unit
- **Precondition:** P1 narrates with VT-SHORT (20 s sample, no consent clip); VT-LONG (70 s sample, consent clip); faked ElevenLabs and Google AI.
- **Steps:**
  1. `speech` = `elevenlabs`; narration with VT-SHORT
  2. `speech` = `elevenlabs`; two narrations with VT-LONG
  3. `speech` = `google`; narration with VT-SHORT
  4. `speech` = `google`; narration with VT-LONG
  5. `speech` = `omnivoice`; narration with VT-SHORT
- **Expected:**
  1. `failed` at once, `error_message` = `ElevenLabs needs a voice sample of at least 60 s; 'VT-SHORT' is 20 s`
  2. ElevenLabs is asked to make a voice once (`POST /v1/voices/add`); `providerVoices.elevenlabs` set; both narrations use that voice id
  3. `failed` at once, `error_message` = `Google AI needs a consent clip for 'VT-SHORT' — add it in the library`
  4. `failed` at once, `error_message` = `Google AI needs a voice sample of 10-30 s; 'VT-LONG' is 70 s`
  5. The adapter gets `POST /speech` with `text`, `language`, `sample` and `sampleText` = VT-SHORT's text

### TC-PS-15: Local adapters
- **App:** API unit
- **Precondition:** Faked adapter servers for `omnivoice`, `ace_step`, `yue`.
- **Steps:**
  1. `test` `ace_step` whose `/health` answers 200
  2. A `music` request on `ace_step` for an episode of 95 s of kept clips
  3. A `music` request on `elevenlabs` for an episode of 420 s
  4. A `narration` whose adapter answers 500 `CUDA out of memory`
  5. A `narration` whose adapter gives no answer within `LOCAL_SERVER_TIMEOUT_SEC`
- **Expected:**
  1. `ok` = `true`
  2. `POST /music` with `{ "prompt": …, "durationS": 95, "instrumental": true }`
  3. ElevenLabs is asked for 300 s — its longest track
  4. A provider error with text `CUDA out of memory`, retried as 4.3
  5. `failed` at once, `error_message` = `OmniVoice timed out: …`, `attempts` = 1; nothing is sent again

## Google Flow

### TC-PS-16: Flow pacing guard
- **App:** API unit
- **Precondition:** `google_flow` with `max_concurrent` = 10, `min_interval_s` = 0; six `scene_clip` requests queued.
- **Steps:**
  1. Run the worker until all are submitted
- **Expected:**
  - Submits go out one at a time, each at least 3 s after the previous one; up to 10 stay in flight while polling

### TC-PS-17: Pause, Resume now and Open Flow tab
- **App:** API unit + API
- **Steps:**
  1. *(API unit)* The extension answers a submit with `PUBLIC_ERROR_UNUSUAL_ACTIVITY`; read `GET PV`
  2. *(API unit)* `POST PV/google_flow/resume`; run the worker
  3. `curl -i -X POST PV/google_flow/open-tab` with the extension disconnected
  4. *(API unit)* `POST PV/google_flow/open-tab` with the extension connected
- **Expected:**
  1. The request is `failed`; Google Flow `pausedUntil` ≈ now + 120 s; no Flow submit until then; the Google Flow sub-tab reads `Paused — resumes in {s} s` with `Resume now`
  2. `pausedUntil` = `null`; the next queued Flow request is submitted at once
  3. `HTTP 409`, `detail` = `The Google Flow extension is not connected`
  4. `204`; the extension receives an open-tab message

### TC-PS-18: Flow project and its fallback
- **App:** API unit
- **Steps:**
  1. First Flow request of project P; Flow creates a project `fp-1`
  2. First Flow request of project Q; project creation fails; `providers.flow_project_id` = `594758cc-0000-4000-8000-000000000000`
  3. First Flow request of project R; creation fails; no fallback id
- **Expected:**
  1. P's `flow_project_id` = `fp-1`; the request uses it
  2. The request uses the fallback id; Q's `flow_project_id` stays `null`
  3. `failed`, `error_message` = `No Flow project — create one in Flow and enter its id in Settings`

### TC-PS-19: The extension on the test port
- **App:** Frontend
- **Precondition:** The extension loaded unpacked from `video-tool/extension/google-flow/`; a signed-in Flow tab open.
- **Steps:**
  1. In the extension popup set `Agent port` to `5074`
  2. Navigate to http://localhost:5071/settings?tab=general
  3. Set `Agent port` to `4024` (no dev stack running); reload the page
- **Expected:**
  2. Sub-tab `Google Flow` selected, reading `Connected`; `Open Flow tab` is enabled
  3. Google Flow reads `Not connected`; `Open Flow tab` is disabled

## Queue

### TC-PS-20: Queue lines
- **App:** API unit
- **Precondition:** `fal` requests: 2 `queued`, 1 `processing`, 1 `failed` 2 h ago, 1 `failed` 30 h ago.
- **Steps:**
  1. `GET PV`
- **Expected:**
  - `fal` `queue` = `{ "queued": 2, "processing": 1, "failedLast24h": 1 }`; every other provider has zeros

## Provider errors

### TC-PS-21: Which provider errors are retried
- **App:** API unit
- **Precondition:** An image request on a faked `openai` provider; `FILM_REQUEST_MAX_ATTEMPTS` = 5.
- **Steps:**
  1. The provider answers `429`, then `503`
  2. The provider answers `409`
  3. Sending times out
  4. The provider takes the request (`external_id` `op-1`); the first status check times out, the second gets
     `503`, the third returns the image
  5. The provider takes the request; a status check reports the job failed (`Replicate: GPU lost`)
  6. A result download answers `503`, then `404`
  7. *(Google Flow)* The extension gives no answer within 300 s when sending
- **Expected:**
  1. Each time back to `queued`, `attempts` counted, `next_attempt_at` = now + 20 s, then + 40 s
  2. `failed` at once
  3. `failed` at once, `attempts` = 1; one submit only
  4. `done`, `attempts` = 0; one submit, three status checks of `op-1`
  5. `failed` at once with `Replicate: GPU lost`; one submit
  6. `503` → `Could not download the result: HTTP 503`, retried; `404` → `failed` at once
  7. `failed` at once with `Google Flow did not answer within 300 s`; nothing is sent again

## Claude CLI

### TC-PS-22: Claude CLI sub-tab and its test
- **App:** API unit + API + Frontend
- **Steps:**
  1. *(API unit)* `test` `claude_cli` whose faked `claude auth status --json` prints `{"loggedIn":true,"authMethod":"claude.ai"}`
  2. *(API unit)* the same, printing `{"loggedIn":false}`
  3. *(API unit)* `test` `claude_cli` with `CLAUDE_BIN` = `/nonexistent/claude`
  4. `curl -i -X PATCH PV/claude_cli -H 'Content-Type: application/json' -d '{"maxConcurrent":3}'`
  5. `curl -s PV`
  6. Navigate to http://localhost:5071/settings?tab=general&provider=claude_cli; click `Test connection`
- **Expected:**
  1. `{ "ok": true, "error": null, "testedAt": … }`; no `claude -p` call made
  2. `ok` = `false`, `error` = `Not signed in — run claude auth login`
  3. `ok` = `false`, `error` = `Claude CLI not found at '/nonexistent/claude'`
  4. `HTTP 400`, `detail` = `maxConcurrent does not apply to Claude CLI`
  5. `claude_cli`: `kind` = `cli`, `mediaKinds` = `["analysis"]`, `setUp` = `true`, `cliStatus` = `signedIn`, `hasKey` = `false`
  6. The Claude CLI sub-tab shows `OK` with the test time
