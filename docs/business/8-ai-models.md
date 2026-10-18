# 8. Mô hình AI (AI Models)

> One file = one domain. Every section below belongs to the **AI Models** domain.

Says which AI model reads and writes for the app at each AI step, and what it looks at when it picks the
key moments of a video. Four settings decide it — the first three in the `AI models` tab of `/settings`,
the last in its `Film Clone` tab (6.2):

| Setting | Values | Decides |
|---|---|---|
| `aiModel` | a provider and one of its models (8.1); default Claude CLI with the CLI default model | the model of every AI step whose group has no model of its own |
| `aiStepModels` | per step group: `null` (same as `aiModel`) or a provider and one of its models | the model of that group's steps (8.1) |
| `inputMode` | `subtitles` (default) \| `whole_video` | what the model sees in `picking_moments` of a Video to Markdown or Film Analysis job: the transcript only, or the transcript and one frame per second (8.3) |
| `filmCloneInputMode` | `subtitles` (default) \| `whole_video` | the same, for the stage 1 job of a Film Clone |

Every later call — prompt passes, assets, shots, localization, scripts — reads the video notes and the
captured frames, never the video, whatever the settings say.

- Persona: the same single local user as domain 1.
- Entities: none of its own. The settings are `AppSetting` keys (6.1). A job keeps a copy of its input mode
  in `Job.options.inputMode` (1.1); jobs, clones and episodes keep the model each AI step used in `ai_used` (8.1).
- Providers: Claude through the `claude` CLI; Gemini through the Gemini API with the key of the `google`
  provider; OpenAI through the OpenAI API with the key of the `openai` provider (domain 7). The models are
  those of the `analysis` catalog (7.5).

## 8.1 Model of a step

### Step groups

| Group (`aiStepModels` key) | Screen label | AI steps | Prompts (2.2) |
|---|---|---|---|
| `moments` | `Key moments` | `picking_moments` of every job — Video to Markdown (1.5), Film Analysis (3.2), the stage 1 job of a Film Clone (5.1) | `videoToMarkdown` |
| `filmAnalysis` | `Film analysis` | the three prompt passes (3.3) | `characterImage`, `characterVoice`, `scene` |
| `filmScript` | `Film script` | an episode's `writing_script` (4.2) | `filmScript` |
| `filmClone` | `Film clone` | `extracting_assets`, `analyzing_shots`, `proposing`, `writing_script` (5.2–5.4) | `cloneAssets`, `cloneShots`, `cloneLocalization`, `cloneScript` |

### Values

A model value is `{ "provider", "model" }`:

| `provider` | `model` |
|---|---|
| `claude_cli` | an id of the `claude_cli` `analysis` catalog (7.5); `default` = the CLI's own default |
| `google` | an id of the `google` `analysis` catalog |
| `openai` | an id of the `openai` `analysis` catalog |

- `aiModel` defaults to `{ "provider": "claude_cli", "model": "default" }`.
- `aiStepModels` defaults to every group `null`; a missing group reads `null`.
- The model of a step = its group's value in `aiStepModels`; `null` → `aiModel`.

| Rule (`PATCH /settings`, 6.1) | Result |
|---|---|
| `aiModel` is an object whose `provider` is one of the three and whose `model` is in that provider's catalog | 400 `Invalid value for 'aiModel'` |
| `aiStepModels` is an object whose keys are among the four groups and whose values are `null` or a model value as above | 400 `Invalid value for 'aiStepModels'` |

A model whose provider is not set up (7.1) can be saved; creating a run that needs it answers 409 (below).

### When the model is read

- When each call starts. A change applies to every call that starts afterwards, pending runs included: a
  Film Clone can find its assets with one model and write its script with another; a failed step resumed or
  rerun after a change runs on the new model.
- In `whole_video` the model is read once when `picking_moments` starts; every window uses it (8.3).
- The input mode is not read this way: it is copied into `Job.options.inputMode` at creation (1.1) —
  `inputMode` for a Video to Markdown or Film Analysis job, `filmCloneInputMode` for the stage 1 job of a Film
  Clone — and a job reads only its copy. A job without it uses `subtitles`.

