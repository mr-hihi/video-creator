# 8. Mô hình AI (AI Models)

> One file = one domain. Every section below belongs to the **AI Models** domain.

Says which AI model reads and writes for the app at each AI step, and what it looks at and listens to
when it reads a video. Five settings decide it — the first four in the `AI models` tab of `/settings`, the
last in its `Film Clone` tab (6.2):

| Setting | Values | Decides |
|---|---|---|
| `aiModel` | a provider and one of its models (8.1); default Claude CLI with the CLI default model | the model of every AI step whose group has no model of its own |
| `aiStepModels` | per step group: `null` (same as `aiModel`) or a provider and one of its models | the model of that group's steps (8.1) |
| `inputMode` | `subtitles` (default) \| `whole_video` | what a Video to Markdown job shows the model (8.3) |
| `filmAnalysisInputMode` | `subtitles` (default) \| `whole_video` \| `full_video` | what a Film Analysis job shows the model and lets it hear (8.3) |
| `filmCloneInputMode` | `subtitles` (default) \| `whole_video` | the same, for the stage 1 job of a Film Clone |

Only Gemini receives video or audio: the audio in `whole_video` for Film Analysis and Film Clone, the
compressed video in `full_video`. Every other call — the prompt passes outside `full_video`, assets, shots,
localization, scripts — reads the video notes and the captured frames.

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
| `audio` | `Audio` | `listening_to_audio` of a Film Analysis job or the stage 1 job of a Film Clone in `whole_video` (8.3) — Google AI only | `speakersAndSounds` |
| `filmAnalysis` | `Film analysis` | the three prompt passes (3.3) — Google AI only in `full_video` | `characterImage`, `characterVoice`, `scene` |
| `filmScript` | `Film script` | an episode's `writing_outline`, `writing_script` and `updating_story_bible` (4.2) | `filmOutline`, `filmScript`, `storyBible` |
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
| `aiStepModels` is an object whose keys are among the five groups and whose values are `null` or a model value as above | 400 `Invalid value for 'aiStepModels'` |

A model whose provider is not set up (7.1), or a model of another provider for a group that needs Google AI,
can be saved; creating a run that needs it answers 409 (below).

### When the model is read

- When each call starts. A change applies to every call that starts afterwards, pending runs included: a
  Film Clone can find its assets with one model and write its script with another; a failed step resumed or
  rerun after a change runs on the new model.
- In `whole_video` the model is read once when `picking_moments` starts, and once when `listening_to_audio`
  starts; every window or part of the step uses it (8.3). In `full_video` each pass reads it when it starts,
  and every part of the pass uses it.
- The input mode is not read this way: it is copied into `Job.options.inputMode` at creation (1.1) —
  `inputMode` for a Video to Markdown job, `filmAnalysisInputMode` for a Film Analysis job,
  `filmCloneInputMode` for the stage 1 job of a Film Clone — and a job reads only its copy. A job without it
  uses `subtitles`.

### Check at creation

Every creation route runs one more check, right after the prompt preset check: the provider of the model of
each step group the run uses is set up (7.1), and a group that needs Google AI has a `google` model.

| Route | Groups | Needs Google AI |
|---|---|---|
| `POST /jobs/video-to-markdown`, `/jobs/youtube-to-markdown` | `moments` | — |
| `POST /jobs/film-analysis`, `/jobs/youtube-film-analysis` | `subtitles`: `moments`, `filmAnalysis` · `whole_video`: plus `audio` · `full_video`: `filmAnalysis` only | `audio` in `whole_video`; `filmAnalysis` in `full_video` |
| `POST /jobs/{id}/film-analysis-rerun` | `filmAnalysis` | `filmAnalysis` when the source is `full_video` |
| `POST /film-clones`, `/film-clones/youtube` | `moments`, `filmClone`; plus `audio` in `whole_video` | `audio` in `whole_video` |
| `POST /films/projects/{id}/episodes` | `filmScript` | — |

| Rule | Result |
|---|---|
| The provider of a checked group's model is not set up | 409 `{provider name} is not set up — open Settings` |
| A group that needs Google AI has a model of another provider | 409 `{group label} needs a Google AI model — open Settings`, e.g. `Audio needs a Google AI model — open Settings` |

`claude_cli` is always set up (7.1): a CLI that is missing or signed out fails the call itself (8.2).

