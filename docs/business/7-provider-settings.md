# 7. Nhà cung cấp media (Provider Settings)

> One file = one domain. Every section below belongs to the **Provider Settings** domain.

Says how the app reaches each provider that makes images, clips, speech and music for Film Studio (domain 4)
and Film Clone (domain 5): its key or server address, the model it uses from a fixed catalog, how many
requests it takes at once and how fast. Its routes pick which provider makes images, clips, speech and music;
Film Clone and Film Studio follow the image and clip routes unless they pick their own (6.1). The `google`
and `openai` providers also hold the keys of AI Models (domain 8), and `claude_cli` stands for the `claude`
CLI it runs. Connections are set in the `General` tab of `/settings`, routes and models in its `AI models`
tab (7.4).

- Persona: the same single local user as domain 1. No captcha on these routes.
- Entities: `Provider` (table `providers`), `ProviderRoute` (table `provider_routes`); the model catalog
  lives in the API code (7.5).
- Callers store only the provider id each `GenerationRequest` used (4.3); everything else is read here when
  the request is submitted.

## 7.1 Providers

The list is fixed; the rows are written at API start when missing.

| Provider | `id` | `kind` | Media kinds | Needs |
|---|---|---|---|---|
| Google Flow | `google_flow` | `extension` | `image`, `edit_image`, `video` | the Chrome extension connected to a signed-in Flow tab (7.7) |
| Google AI (Gemini, Veo) | `google` | `api` | `image`, `edit_image`, `video`, `speech`, `analysis` | API key |
| fal.ai | `fal` | `api` | `image`, `edit_image`, `video` | API key |
| Replicate | `replicate` | `api` | `image`, `edit_image`, `video` | API key |
| OpenAI | `openai` | `api` | `image`, `edit_image`, `analysis` | API key |
| ElevenLabs | `elevenlabs` | `api` | `speech`, `music` | API key |
| Stable Diffusion WebUI / Forge | `sd_webui` | `local` | `image`, `edit_image` | base URL of the user's server (7.6) |
| OmniVoice | `omnivoice` | `local` | `speech` | base URL of its adapter server (7.6) |
| ACE-Step | `ace_step` | `local` | `music` | base URL of its adapter server (7.6) |
| YuE | `yue` | `local` | `music` | base URL of its adapter server (7.6) |
| Claude CLI | `claude_cli` | `cli` | `analysis` | the `claude` CLI at `CLAUDE_BIN`, signed in |

### Data model — `Provider`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(20) | primary key; the ids above |
| `api_key_encrypted` | blob \| null | `api` kind only (7.3) |
| `api_key_last4` | string(4) \| null | last 4 characters of the key |
| `base_url` | string(500) \| null | `local` kind only |
| `models` | JSON | `api` and `extension` kinds: a model id of 7.5 per media kind it serves but `analysis`, e.g. `{ "image": "…", "video": "…" }`; a missing entry → the catalog default. `local` providers use the model loaded in their server; `analysis` models are picked in the AI models settings (8.1) |
| `max_concurrent` | int | requests in flight — submitted and not yet answered; 1–10. Default `google_flow` 5, `api` 2, `local` 1 |
| `min_interval_s` | int | seconds between two submits; 0–600. Default `google_flow` 10, the others 0 |
| `flow_project_id` | string(36) \| null | `google_flow` only — the fallback Flow project (7.7) |
| `last_test_at` / `last_test_ok` / `last_test_error` | datetime / boolean / text \| null | last connection test (7.3) |
| `updated_at` | datetime (UTC) | |

A provider is **set up** when: `api` → a key is stored and can be decrypted; `local` → `base_url` is set;
`extension` → always (whether the extension is connected is checked per request, 4.3); `cli` → always
(whether the CLI is signed in is checked by the test, 7.3, and by each call, 8.2).

### Rules

`models` is saved with `PATCH /settings/ai-models` (6); the other fields with `PATCH /settings/providers/{id}`.