### Check at creation

Every creation route runs one more check, right after the prompt preset check: the provider of the model of
each step group the run uses is set up (7.1).

| Route | Groups |
|---|---|
| `POST /jobs/video-to-markdown`, `/jobs/youtube-to-markdown` | `moments` |
| `POST /jobs/film-analysis`, `/jobs/youtube-film-analysis` | `moments`, `filmAnalysis` |
| `POST /jobs/{id}/film-analysis-rerun` | `filmAnalysis` |
| `POST /film-clones`, `/film-clones/youtube` | `moments`, `filmClone` |
| `POST /films/projects/{id}/episodes` | `filmScript` |

| Rule | Result |
|---|---|
| The provider of a checked group's model is not set up | 409 `{provider name} is not set up — open Settings` |

`claude_cli` is always set up (7.1): a CLI that is missing or signed out fails the call itself (8.2).

A call that starts while the provider of its model is not set up — the key was removed or became unreadable,
or the setting changed — fails its step with `{provider name} is not set up — open Settings`; the user fixes
the key or the setting and resumes.

### What a run records

When the call of an AI step starts, the run stores the model in `ai_used`, a JSON object keyed by step:
`{ "{step}": { "provider", "model" } }`. A step that runs again overwrites its entry.

| Run | Field | Steps |
|---|---|---|
| Job (1.1) — Video to Markdown, Film Analysis, a rerun, the stage 1 job of a Film Clone | `jobs.ai_used` | `picking_moments`, `writing_character_image_prompts`, `writing_character_voice_prompts`, `writing_scene_prompts` |
| Film Clone (5.1) | `film_clones.ai_used` | `extracting_assets`, `analyzing_shots`, `proposing`, `writing_script` |
| Episode (4.2) | `film_episodes.ai_used` | `writing_script` |

## 8.2 Calling a model

A call has the same parts whatever the provider: the prompt of the step (domain 2) as the system prompt, one
user message of text parts and images — each image after a text part naming its path or time — and, for a
structured step, a JSON schema.

No provider gets a tool: the message carries caption text and notes taken from the video, so the call must
not be able to read files, run commands or code, or search the web.

### Images

- Before any provider gets an image, the app scales it so its longer side is at most `AI_IMAGE_MAX_SIDE_PX`,
  never upscaled, and encodes it as JPEG at quality `AI_IMAGE_JPEG_QUALITY`. Only the copy sent changes; the
  frames on disk stay as captured.
- Gemini takes at most 20 MB of inline data per call. A Gemini call whose request is larger after scaling is
  not sent: the step fails with `gemini takes at most 20 MB per call; this call is {n} MB — lower Max frames
  or pick another model`, `{n}` with one decimal.

### Claude CLI

- `claude -p`, run in the system temp folder outside the repo, with no tool (`--tools ""`), no session
  persistence and no settings files (`--setting-sources ""`), so the machine's own hooks, plugins and
  `CLAUDE.md` never reach the prompt; `--model {model}`, left out for `default`.
- The prompt goes in `--system-prompt`; the schema in `--json-schema`. The message goes on stdin: plain text
  when it has no image, one stream-json user event when it has images.
- An API error 5xx is retried by the CLI itself (10 times over about 3 minutes); the app adds no retry.
- Film Clone calls add `--include-partial-messages`, so the output streams while Claude writes (5.1).

### Gemini

- `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse`, the
  key in the `x-goog-api-key` header.
- `systemInstruction` = the prompt; one `user` content with the text parts and each image as an
  `inlineData` JPEG part; a schema → `generationConfig.responseMimeType = application/json` and
  `responseJsonSchema`. No `tools`.
- The answer is the text of every streamed chunk, joined. Each chunk is a sign of life (5.1).

### OpenAI

- `POST https://api.openai.com/v1/responses`, the key in the `Authorization: Bearer` header; `stream: true`,
  `store: false`, no `tools`.