A call that starts while the provider of its model is not set up — the key was removed or became unreadable,
or the setting changed — fails its step with `{provider name} is not set up — open Settings`; a call that
needs Google AI and starts on another provider's model fails its step with `{group label} needs a Google AI
model — open Settings`. The user fixes the key or the setting and resumes.

### What a run records

When the call of an AI step starts, the run stores the model in `ai_used`, a JSON object keyed by step:
`{ "{step}": { "provider", "model" } }`. A step that runs again overwrites its entry.

| Run | Field | Steps |
|---|---|---|
| Job (1.1) — Video to Markdown, Film Analysis, a rerun, the stage 1 job of a Film Clone | `jobs.ai_used` | `listening_to_audio`, `picking_moments`, `writing_character_image_prompts`, `writing_character_voice_prompts`, `writing_scene_prompts` |
| Film Clone (5.1) | `film_clones.ai_used` | `extracting_assets`, `analyzing_shots`, `proposing`, `writing_script` |
| Episode (4.2) | `film_episodes.ai_used` | `writing_outline`, `writing_script`, `updating_story_bible` |

## 8.2 Calling a model

A call has the same parts whatever the provider: the prompt of the step (domain 2) as the system prompt, one
user message of text parts and images — each image after a text part naming its path or time; for Gemini
also audio or video files (§ Video and audio) — and, for a structured step, a JSON schema.

No provider gets a tool: the message carries caption text and notes taken from the video, so the call must
not be able to read files, run commands or code, or search the web.

### Images

- Before any provider gets an image, the app scales it so its longer side is at most `AI_IMAGE_MAX_SIDE_PX`,
  never upscaled, and encodes it as JPEG at quality `AI_IMAGE_JPEG_QUALITY`. Only the copy sent changes; the
  frames on disk stay as captured.
- Gemini takes at most 20 MB of inline data per call. A Gemini call whose request is larger after scaling is
  not sent: the step fails with `gemini takes at most 20 MB per call; this call is {n} MB — lower Max frames
  or pick another model`, `{n}` with one decimal.

### Video and audio

Only Gemini receives them — the audio parts of `listening_to_audio` and the video parts of `full_video` (8.3).

- Each part goes through the Gemini Files API: a resumable upload, then the app waits until the file is
  `ACTIVE`. The call names it as a `fileData` part (`mimeType`, `fileUri`) after a text part with its time
  range, e.g. `[audio 30:00–1:00:00]`. Uploaded files do not count toward the 20 MB of § Images.
- Video calls send `generationConfig.mediaResolution` = `MEDIA_RESOLUTION_LOW` and no `videoMetadata.fps`, so
  Gemini reads one frame per second whatever the frame rate of the file.
- Each part is uploaded right before the call that sends it, and the app deletes it from Gemini right after
  that call, whether the call succeeds or fails; a file that ends `FAILED` is deleted too. A failed delete is
  logged and never fails the step.

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
- `systemInstruction` = the prompt; one `user` content with the text parts, each image as an
  `inlineData` JPEG part and each audio or video part as a `fileData` part; a schema →
  `generationConfig.responseMimeType = application/json` and `responseJsonSchema`. No `tools`.
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
| Gemini: an upload fails, or an uploaded file ends `FAILED` instead of `ACTIVE` | `gemini could not take the {audio \| video}: {message or state}` |
| Longer than the step's limit (below) | `{ai} timed out after {N}s` |
| Film Clone: no output for `CLONE_AI_SILENCE_SEC` | `{ai} stopped responding for {N}s` |
| The provider of the step's model is not set up when the call starts | `{provider name} is not set up — open Settings` |
| A step that needs Google AI starts on another provider's model (8.1) | `{group label} needs a Google AI model — open Settings` |

Each step keeps its own checks on the parsed answer (1.5, 3.3, 4.2, 5.2–5.4), with `{ai}` in their
messages.

### Limits per step

| Step | Limit | Section |
|---|---|---|
| `picking_moments` | `AI_MOMENTS_TIMEOUT_SEC` per call — per window in `whole_video` | 1.5, 8.3 |
| `listening_to_audio` | `AI_AUDIO_TIMEOUT_SEC` per part, the upload included | 8.3 |
| Film Analysis passes | `FILM_PROMPT_TIMEOUT_SEC` per call — per part in `full_video`, the upload included | 3.3 |
| Film Studio `writing_outline`, `writing_script`, `updating_story_bible` | `FILM_SCRIPT_TIMEOUT_SEC` per call — per part in `writing_script` | 4.2 |
| Film Clone stages 2–4 | `CLONE_AI_SILENCE_SEC` without output, `CLONE_AI_MAX_RUN_SEC` in all | 5.1 |

These keys apply to every provider. AI calls run in the batch worker one at a time and do not count toward a
provider's `max_concurrent`, `min_interval_s` or queue line (7.1).

### Activity

While a Film Clone call runs, the clone detail carries `aiActivity` — `{ "provider", "model", "label",
"startedAt", "lastOutputAt" }` — kept in memory; an API restart clears it (5.1, 5.6).

## 8.3 Input modes

What a job shows the model, and lets it hear, before its results are written.

| Mode | Screen label | Video to Markdown | Film Analysis | Film Clone stage 1 |
|---|---|---|---|---|
| `subtitles` | `Subtitles` | `picking_moments` reads the transcript, one call (1.5) | as Video to Markdown | as Video to Markdown |
| `whole_video` | `Whole video` for Video to Markdown; `Frame image + audio` for Film Analysis and Film Clone | `picking_moments` also sees one frame per second, one call per window (§ Windows) | as Video to Markdown, plus `listening_to_audio`: Gemini hears the audio, tells the speakers apart and marks the sounds, which become frames (3.2) | as Film Analysis |
| `full_video` | `Full video` | — | no transcript, moments or frames: each prompt pass gets the compressed video (§ Full video, 3.3) | — |

`picking_moments` asks for at most `M` key moments: `MAX_MOMENTS` for Video to Markdown, ⌊max frames ÷ 2⌋
for Film Analysis and Film Clone, with the job's `videoToMarkdown` prompt, the reply shape of 2.2 and the
normalising of 1.5.

### Steps in `whole_video`

The transcript is still required: a video with no speech or no usable captions fails as in 1.2 and 1.4.

| # | Uploaded file | YouTube link |
|---|---|---|
| 1 | `extracting_audio` | `fetching_transcript` |
| 2 | `transcribing` | `downloading_video` |
| 3 | `listening_to_audio` — Film Analysis and Film Clone only | the same |
| 4 | `sampling_frames` | `sampling_frames` |
| 5 | `picking_moments` | `picking_moments` |
| 6 … | the steps after `picking_moments` of the job type (1.1, 3.1, 5.1) | the same, without a second `downloading_video` |

YouTube downloads before `picking_moments` here, because the frames come from the video; a Film Analysis or
Film Clone job downloads the audio too (1.3).

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

### `listening_to_audio`

Film Analysis and Film Clone in `whole_video`. One call of the `audio` model — Google AI only (8.1) — per
part, with the job's `speakersAndSounds` prompt (2.2) and a JSON schema.

- Parts: the audio of the uploaded file or of `source.mp4`, cut into parts of `AI_MEDIA_PART_SEC` seconds —
  the last one shorter — each encoded as mono AAC, in one `ffmpeg` pass limited to `MEDIA_TIMEOUT_SEC`, and
  saved as `storage/{job-id}/audio/part-{NN}.m4a`. An `ffmpeg` error or timeout → `failed` with `Audio
  preparation failed: {error}`. `audio/` is emptied before the step starts and deleted as soon as it ends,
  whether it succeeds or fails.
- One call per part, in time order. The user message, written by the app:
  - `This part of the film runs from {start} to {end}.` — formatted as in 1.6.
  - From the second part on, when speakers were found: `Speakers so far:`, one `- {name} — {voice}` per
    speaker, then `Use the same name for the same voice.`
  - `Transcript:`, then the segments that start inside the part as `[{start_ms}ms] {text}`, or
    `(no speech in this part)`.
  - The part as audio (8.2).
- Reply shape: `speakers[] { name, voice }`, `lines[] { atMs, speaker }`, `sounds[] { atMs, kind,
  description }`, `kind` one of the four below.
- Normalising, over the replies of every part together:
  1. Speakers: trimmed; a blank name is dropped; name cut to 100 characters, voice to 500; a repeat,
     case-insensitive, keeps the first.
  2. Lines: an `atMs` that is not the start of a segment of that part, or a blank `speaker`, is dropped; the
     first entry per segment is kept; a speaker missing from `speakers` is added with a blank voice.
  3. Sounds: an unknown `kind` or a blank `description` is dropped; `atMs` is clamped to the part and to
     `[0, duration − 500 ms]`; `description` is cut to 200 characters; sorted by time, a sound less than 3 s
     after the previous kept one is dropped.
  4. Finding no speaker, line or sound is not an error.
- The result is saved as `storage/{job-id}/audio-notes.json` for `capturing_frames` and `writing_markdown`
  (3.2); a requeued job writes it again.
- A failing part fails the step; nothing of the earlier parts is kept.

| `kind` | Label | Marks |
|---|---|---|
| `action` | Action | a sound of what a character does — footsteps, a door, a blow, crying, laughter |
| `silence` | Silence | the start of 3 s or more without speech or sound |
| `ambient` | Ambient | a sound of the surroundings — an animal, rain, wind, traffic, a crowd |
| `music` | Music | music that starts or changes mood |

### Full video

Film Analysis in `full_video`. No transcript is needed: a film with no speech, or a YouTube video without
usable captions, still runs. Its steps: 3.1.

`compressing_video`:

- `ffprobe` reads the duration. One `ffmpeg` pass, limited to `MEDIA_TIMEOUT_SEC`, writes the uploaded file,
  or `source.mp4` downloaded with its audio (1.3), as H.264 video with mono AAC audio: longer side at most
  `FULL_VIDEO_MAX_SIDE_PX`, never upscaled; frame rate at most `FULL_VIDEO_MAX_FPS`, never raised; cut into
  parts of `AI_MEDIA_PART_SEC` seconds, the last one shorter.
- Saved as `storage/{job-id}/compressed/part-{NN}.mp4` and kept until the job is deleted, so a rerun can
  send them again (3.4).
- An `ffmpeg` error or timeout → `failed` with `Video compression failed: {error}`.

Each prompt pass then sends the parts to the `filmAnalysis` model — Google AI only (8.1) — one call per part
(3.3). The frame rate cap only makes the files smaller: Gemini reads one frame per second (8.2).

## 8.4 Screens

### Group "Text" of the `AI models` tab (6.2)

| Element | Detail |
|---|---|
| `All steps` | one select of every model of the `analysis` catalog (7.5), grouped under `Claude CLI`, `Google AI`, `OpenAI`, each option the model label; hint `The model of every step set to Same as all steps.`; help `Every step whose row below is Same as all steps uses this model. Claude CLI runs the signed-in claude command; Google AI and OpenAI need their key in General.` |
| `Apply to all steps` | button next to `All steps`; sets the five rows below to `Same as all steps`; disabled when they all are. Saved with the tab's `Save` |
| `Key moments`, `Audio`, `Film analysis`, `Film script`, `Film clone` | one select each: `Same as all steps ({model label})` first, then the models as in `All steps`. Hints: `Picks the key moments of every video.` · `Hears the speakers and sounds in Frame image + audio mode. Google AI only.` · `Writes the character image, voice and scene prompts. Google AI only in Full video mode.` · `Writes the scripts of Film Studio episodes.` · `Finds assets and shots, proposes changes and writes Film Clone scripts.` Help: `Picks the moments that get a frame, from the transcript — and from one frame per second in Whole video or Frame image + audio mode. Used by Video to Markdown, Film Analysis and Film Clone.` · `Listens to the film's audio in Frame image + audio mode of Film Analysis and Film Clone: tells the speakers apart by voice and marks actions, silences, ambient sounds and music, which add frames. Must be a Google AI model.` · `Writes the character image, character voice and scene prompts of Film Analysis. In Full video mode it watches the compressed film itself, so it must be a Google AI model.` · `Writes the outline, the part scripts and the story bible of Film Studio episodes.` · `Finds the assets and shots of a film, proposes the localized changes and writes the Film Clone script.` |
| Warning | under `All steps`, or under a step row with a model of its own, when that model's provider is not set up: `{provider name} is not set up — add its key in General.`, `General` linking to `?tab=general&provider={id}` |
| Google AI warning | under `Audio` when its model is not a `google` one and the saved `filmAnalysisInputMode` or `filmCloneInputMode` is `whole_video`: `Frame image + audio needs a Google AI model here.`; under `Film analysis` when its model is not a `google` one and the saved `filmAnalysisInputMode` is `full_video`: `Full video needs a Google AI model here.` — the models as on screen, the input modes as saved |
| `Video to Markdown input` | `Subtitles` (default) \| `Whole video`; hint `What the model sees to pick key moments.`; help `Subtitles: the model reads only the transcript — the fastest. Whole video: it also sees one frame per second, so it can pick moments without speech — slower, with more calls on long videos.` Film Analysis and Film Clone have their own `Input mode`, in their tabs (6.2) |