| Rule | Result |
|---|---|
| Unknown provider | 404 `Provider {id} not found` |
| A field that does not fit the kind — `apiKey` on a non-`api` provider, `baseUrl` on a non-`local` one, `models` on a `local` one, a model for a media kind it does not serve or for `analysis`, `flowProjectId` on any but `google_flow`, any field on `claude_cli` | 400 `{field} does not apply to {provider name}` |
| `apiKey` trimmed is 1–500 characters; `null` removes the key | 400 `API key must be 1-500 characters` |
| `baseUrl` starts with `http://` or `https://`; `null` clears it | 400 `Base URL must start with http:// or https://` |
| Each model is in the catalog of 7.5 for that provider and media kind | 400 `Unknown model '{model}' for {provider name} {media kind}` |
| `flowProjectId` is a UUID; `null` clears it | 400 `Flow project id must be a UUID` |
| `maxConcurrent` 1–10 | 400 `Concurrent requests must be between 1 and 10` |
| `minIntervalS` 0–600 | 400 `Interval must be between 0 and 600 seconds` |

### When the values are read

- The provider of a request is fixed when the request is created (4.3). Its key, base URL, model,
  `max_concurrent` and `min_interval_s` are read when the worker submits it, so a change applies to requests
  submitted afterwards; a request already `processing` finishes as it started.
- `analysis` is not a `GenerationRequest`: an AI call of domain 8 reads the key when it starts and takes its
  model from the AI models settings (8.1); `max_concurrent`, `min_interval_s` and the queue line do not count
  it (8.2).
- At submit, a request is `failed` at once, nothing sent, when:

| Case | `error_message` |
|---|---|
| Provider not set up | `{provider name} is not set up — open Settings` |
| `speech`: the narrator voice lacks what the provider needs (7.5) | the message of 7.5 § Speech |

- More references than the model takes (7.5) → the image is made in passes, one reference per pass, in the
  order of `character_ids`: pass 1 is the request with the first reference; each next pass edits the result
  of the previous one with the next reference only, prompt `Keep the scene, the framing and everyone else
  unchanged. Make {name} look like the reference image.` Each pass is one paid generation. The request keeps
  its one slot; `params.pass` / `params.passes` show the progress; a pass retried under 4.3 § Retries starts
  again at that pass.
- A model that takes no reference (Flux Kontext) gets the source image only; `params.droppedReferences` lists
  the references not sent.
- Stable Diffusion WebUI never runs passes: it gets one composite image (7.6).
- A `video` request asks for the scene's `clip_duration_s` (4.3), L, out of the model's clip lengths (7.5):
  1. The shortest length ≥ L → one clip, cut at L when longer.
  2. None → segments: a first segment of the longest length; then, while the clip is shorter than L, one
     more segment of the shortest length that brings it to L or more — the longest when none does. A
     segment after the first adds its length minus 1 s: its first second is cut at the join.
  3. The joined clip is cut at L.

  Example, 30 s: Veo 3.1 Lite on Google Flow (8 s only) → segments 8, 8, 8, 8, 8 s, joined 8 + 7 + 7 + 7 +
  7 = 36 s, cut to 30 s; Veo 3.1 on Google AI (4, 6, 8 s) → segments 8, 8, 8, 8, 4 s, joined 8 + 7 + 7 + 7 +
  3 = 32 s, cut to 30 s. Each segment is one paid
  generation. The request keeps its one slot and the model of its first segment; `params.segment` /
  `params.segments` show the progress, `params.segmentLengths` the plan. How a segment starts and what a
  failure keeps: 4.3 § Segments.
- A `music` request asks for at most the model's longest track (7.5); a shorter track loops until the film
  ends (4.4).

## 7.2 Routing