- `instructions` = the prompt; `input` = one `user` message with each text part as `input_text` and each
  image as `input_image` with a `data:image/jpeg;base64,…` URL; a schema → `text.format` =
  `{ "type": "json_schema", "name": "reply", "schema": …, "strict": false }`.
- The answer is the `delta` of every `response.output_text.delta` event, joined. Each event is a sign of
  life (5.1). The stream ends with `response.completed`.

### Gemini and OpenAI

- The key is read when the call starts.
- No retry: any error fails the step.
- The key is never written to logs, errors, jobs, clones or episodes.

### Answers

| Step | Claude CLI | Gemini, OpenAI |
|---|---|---|
| Structured — moments, assets, shots, localization, scripts | `structured_output` of the final result event | the joined text, parsed as JSON |
| Markdown — the three Film Analysis passes | `result` of the final result event, trimmed | the joined text, trimmed |

### Failures

`{ai}` = `claude`, `gemini` or `openai`.

| Failure | `error_message` |
|---|---|
| Claude: a reply line is not JSON · Gemini, OpenAI: the answer of a structured step is not JSON | `{ai} returned output that is not JSON` |
| Claude: the CLI reports an error, an API error 5xx after its retries included · Gemini, OpenAI: an HTTP status other than 2xx, `{message}` = its `error.message` · OpenAI: a `response.failed` or `error` event, `{message}` = its error message | `{ai} failed: {message}`, e.g. `gemini failed: Resource has been exhausted` |
| Claude CLI exits with an error and no result | `claude exited with {code}: {stderr}` |
| Claude, a Markdown step: no result event | `claude returned no result` |
| Gemini: no text, the prompt or the answer blocked — `{reason}` = `promptFeedback.blockReason` or the last `finishReason` | `gemini returned no answer: {reason}`, e.g. `gemini returned no answer: SAFETY` |
| OpenAI: no text — `{reason}` = `incomplete_details.reason`, or `refusal` when the model refused | `openai returned no answer: {reason}`, e.g. `openai returned no answer: content_filter` |
| Structured step without structured output — for Claude, no result event included | `{ai} returned no structured output` |
| Markdown step with a blank answer | `{ai} returned an empty answer` |
| Gemini request over 20 MB (§ Images) | `gemini takes at most 20 MB per call; this call is {n} MB — lower Max frames or pick another model` |
| Longer than the step's limit (below) | `{ai} timed out after {N}s` |
| Film Clone: no output for `CLONE_AI_SILENCE_SEC` | `{ai} stopped responding for {N}s` |
| The provider of the step's model is not set up when the call starts | `{provider name} is not set up — open Settings` |

Each step keeps its own checks on the parsed answer (1.5, 3.3, 4.2, 5.2–5.4), with `{ai}` in their
messages.

### Limits per step

| Step | Limit | Section |
|---|---|---|
| `picking_moments` | `AI_MOMENTS_TIMEOUT_SEC` per call — per window in `whole_video` | 1.5, 8.3 |
| Film Analysis passes | `FILM_PROMPT_TIMEOUT_SEC` | 3.3 |
| Film Studio `writing_script` | `FILM_SCRIPT_TIMEOUT_SEC` | 4.2 |
| Film Clone stages 2–4 | `CLONE_AI_SILENCE_SEC` without output, `CLONE_AI_MAX_RUN_SEC` in all | 5.1 |

These keys apply to every provider. AI calls run in the batch worker one at a time and do not count toward a
provider's `max_concurrent`, `min_interval_s` or queue line (7.1).

### Activity

While a Film Clone call runs, the clone detail carries `aiActivity` — `{ "provider", "model", "label",
"startedAt", "lastOutputAt" }` — kept in memory; an API restart clears it (5.1, 5.6).

## 8.3 Picking key moments — input modes

`picking_moments` (1.5) asks the model for at most `M` key moments: `MAX_MOMENTS` for Video to Markdown,
⌊max frames ÷ 2⌋ for Film Analysis and Film Clone. Both modes use the job's `videoToMarkdown` prompt, the
reply shape of 2.2 and the normalising of 1.5.