### Google AI warning of the `Film Analysis` and `Film Clone` tabs (6.2)

Under `Input mode`, from the value on screen and the models as saved:

| Tab | Input mode | Shown when | Warning |
|---|---|---|---|
| `Film Analysis` | `Frame image + audio` | the `Audio` model is not a `google` one | `Frame image + audio needs a Google AI model here.` |
| `Film Analysis` | `Full video` | the `Film analysis` model is not a `google` one | `Full video needs a Google AI model here.` |
| `Film Clone` | `Frame image + audio` | the `Audio` model is not a `google` one | `Frame image + audio needs a Google AI model here.` |

### Creation forms

Panels `New conversion` (1.7), `New analysis` (3.6) and `New clone` (5.6) show, above the submit button, a
read-only line `AI: {models} · Input: {mode label}` and a link `Change` → `/settings?tab=ai-models`; the mode
label is that of 8.3 for the job's own setting — `inputMode`, `filmAnalysisInputMode` or
`filmCloneInputMode`. On `New analysis` and `New clone`, `Input` is followed by its own link `Change` →
`/settings?tab=film-analysis` or `/settings?tab=film-clone`. The `Rerun with another preset` panel and the `Send to Film Studio` dialog (3.6)
and the `New episode` panel (4.5) show `AI: {models}` with a link `Change` → `/settings?tab=ai-models`.