| Route | Used when | Choices | Default |
|---|---|---|---|
| `image` | `image`, `edit_image` of Film Clone or Film Studio whose image provider setting is `null` (6.1) | `google_flow`, `google`, `fal`, `replicate`, `openai`, `sd_webui` | `google_flow` |
| `video` | `video` of Film Studio while `filmStudioClipProvider` is `null` (6.1) | `google_flow`, `google`, `fal`, `replicate` | `google_flow` |
| `speech` | every `speech` request (4.4) | `omnivoice`, `elevenlabs`, `google` | `omnivoice` |
| `music` | every `music` request (4.4) | `ace_step`, `elevenlabs`, `yue` | `ace_step` |

### Data model — `ProviderRoute`

| Field | Type | Meaning |
|---|---|---|
| `route` | string(20) | primary key; the routes above |
| `provider_id` | string(20) | → `providers.id` |
| `updated_at` | datetime (UTC) | |

A route without a row uses its default.

| Rule | Result |
|---|---|
| Route is one of the four | 400 `Unknown route '{route}'` |
| Provider is one of the route's choices | 400 `{provider name} cannot serve {route}` |

A route change applies to requests created afterwards; queued requests keep the provider they were given.

## 7.3 API keys & connection test

### Keys

- Encrypted with `SETTINGS_SECRET_KEY` from `api/.env` before they are stored. No route ever returns a key —
  only `hasKey` and `apiKeyLast4`.
- Saving a key while `SETTINGS_SECRET_KEY` is empty → 409 `Set SETTINGS_SECRET_KEY in api/.env before saving
  API keys`.
- A stored key that cannot be decrypted — the secret was changed — makes the provider not set up and is
  reported as `keyUnreadable`; saving a new key replaces it.
- Keys are never written to logs, errors or `GenerationRequest` rows.

### `POST /settings/providers/{id}/test`

| Kind | Check | Spends credit |
|---|---|---|
| `api` | one authenticated read call — `google` lists models, `openai` lists models, `replicate` reads the account, `elevenlabs` reads the user, `fal` reads the account billing | no |
| `local` | `sd_webui`: `GET /sdapi/v1/sd-models`; adapters: `GET /health` (7.6) | no |
| `extension` | the extension is connected | no |
| `cli` | `{CLAUDE_BIN} auth status --json` answers `"loggedIn": true`; else `error` = `Not signed in — run claude auth login`, or `Claude CLI not found at '{CLAUDE_BIN}'` when the command cannot start | no |

- Limited to `PROVIDER_TEST_TIMEOUT_SEC`. Not set up → `ok = false`, `error` = `Not set up`.
- The result is stored in `last_test_*` and returned as `{ "ok", "error", "testedAt" }`; a failed test is not
  an HTTP error. A `fal` key without billing scope fails this check yet still runs models.

## 7.4 Screens of `/settings`

### Panel "Providers" of the `General` tab (6.2)

- One sub-tab per provider, in the order of 7.1, labelled with its name; the first is selected;
  `&provider={id}` selects one, and selecting a sub-tab writes it to the URL.
- `SETTINGS_SECRET_KEY` empty → notice `Set SETTINGS_SECRET_KEY in api/.env to save API keys.` above the
  sub-tabs; every `API key` field is disabled.
- The panel refreshes the status and queue lines every 5 s while the `General` tab is open.

A sub-tab shows its provider:

| Part | Detail |
|---|---|
| Title | name, badge `API` / `Local` / `Extension` / `CLI` |
| Status | `Ready` \| `Not set up` \| `Key unreadable — enter it again`; Google Flow: `Connected` \| `Not connected` \| `Paused — resumes in {s} s`; Claude CLI: `Signed in` \| `Not signed in` \| `CLI not found` — the check of 7.3, run when the `General` tab opens and at most once a minute after |
| Queue | `Queued {n} · Running {n} · Failed (24 h) {n}` — this provider's requests; not on Claude CLI |
| `API key` | `api` only; password field, placeholder `••••{last4}` when a key is stored; `Remove key` → confirm `Remove the API key of {name}?`; help `The key the app sends with every request to {name}. It is stored encrypted and never shown again, only its last 4 characters. Without a key the provider is not set up and its requests fail.` |
| `Base URL` | `local` only; hint `Run the adapter of tools/local-servers/ and enter its address.` on OmniVoice, ACE-Step and YuE; help `The address of the local server the app calls, starting with http:// or https://. Without it the provider is not set up and its requests fail.` |
| Google Flow only | `Fallback Flow project id` field, help `The id in the address of a Flow project you made. Used only when the app cannot create a Flow project for a film project or a film clone.`; `Resume now` while paused; `Open Flow tab`, disabled when not connected |
| `Concurrent requests`, `Seconds between requests` | number fields; not on Claude CLI. Help: `How many requests to {name} can wait for an answer at once, 1–10. The others wait in the queue.` · `The least time between two requests sent to {name}, 0–600 s, to stay under its rate limit.` — on Google Flow followed by ` Google Flow always sends one at a time, at least 3 s apart.` |
| Models line | line `Pick its models in AI models.`, `AI models` linking to `?tab=ai-models` |
| Buttons | `Save` (enabled with unsaved changes; notice `Saved`; not on Claude CLI), `Test connection` → `OK` or the error, with the test time |

### Groups "Images", "Clips", "Speech", "Music" of the `AI models` tab (6.2)

Each group opens with the select of its route (7.2), then one row per provider the route can choose, in the
order of the select:

| Group | Select | Rows |
|---|---|---|
| `Images` | `Images`: `Google Flow` \| `Google AI` \| `fal.ai` \| `Replicate` \| `OpenAI` \| `Stable Diffusion WebUI / Forge`; hint `Film Clone and Film Studio use it unless they pick their own.`; help `The provider of every image of Film Clone and Film Studio, unless their own tab picks another. A queued image keeps the provider it was given.` | Google Flow, Google AI, fal.ai, Replicate, OpenAI: `Image model`, `Image edit model`; Stable Diffusion WebUI / Forge: line `Uses the model loaded in the server.` |
| `Clips` | `Clips`: `Google Flow` \| `Google AI` \| `fal.ai` \| `Replicate`; hint `Film Studio uses it unless it picks its own.`; help `The provider of every clip of Film Studio, unless the Film Studio tab picks another. A queued clip keeps the provider it was given.` | each: `Clip model` |
| `Speech` | `Speech`: `OmniVoice` \| `ElevenLabs` \| `Google AI`; help `The provider that reads the narration of Film Studio episodes aloud.` | ElevenLabs, Google AI: `Speech model`; OmniVoice: line `Uses the model loaded in the server.` |
| `Music` | `Music`: `ACE-Step` \| `ElevenLabs` \| `YuE`; help `The provider that makes the music of Film Studio episodes.` | ElevenLabs: `Music model`; ACE-Step, YuE: line `Uses the model loaded in the server.` |

- A model select lists the models of 7.5 for that provider and media kind, the saved one — else the default
  — preselected. Help: `Image model` `The model {name} uses to make a new image.` · `Image edit model` `The
  model {name} uses to change an existing image.` · `Clip model` `The model {name} uses to make a clip.` ·
  `Speech model` `The model {name} uses to read text aloud.` · `Music model` `The model {name} uses to make
  music.`
- Badge `In use` on the row of every provider a request of the group goes to now: the route's, and for
  `Images` and `Clips` the providers Film Clone and Film Studio picked (6.1), as saved.
- A row whose provider is not set up shows `Not set up — set it up in General.`, `General` linking to
  `?tab=general&provider={id}`; its model selects stay editable.
- The groups are saved with the tab's `Save` (6.2): the routes and the models in one
  `PATCH /settings/ai-models`.

- An error shows an alert with the API `detail` and keeps the input; the unsaved changes guard is that of 6.2.

## 7.5 Model catalog

The models the app knows how to call. The screen offers only these; ★ = default.

### Image (`image`, `edit_image`)

