## 6. Cài đặt (Settings) (6-settings.md)

Test cases for [business/6-settings.md](../business/6-settings.md). Acronym `ST`.

## Test environment

- Stack, captcha switch and app labels: as in
  [1-video-to-markdown.md § Test environment](./1-video-to-markdown.md#test-environment).
- Start from a fresh test DB, so `app_settings` is empty.
- Shorthand: `S` = `http://localhost:5070/settings`; `AM` = `http://localhost:5070/settings/ai-models`;
  `PV` = `http://localhost:5070/settings/providers`.

---

## Settings

### TC-ST-01: Default value and save
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings
  2. Select `Japanese` from `Script language`; click `Save`
  3. Reload the page
  4. `curl -s S`
- **Expected:**
  - Step 1: tabs `General` · `AI models` · `Prompt override` · `Film Analysis` · `Film Clone` · `Film Studio`, `General` open; `Script language` = `Follow the target country` with the hint `The language Film Clone writes scripts in.`; `Save` is disabled; below it the panel `Providers` with its first sub-tab `Google Flow` selected (7.4); no `AI models`, `Input mode`, `Images with` or `Clips with` field on this tab
  - Step 2: notice `Saved`; `Save` is disabled again
  - Step 3: `Script language` = `Japanese`
  - Step 4: `{"scriptLanguage":"ja","aiModel":{"provider":"claude_cli","model":"default"},"aiStepModels":{"moments":null,"audio":null,"filmAnalysis":null,"filmScript":null,"filmClone":null},"inputMode":"subtitles","filmAnalysisInputMode":"subtitles","filmCloneInputMode":"subtitles","filmCloneImageProvider":null,"filmStudioImageProvider":null,"filmStudioClipProvider":null}`

### TC-ST-02: Validation
- **App:** API
- **Steps:**
  1. `curl -i -X PATCH S -H 'Content-Type: application/json' -d '{"theme":"dark"}'`
  2. `PATCH S` `{"scriptLanguage":"de"}`
  3. `PATCH S` `["ja"]`
  4. `PATCH S` `{"scriptLanguage":"ja","theme":"dark"}`
  5. `curl -s S` on a fresh test DB
  6. `PATCH S` `{"filmCloneImageProvider":"dall-e"}`
  7. `PATCH S` `{"filmStudioClipProvider":"sd_webui"}`
  8. `PATCH S` `{"filmCloneInputMode":"frames"}`
  9. `PATCH S` `{"imageSource":"local"}`
- **Expected:**
  1. `HTTP 400`, `detail` = `Unknown setting 'theme'`
  2. `HTTP 400`, `detail` = `Invalid value for 'scriptLanguage'`
  3. `HTTP 422`
  4. `HTTP 400`, `detail` = `Unknown setting 'theme'`; `scriptLanguage` is not changed
  5. `{"scriptLanguage":"follow_target_country","aiModel":{"provider":"claude_cli","model":"default"},"aiStepModels":{"moments":null,"audio":null,"filmAnalysis":null,"filmScript":null,"filmClone":null},"inputMode":"subtitles","filmAnalysisInputMode":"subtitles","filmCloneInputMode":"subtitles","filmCloneImageProvider":null,"filmStudioImageProvider":null,"filmStudioClipProvider":null}`
  6. `HTTP 400`, `detail` = `Invalid value for 'filmCloneImageProvider'`
  7. `HTTP 400`, `detail` = `Invalid value for 'filmStudioClipProvider'` — Stable Diffusion WebUI makes images only
  8. `HTTP 400`, `detail` = `Invalid value for 'filmCloneInputMode'`
  9. `HTTP 400`, `detail` = `Unknown setting 'imageSource'`

### TC-ST-03: Unsaved changes guard
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/settings; select `English` from `Script language`
  2. Click tab `AI models`; click `Cancel`
  3. Click tab `AI models`; click `OK`
  4. Navigate to `/settings?tab=general`
- **Expected:**
  - Steps 2 and 3: dialog `Discard unsaved changes?`; after `Cancel` tab `General` stays open with `English`
  - Step 3: tab `AI models` opens; URL has `?tab=ai-models`
  - Step 4: `Script language` shows the saved value, not `English`

### TC-ST-04: Film Clone reads the setting
- **App:** Frontend
- **Precondition:** K1 of [5-film-clone.md](./5-film-clone.md) at `choosing_localization`.
- **Steps:**
  1. Set `Script language` to `English` on `/settings`; save
  2. Navigate to `/film-clone/{K1}`; open `Localization`; select `Japan`
  3. Click `Change in Settings`
- **Expected:**
  - Step 2: the line reads `Script language: English` with `from Settings`
  - Step 3: URL becomes `/settings`; `Settings` is highlighted in the header

### TC-ST-05: Film Studio image and clip providers
- **App:** Frontend + API
- **Precondition:** project P1 of [4-film-studio.md](./4-film-studio.md) with a linked character; the mock
  providers running, as in [7-provider-settings.md](./7-provider-settings.md).
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=film-studio
  2. Select `Stable Diffusion WebUI / Forge` from `Images with` and `Replicate` from `Clips with`; click `Save`
  3. Navigate to `/films`; click `New project`
  4. Navigate to `/film-clone`
  5. Navigate to `/films/{P1}`; click `Generate` on the character; `curl -s http://localhost:5070/films/projects/{P1}`
  6. On `/settings?tab=film-studio`, select `Same as AI models (Google Flow)` from `Images with`; click `Save`;
     click `Regenerate` on the same character
- **Expected:**
  - Step 1: `Images with` = `Same as AI models (Google Flow)` with the hint `Makes the reference and scene
    images of Film Studio.`; `Clips with` = `Same as AI models (Google Flow)` with the hint `Makes the clips of
    Film Studio.`; `Save` is disabled
  - Step 2: notice `Saved`; `curl -s S` has `"filmStudioImageProvider":"sd_webui","filmStudioClipProvider":"replicate"`
    and `"filmCloneImageProvider":null`; under `Images with` the warning `Stable Diffusion WebUI / Forge is not
    set up — set it up in General.` and under `Clips with` `Replicate is not set up — set it up in General.`,
    each `General` linking to `/settings?tab=general&provider={its id}`
  - Step 3: no `Images with` or `Clips with` field; the line `Images with: Stable Diffusion WebUI / Forge · Clips
    with: Replicate` with a link `Change` → `/settings?tab=film-studio`
  - Step 4: the `New clone` panel shows `Images with: Google Flow` with `Change` → `/settings?tab=film-clone`
  - Step 5: the character's open request has `"provider":"sd_webui"`; the project JSON has no image or clip
    provider field
  - Step 6: notice `Saved`; the new request has `"provider":"google_flow"`

### TC-ST-06: Film Clone image provider and input mode
- **App:** Frontend + API
- **Precondition:** fresh test DB.
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=film-clone
  2. Select `OpenAI` from `Images with`
  3. Select `Google Flow` from `Images with` and `Frame image + audio` from `Input mode`; click `Save`
  4. `curl -s S`
  5. Navigate to `/film-clone`
  6. Navigate to `/`
  7. `curl -s -X PATCH AM -H 'Content-Type: application/json' -d '{"routes":{"image":"fal"}}'`; navigate to
     `/settings?tab=film-clone`; select the first option of `Images with`
- **Expected:**
  - Step 1: `Images with` = `Same as AI models (Google Flow)` with the hint `Makes the asset references and scene
    images of Film Clone.`; `Input mode` = `Subtitles` (options `Subtitles`, `Frame image + audio`) with the
    hint `What the model gets from the film.`; `Save` is disabled
  - Step 2: warning `OpenAI is not set up — set it up in General.`, `General` linking to
    `/settings?tab=general&provider=openai`
  - Step 3: notice `Saved`; no provider warning; under `Input mode` the warning `Frame image + audio needs a
    Google AI model here.` — the `Audio` model is still Claude (CLI default)
  - Step 4: `"filmCloneImageProvider":"google_flow","filmCloneInputMode":"whole_video"`, while
    `"inputMode":"subtitles"`, `"filmAnalysisInputMode":"subtitles"` and `"filmStudioImageProvider":null`
  - Step 5: the `New clone` panel reads `AI: Key moments — Claude (CLI default) · Audio — Claude (CLI default) —
    needs Google AI · Film clone — Claude (CLI default) · Input: Frame image + audio`, `Change` after `AI` →
    `/settings?tab=ai-models`, `Change` after `Input` → `/settings?tab=film-clone`; the line `Images with: Google
    Flow`; `Clone` is disabled
  - Step 6: the `New conversion` panel reads `AI: Claude (CLI default) · Input: Subtitles`
  - Step 7: on the reloaded tab `Images with` still reads `Google Flow` and its first option reads `Same as AI
    models (fal.ai)`; after selecting it, warning `fal.ai is not set up — set it up in General.`

### TC-ST-07: Old tab addresses
- **App:** Frontend
- **Precondition:** fresh test DB; `{default id}` = the id of `Default` from `GET http://localhost:5070/prompt-presets`.
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=providers
  2. Navigate to `/settings?tab=prompt-presets&id={default id}`
  3. Navigate to `/settings?tab=general&provider=claude_cli`
- **Expected:**
  - Step 1: URL becomes `/settings?tab=general`; tab `General` is open
  - Step 2: URL has `tab=prompt-override` and `id={default id}`; tab `Prompt override` is open with `Default`
    selected in the panel `Presets`
  - Step 3: tab `General` is open with the sub-tab `Claude CLI` selected

### TC-ST-08: AI models saved all or none
- **App:** API
- **Precondition:** fresh test DB.
- **Steps:**
  1. `curl -i -X PATCH AM -H 'Content-Type: application/json' -d '{"inputMode":"whole_video","routes":{"image":"fal","video":"openai"}}'`
  2. `curl -s S`; `curl -s PV`
  3. `PATCH AM` `{"inputMode":"whole_video","routes":{"image":"fal"},"models":{"fal":{"image":"no-such-model"}}}`
  4. `PATCH AM` `{"models":{"midjourney":{"image":"v7"}}}`
  5. `PATCH AM` `{"routes":{"apiImage":"google"}}`
  6. `PATCH AM` `["whole_video"]`
  7. `PATCH AM` `{"inputMode":"whole_video","routes":{"image":"sd_webui","video":"replicate"}}`
  8. `PATCH AM` `{"filmAnalysisInputMode":"full_video","routes":{"video":"openai"}}`
  9. `PATCH AM` `{"filmAnalysisInputMode":"full_video"}`
- **Expected:**
  1. `HTTP 400`, `detail` = `OpenAI cannot serve video`
  2. `inputMode` = `subtitles`; `routes` = `{"image":"google_flow","video":"google_flow","speech":"omnivoice","music":"ace_step"}`
  3. `HTTP 400`, `detail` = `Unknown model 'no-such-model' for fal.ai image`; `inputMode` and `routes` as in step 2
  4. `HTTP 404`, `detail` = `Provider midjourney not found`
  5. `HTTP 400`, `detail` = `Unknown route 'apiImage'`
  6. `HTTP 422`
  7. `HTTP 200`; `settings.inputMode` = `whole_video`; `providers.routes` = `{"image":"sd_webui","video":"replicate","speech":"omnivoice","music":"ace_step"}`
  8. `HTTP 400`, `detail` = `OpenAI cannot serve video`; `filmAnalysisInputMode` still `subtitles`
  9. `HTTP 200`; `settings.filmAnalysisInputMode` = `full_video`, `settings.inputMode` still `whole_video`

### TC-ST-09: Film Analysis input mode
- **App:** Frontend + API
- **Precondition:** fresh test DB; `google` has no key.
- **Steps:**
  1. Navigate to http://localhost:5071/settings?tab=film-analysis
  2. Select `Frame image + audio` from `Input mode`
  3. Select `Full video` from `Input mode`; click `Save`; `curl -s S`
  4. Click tab `AI models`
  5. Navigate to `/film-analysis`; click the `Change` right after `Input: Full video`
  6. `curl -s -X PATCH S -H 'Content-Type: application/json' -d '{"aiStepModels":{"filmAnalysis":{"provider":"google","model":"gemini-3.8-flash"}}}'`; reload the page
- **Expected:**
  - Step 1: tab `Film Analysis` open, between `Prompt override` and `Film Clone`; `Input mode` = `Subtitles` with the
    options `Subtitles`, `Frame image + audio`, `Full video` and the hint `What the model gets from the film.`; no
    warning; `Save` is disabled
  - Step 2: under `Input mode`, `Frame image + audio needs a Google AI model here.`; `Save` is enabled
  - Step 3: under `Input mode`, `Full video needs a Google AI model here.`; notice `Saved`; body has
    `"filmAnalysisInputMode":"full_video"`, `"inputMode":"subtitles"`, `"filmCloneInputMode":"subtitles"`
  - Step 4: group `Text` ends with `Video to Markdown input` — no `Film Analysis input`; under `Film analysis`,
    `Full video needs a Google AI model here.`; no warning under `Audio`
  - Step 5: `New analysis` reads `AI: Film analysis — Claude (CLI default) — needs Google AI · Input: Full video`,
    with a link `Change` for the AI models and its own link `Change` right after `Input: Full video`; after the
    click, URL becomes `/settings?tab=film-analysis` with `Input mode` = `Full video`
  - Step 6: no warning under `Input mode`

### TC-ST-10: Field help
- **App:** Frontend
- **Precondition:** fresh test DB.
- **Steps:**
  1. Navigate to http://localhost:5071/settings; hover the `(i)` after `Script language`
  2. Move the mouse away; press `Tab` until `About Script language` has focus; press `Esc`
  3. In `Providers`, on the sub-tab `Google AI (Gemini, Veo)` hover the `(i)` of `API key`, then of
     `Concurrent requests`; on the sub-tab `Google Flow` hover the `(i)` of `Seconds between requests`
  4. Click tab `AI models`; hover the `(i)` of `Audio`, of `Video to Markdown input`, of `Images` and of
     `Image model` on the `Google AI` row
  5. Click tab `Prompt override`; hover the `(i)` of `Instructions` in `Speakers & sounds`
  6. Click tabs `Film Analysis`, `Film Clone` and `Film Studio` in turn; hover the `(i)` of each field
  7. On every tab and provider sub-tab, count the select, text, number and text-area fields that can be changed
     and the `(i)` buttons
- **Expected:**
  - Step 1: a tooltip `Film Clone writes the script of a clone in this language. Follow the target country: …`
    (6.2); the hint `The language Film Clone writes scripts in.` stays under the field
  - Step 2: no tooltip after the mouse leaves; the same tooltip while the button has focus; `Esc` hides it
  - Step 3: `The key the app sends with every request to Google AI (Gemini, Veo). …`; `How many requests to Google
    AI (Gemini, Veo) can wait for an answer at once, 1–10. The others wait in the queue.`; `The least time
    between two requests sent to Google Flow, 0–600 s, to stay under its rate limit. Google Flow always sends
    one at a time, at least 3 s apart.`
  - Step 4: the help texts of 8.4 for `Audio` and `Video to Markdown input`; of 7.4 for `Images`, and `The model
    Google AI (Gemini, Veo) uses to make a new image.` for `Image model`
  - Step 5: `What the AI model is told to do for Speakers & sounds. A job copies these instructions when it is
    created, …`
  - Step 6: the help texts of 6.2 for `Input mode` (Film Analysis), `Images with` and `Input mode` (Film Clone),
    `Images with` and `Clips with` (Film Studio)
  - Step 7: every field that can be changed has exactly one `(i)` button, named `About {label}`; the read-only
    `Added by the app` text areas have none