- `{models}` = the model label when every group the run uses (8.1 § Check at creation) has the same model;
  else `{group label} — {model label}` per group, joined by ` · `, e.g.
  `Key moments — Claude (CLI default) · Film analysis — Gemini 4 Argon`.
- A model whose provider is not set up is followed by `— not set up`, and the submit button is disabled with
  the hint `Add the {provider name} key in Settings → General.`
- A group that needs Google AI (8.1) with a model of another provider makes the line list every group as
  `{group label} — {model label}`, that one followed by `— needs Google AI`, and the submit button is
  disabled with the hint `Pick a Google AI model for {group label} in Settings → AI models.`

### Detail screens

- `/jobs/{id}` (1.7), `/film-analysis/{id}` (3.6) and `/film-clone/{id}` (5.6) add to their summary `AI` and
  `Input` (the mode label of 8.3; `—` for a rerun, except `Full video` for a rerun of a `full_video`
  analysis). `AI` lists `{step label}: {model label}` for every
  entry of `ai_used` in step order — for a clone, its stage 1 job's then its own; `—` before the first AI step
  starts. Step labels are those of 1.7, 3.6 and 5.6.
- The episode page (4.5) adds `AI` to its `Script` panel: `{step label}: {model label}` for every entry of
  `ai_used` in step order, with the stage labels of 4.5, or `—` before the first AI step starts.