| Provider | Models (label — id) | Max references |
|---|---|---|
| `google_flow` | ★ Nano Banana Pro — `GEM_PIX_2`; Nano Banana 2 — `NARWHAL`; Nano Banana 2 Lite — `HARBOR_SEAL` | every listed reference |
| `google` | ★ Nano Banana 2.1 — `gemini-nano-banana-2.1`; Nano Banana 2 — `gemini-3.1-flash-image`; Nano Banana Pro — `gemini-3-pro-image` | 14; 14; 11 |
| `fal` | `image`: ★ Nano Banana Pro — `fal-ai/nano-banana-pro` (`fal-ai/nano-banana-pro/edit` when references are sent). `edit_image`: ★ Nano Banana Pro edit — `fal-ai/nano-banana-pro/edit`; Nano Banana 2.1 edit — `google/nano-banana-2.1/edit`; Seedream 4.5 edit — `fal-ai/bytedance/seedream/v4.5/edit`; Flux Kontext — `fal-ai/flux-pro/kontext` | 14; 14; 10; 0 (the source image only) |
| `replicate` | `image`: ★ Nano Banana Pro — `google/nano-banana-pro`; Seedream 4.5 — `bytedance/seedream-4.5`. `edit_image`: the same two, plus Flux Kontext Pro — `black-forest-labs/flux-kontext-pro` | 14; 14; 0 (the source image only) |
| `openai` | ★ GPT Image 2.5 — `gpt-image-2.5-sunburst`; GPT Image 2.5 Flare — `gpt-image-2.5-flare` | 4 |
| `sd_webui` | the checkpoint loaded in the server | — one composite image (7.6) |

### Video (`video`)

| Provider | Model (label — id) | Clip lengths | Sound |
|---|---|---|---|
| `google_flow` | ★ Veo 3.1 Lite — `veo_3_1_i2v_lite` | 8 s | yes |
| `google_flow` | Veo 3.1 Lite, low priority — `veo_3_1_i2v_lite_low_priority` | 8 s | yes |
| `google_flow` | Veo 3.1 Fast — `veo_3_1_i2v_s_fast_ultra` | 8 s | yes |
| `google_flow` | Omni Flash — `abra_i2v_{n}s`, 720p | 4, 6, 8, 10 s | yes |
| `google` | ★ Veo 3.1 Lite — `veo-3.1-lite-generate-preview`; Veo 3.1 Fast — `veo-3.1-fast-generate-preview`; Veo 3.1 — `veo-3.1-generate-preview`; 720p | 4, 6, 8 s | yes |
| `fal` | ★ Kling 3 Pro — `fal-ai/kling-video/v3/pro/image-to-video`; Seedance 2.5 — `bytedance/seedance-2.5/image-to-video` | 4, 6, 8, 10 s | yes |
| `replicate` | ★ Kling 3 — `kwaivgi/kling-v3-video`; Wan 3 — `alibaba/wan-3` | 4, 6, 8, 10 s | yes |
| `replicate` | Veo 3.1 — `google/veo-3.1`; Veo 3.1 Fast — `google/veo-3.1-fast` | 4, 6, 8 s | yes |
| `replicate` | Hailuo 2.3 — `minimax/hailuo-2.3` | 6, 10 s | no |

Clip lengths are what the app may ask a model for; a scene of another length is cut from a longer clip or
joined from segments (7.1). A clip without sound has no dialogue.

### Speech (`speech`)

Every speech provider imitates the project's narrator voice (4.1). ElevenLabs and Google AI first make their
own copy of the voice from the template — once per template, kept in its `provider_voices` — and reuse it;
a new sample or consent clip drops the copies.

| Provider | Models | Needs from the voice template | Refused with |
|---|---|---|---|
| `omnivoice` | the model loaded in the adapter | the sample and its `sample_text` | — |
| `elevenlabs` | ★ Eleven v4 — `eleven_v4`; Eleven v4 Turbo — `eleven_v4_turbo`; Eleven v3 — `eleven_v3`; Flash 2.5 — `eleven_flash_v2_5` | a sample of at least 60 s; a paid plan (Starter or higher) | `ElevenLabs needs a voice sample of at least 60 s; '{voice}' is {n} s` |
| `google` | ★ Gemini 3.8 Flash TTS — `gemini-3.8-flash-tts`; Gemini 3.8 Flash Lite TTS — `gemini-3.8-flash-lite-tts` | a sample of 10–30 s and a consent clip — the same speaker reading Google's consent statement | `Google AI needs a voice sample of 10-30 s; '{voice}' is {n} s` / `Google AI needs a consent clip for '{voice}' — add it in the library` |