| Mode | The model sees | Calls |
|---|---|---|
| `subtitles` | the transcript, one line per segment | one (1.5) |
| `whole_video` | the transcript and one frame per second, a window at a time | one per window |

### Steps in `whole_video`

The transcript is still required: a video with no speech or no usable captions fails as in 1.2 and 1.4.

| # | Uploaded file | YouTube link |
|---|---|---|
| 1 | `extracting_audio` | `fetching_transcript` |
| 2 | `transcribing` | `downloading_video` |
| 3 | `sampling_frames` | `sampling_frames` |
| 4 | `picking_moments` | `picking_moments` |
| 5 … | the steps after `picking_moments` of the job type (1.1, 3.1, 5.1) | the same, without a second `downloading_video` |

YouTube downloads before `picking_moments` here, because the frames come from the video.

### `sampling_frames`

- One JPEG per second of the video — the uploaded file, or `source.mp4` — at 0 s, 1 s, 2 s … up to
  duration − 500 ms, width ≤ `SAMPLE_FRAME_WIDTH`, never upscaled; one `ffmpeg` pass limited to
  `MEDIA_TIMEOUT_SEC`.
- Saved as `storage/{job-id}/samples/sample-{NNNNN}.jpg`, `{NNNNN}` = the second, zero-padded.
- An `ffmpeg` error or timeout → `failed` with `Frame sampling failed: {error}`.
- `samples/` is emptied before sampling starts and deleted as soon as `picking_moments` ends, whether it
  succeeds or fails. The frames of the result are those `capturing_frames` takes (1.5), not the samples.

### Windows

- `W` = the images per call of the provider of the step's model: `CLAUDE_MAX_IMAGES_PER_CALL`,
  `GEMINI_MAX_IMAGES_PER_CALL` or `OPENAI_MAX_IMAGES_PER_CALL`. Window `k` = 0, 1, 2 … holds the samples of
  seconds `k × W` to `(k + 1) × W − 1`; `S` samples make ⌈S ÷ W⌉ windows.
- One call per window, in time order, with the step's prompt and schema. The user message, written by the
  app:
  - `This part of the video runs from {start} to {end}. Choose at most {m} key moments in it. Set atMs to
    the time of the frame or the line where the moment begins.` — `{start}` = `k × W` s, `{end}` = the
    smaller of `(k + 1) × W` s and the duration, both formatted as in 1.6; `{m}` = max(1, ⌈M × window
    seconds ÷ video seconds⌉).
  - `Transcript:`, then the segments that start inside the window as `[{start_ms}ms] {text}`, or
    `(no speech in this part)`.
  - `Frames:`, then every sample of the window, each image after the text `[{ms}ms]`.
- Merge: the moments of every window together; `title` and `summary` from the reply of window 0. Then the
  normalising of 1.5 — clamp, blank titles, 3 s gap, the first `M`.
- A failing window fails the step; the moments of earlier windows are not kept.

## 8.4 Screens

### Group "Text" of the `AI models` tab (6.2)

| Element | Detail |
|---|---|
| `All steps` | one select of every model of the `analysis` catalog (7.5), grouped under `Claude CLI`, `Google AI`, `OpenAI`, each option the model label; hint `The model of every step set to Same as all steps.` |
| `Apply to all steps` | button next to `All steps`; sets the four rows below to `Same as all steps`; disabled when they all are. Saved with the tab's `Save` |
| `Key moments`, `Film analysis`, `Film script`, `Film clone` | one select each: `Same as all steps ({model label})` first, then the models as in `All steps`. Hints: `Picks the key moments of every video.` · `Writes the character image, voice and scene prompts.` · `Writes the scripts of Film Studio episodes.` · `Finds assets and shots, proposes changes and writes Film Clone scripts.` |
| Warning | under `All steps`, or under a step row with a model of its own, when that model's provider is not set up: `{provider name} is not set up — add its key in General.`, `General` linking to `?tab=general&provider={id}` |
| `Input mode` | `Subtitles` (default) \| `Whole video`; hint `For Video to Markdown and Film Analysis. Subtitles: the model reads the transcript to pick key moments. Whole video: it also sees one frame per second — slower, with more calls on long videos.` Film Clone has its own, in the `Film Clone` tab (6.2) |