- While a Film Clone call runs, its line reads `{model label} is working · …` (5.6), e.g.
  `Gemini 4 Argon is working · 01:12 · last output 3s ago`.

---

## API endpoints

No route of its own. It adds:

- `aiModel`, `aiStepModels`, `inputMode`, `filmAnalysisInputMode` and `filmCloneInputMode` to
  `GET /settings` and `PATCH /settings`, and the first four to `PATCH /settings/ai-models` (6).
- `options.inputMode` and `aiUsed` to `Job` (1.1); `aiUsed` to `Episode` (4.2) and `FilmClone` (5, list and
  detail); `aiActivity` to `FilmCloneDetail`. `aiUsed` = `{ "{step}": { "provider", "model", "label" } }`.
- 409 `{provider name} is not set up — open Settings` and 409 `{group label} needs a Google AI model — open
  Settings` to the creation routes of 8.1.

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
| `AI_MEDIA_PART_SEC` | `1800` | 8.3 — the longest audio or video part one Gemini call gets |
| `AI_AUDIO_TIMEOUT_SEC` | `900` | 8.2, 8.3 — `listening_to_audio`, per part |
| `FULL_VIDEO_MAX_SIDE_PX` | `480` | 8.3 § Full video |
| `FULL_VIDEO_MAX_FPS` | `24` | 8.3 § Full video |

Shared: `AI_MOMENTS_TIMEOUT_SEC` (1), `FILM_PROMPT_TIMEOUT_SEC`, `FILM_SCRIPT_TIMEOUT_SEC`,
`CLONE_AI_SILENCE_SEC`, `CLONE_AI_MAX_RUN_SEC` (5), `MEDIA_TIMEOUT_SEC`. The Gemini and OpenAI keys: the
`google` and `openai` providers (domain 7).

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- Sending a YouTube link to a model; sending audio or video to Claude CLI or OpenAI.
- Audio for Video to Markdown; the video file for any step but the Film Analysis passes in `full_video`.
- Cutting the audio or video at scene boundaries instead of every `AI_MEDIA_PART_SEC` seconds.
- A model or a mode chosen per run on the form.
- Retrying a failed Gemini or OpenAI call; falling back to another model.
- Picking moments from frames alone, for a video with no speech.
- Vendors other than Claude, Gemini and OpenAI; Claude through the Anthropic API; cost or token tracking.