A failure while the provider makes its copy fails the `narration` request with the provider's message.

### Music (`music`)

| Provider | Models | Longest track |
|---|---|---|
| `elevenlabs` | ★ Music v2.5 — `music_v2_5`; Music v2 — `music_v2`; Music v1 — `music_v1` | 300 s |
| `ace_step` | the model loaded in the adapter | 600 s |
| `yue` | the model loaded in the adapter | 600 s |

### Analysis (`analysis`)

The models the AI models settings offer (8.1). The label is what every screen shows.

| Provider | Models |
|---|---|
| `claude_cli` | ★ Claude (CLI default) — `default`; Claude Fable — `fable`; Claude Opus — `opus`; Claude Sonnet — `sonnet`; Claude Haiku — `haiku` |
| `google` | ★ Gemini 4 Argon — `gemini-4-argon`; Gemini 3.8 Flash — `gemini-3.8-flash`; Gemini 3.5 Flash-Lite — `gemini-3.5-flash-lite` |
| `openai` | ★ GPT-6 Astra — `gpt-6-astra`; GPT-6.1 Sol — `gpt-6.1-sol`; GPT-6 Luna — `gpt-6-luna` |

The `claude_cli` ids are the CLI's model aliases; `default` sends no `--model` (8.2).

## 7.6 Local servers

The user installs and runs each server; the app only calls it at `base_url`.

**Stable Diffusion WebUI / Forge** — started with its API on (`--api`), usually `http://127.0.0.1:7860`.

| Request | Call |
|---|---|
| `image` without a reference | `POST /sdapi/v1/txt2img` |
| `edit_image` without a reference | `POST /sdapi/v1/img2img` — init image = the current image, `denoising_strength` = `SD_DENOISING_STRENGTH` |
| `clone_scene_image` | the same, init image = the shot's original frame (5.4) |
| `image` or `edit_image` with references | `POST /sdapi/v1/img2img` — init image = the composite below, `denoising_strength` = `SD_COMPOSITE_DENOISING_STRENGTH` |

Composite, built by the app at the request's size:

1. Base, scaled to cover the frame: the current image for `edit_image`; else the reference of the scene's
   first `location`; else a neutral grey canvas.
2. Every other reference, in `character_ids` order, scaled to 60% of the frame height and placed side by side,
   centred, over the lower part of the base.
3. The prompt says what the scene shows; img2img blends the pasted references into one picture.

Size: 1344×768 (16:9) or 768×1344 (9:16). The checkpoint is the one loaded in the server.

**OmniVoice, ACE-Step, YuE** — none of them ships a server the app can call, so the repo ships one adapter
per model under `tools/local-servers/`. Each adapter wraps the installed model and answers:

```
GET  {base_url}/health   → 200 { "ok": true }
POST {base_url}/speech   — multipart `text`, `language`, `sample` (file), `sampleText` → 200 audio/wav        (OmniVoice)
POST {base_url}/music    — JSON { "prompt", "durationS", "instrumental": true } → 200 audio/wav or audio/mpeg  (ACE-Step, YuE)
```

- A non-2xx answer is a provider error; its body, cut to 500 characters, is the error text (4.3 § Retries).
- A call longer than `LOCAL_SERVER_TIMEOUT_SEC` is a timeout: `failed` at once (4.3 § Retries).

## 7.7 Google Flow