### Creation forms

Panels `New conversion` (1.7), `New analysis` (3.6) and `New clone` (5.6) show, above the submit button, a
read-only line `AI: {models} · Input: {Subtitles | Whole video}` and a link `Change` →
`/settings?tab=ai-models`. On `New clone`, `Input` is `filmCloneInputMode` and is followed by its own link
`Change` → `/settings?tab=film-clone`. The `Rerun with another preset` and `Make a film` panels (3.6) and the
`New episode` panel (4.5) show `AI: {models}` with a link `Change` → `/settings?tab=ai-models`.

- `{models}` = the model label when every group the run uses (8.1 § Check at creation) has the same model;
  else `{group label} — {model label}` per group, joined by ` · `, e.g.
  `Key moments — Claude (CLI default) · Film analysis — Gemini 4 Argon`.
- A model whose provider is not set up is followed by `— not set up`, and the submit button is disabled with
  the hint `Add the {provider name} key in Settings → General.`

### Detail screens

- `/jobs/{id}` (1.7), `/film-analysis/{id}` (3.6) and `/film-clone/{id}` (5.6) add to their summary `AI` and
  `Input` (`Subtitles` \| `Whole video`; `—` for a rerun). `AI` lists `{step label}: {model label}` for every
  entry of `ai_used` in step order — for a clone, its stage 1 job's then its own; `—` before the first AI step
  starts. Step labels are those of 1.7, 3.6 and 5.6.
- The episode page (4.5) adds `AI` to its `Script` panel: the model `writing_script` used, or `—`.
- While a Film Clone call runs, its line reads `{model label} is working · …` (5.6), e.g.
  `Gemini 4 Argon is working · 01:12 · last output 3s ago`.

---

## API endpoints

No route of its own. It adds:

- `aiModel`, `aiStepModels`, `inputMode` and `filmCloneInputMode` to `GET /settings` and `PATCH /settings`,
  and the first three to `PATCH /settings/ai-models` (6).
- `options.inputMode` and `aiUsed` to `Job` (1.1); `aiUsed` to `Episode` (4.2) and `FilmClone` (5, list and
  detail); `aiActivity` to `FilmCloneDetail`. `aiUsed` = `{ "{step}": { "provider", "model", "label" } }`.
- 409 `{provider name} is not set up — open Settings` to the creation routes of 8.1.

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `CLAUDE_BIN` | `claude` | 8.2, the Claude CLI test (7.3) |
| `AI_IMAGE_MAX_SIDE_PX` | `480` | 8.2 |
| `AI_IMAGE_JPEG_QUALITY` | `60` | 8.2 |
| `CLAUDE_MAX_IMAGES_PER_CALL` | `100` | 8.3, the Film Analysis passes (3.3), Film Clone `extracting_assets` and `analyzing_shots` (5.2) |
| `GEMINI_MAX_IMAGES_PER_CALL` | `300` | as `CLAUDE_MAX_IMAGES_PER_CALL` |
| `OPENAI_MAX_IMAGES_PER_CALL` | `300` | as `CLAUDE_MAX_IMAGES_PER_CALL` |
| `SAMPLE_FRAME_WIDTH` | `512` | 8.3 |

Shared: `AI_MOMENTS_TIMEOUT_SEC` (1), `FILM_PROMPT_TIMEOUT_SEC`, `FILM_SCRIPT_TIMEOUT_SEC`,
`CLONE_AI_SILENCE_SEC`, `CLONE_AI_MAX_RUN_SEC` (5), `MEDIA_TIMEOUT_SEC`. The Gemini and OpenAI keys: the
`google` and `openai` providers (domain 7).

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- Sending the video file or a YouTube link to a model.
- A model or a mode chosen per run on the form.
- Retrying a failed Gemini or OpenAI call; falling back to another model.
- Picking moments from frames alone, for a video with no speech.
- Vendors other than Claude, Gemini and OpenAI; Claude through the Anthropic API; cost or token tracking.