- The extension lives in `video-tool/extension/google-flow/` (ported from flowkit; its README lists the changes) and is
  loaded unpacked in Chrome. It runs only the commands the API sends — `batch_rpc` and `open_flow_tab` — and
  never sends the Flow bearer token to the API. It connects to `ws://127.0.0.1:{FLOW_WS_PORT}` — 4024 for the dev stack, 5074 for
  the test stack; its popup has an `Agent port` field, default 4024.
- Pacing: whatever `max_concurrent` and `min_interval_s` say, Flow generation submits go out one at a time
  and at least 3 s apart. This guard is fixed: submits fired back to back lower Google's trust in the session
  until it answers `unusual activity`.
- `unusual activity` (4.3 § Retries) pauses every Flow submit for 120 s; the Google Flow sub-tab counts down.
  `Resume now` ends the pause at once.
- Flow project: on the first Flow request of a film project or a film clone, the provider creates a Flow
  project named after it and stores its id in that row's `flow_project_id`. When creation fails, it uses
  `providers.flow_project_id` — the id in the address of a project the user made in Flow. Neither → the
  request is `failed` with `No Flow project — create one in Flow and enter its id in Settings`.
- `Open Flow tab` asks the extension to open, or bring forward, a Flow tab.

---

## API endpoints

Same JSON and error conventions as domain 1.

```
GET   /settings/providers                      — { "routes": { "image", "video", "speech", "music" }, "providers": Provider[], "secretKeySet" }
PATCH /settings/providers/{id}                 — { "apiKey"?, "baseUrl"?, "flowProjectId"?, "maxConcurrent"?, "minIntervalS"? } → Provider
POST  /settings/providers/{id}/test            — { "ok", "error", "testedAt" }
POST  /settings/providers/google_flow/resume   — Provider
POST  /settings/providers/google_flow/open-tab — 204
```

`Provider`: `id`, `name`, `kind`, `mediaKinds`, `hasKey`, `apiKeyLast4`, `keyUnreadable`, `baseUrl`, `models`,
`catalog` (per media kind: `[{ "id", "label", "isDefault", "clipLengths"?, "maxReferences"? }]`),
`maxConcurrent`, `minIntervalS`, `setUp`, `queue` (`{ "queued", "processing", "failedLast24h" }`),
`lastTest` (`{ "ok", "error", "testedAt" }` or `null`); Google Flow adds `extensionConnected`, `pausedUntil`,
`flowProjectId`; Claude CLI adds `cliStatus` (`signedIn` \| `notSignedIn` \| `notFound`).

Routes and models are saved with `PATCH /settings/ai-models` (6).

| Route | Errors |
|---|---|
| `PATCH /settings/providers/{id}` | 400 field rules · 404 · 409 no secret key · 422 |
| `POST /settings/providers/{id}/test` | 404 |
| `POST …/google_flow/resume` | — (not paused → no change) |
| `POST …/google_flow/open-tab` | 409 `The Google Flow extension is not connected` |

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `SETTINGS_SECRET_KEY` | empty — API keys cannot be saved | 7.3 |
| `PROVIDER_TEST_TIMEOUT_SEC` | `15` | 7.3 |
| `FLOW_WS_PORT` | `4024`; `5074` in `.env.test` | 7.7 |
| `LOCAL_SERVER_TIMEOUT_SEC` | `1800` | 7.6 |
| `SD_DENOISING_STRENGTH` | `0.6` | 7.6 |
| `SD_COMPOSITE_DENOISING_STRENGTH` | `0.75` | 7.6 |

Shared: `CLAUDE_BIN` (8), for the Claude CLI test (7.3).

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- Adding providers or models from the screen; several keys per provider; key rotation.
- Credit, cost or quota tracking.
- Installing or starting the local servers — the user runs Stable Diffusion WebUI / Forge and the adapters.
- Suno or any provider reached through an unofficial gateway.
- OpenAI video — the Sora 2 API was shut down on 2026-09-24.
- Meta Muse Image and Muse Video — Meta offers no public API for them.
- Extending a clip on the provider's side (Veo scene extension, Omni Flash extend); a long scene is joined
  from segments (7.1).
