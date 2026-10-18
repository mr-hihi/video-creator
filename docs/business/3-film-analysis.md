# 3. Phân tích phim (Film Analysis)

> One file = one domain. Every section below belongs to the **Film Analysis** domain.

Reads a film — an uploaded file or a YouTube link — and writes three sets of English prompts: character
image prompts, character voice prompts, and prompts for similar shots. It first runs the Video to
Markdown pipeline (domain 1) to get video notes and frames, then three passes of the AI model (domain 8)
read the notes and look at the frames. Results are stored in the database and shown with a `Copy` button;
no `.md` file and no zip are produced.

| Source | Job type | Video notes from | Prompts |
|---|---|---|---|
| Uploaded file | `film_analysis` | 1.2 + 3.2 | 3.3 |
| YouTube link | `youtube_film_analysis` | 1.3 + 1.4 + 3.2 | 3.3 |
| Rerun of an analysis | `film_analysis_rerun` | copied from the source job (3.4) | 3.3 |

- Persona: the same single local user. Captcha on every creation route, switched off as in domain 1.
- Entities: `Job` (table `jobs`, 1.1) with the three types above; `JobOutput` (table `job_outputs`).
- Prompts come from a prompt preset (domain 2), copied into the job at creation (2.5); the input mode from
  the settings, copied likewise; the AI models are read when each call starts (8.1).
- External tools: as domain 1, plus `ffmpeg` scene detection.

## 3.1 Job, steps & outputs

### `options`

| Key | Types | Written at | Value |
|---|---|---|---|
| `language` | all | creation | as 1.2 / 1.3; a rerun copies the source's |
| `url`, `videoId`, `captionKind` | `youtube_film_analysis`; a rerun of one | as 1.3 | as 1.3; a rerun copies the source's |
| `maxFrames` | `film_analysis`, `youtube_film_analysis` | creation | integer 10–1000, default 1000 |
| `frameCounts` | all | `capturing_frames`; a rerun copies the source's | `{ "dialogue": n, "scene": m }` |
| `preset`, `prompts` | all | creation | 2.5 |
| `inputMode` | `film_analysis`, `youtube_film_analysis` | creation | 8.1 |
| `rerunOfJobId` | `film_analysis_rerun` | creation | the source job `id` |

### Steps per type

`inputMode` = `subtitles`:

| # | `film_analysis` | `youtube_film_analysis` | `film_analysis_rerun` |
|---|---|---|---|
| 1 | `extracting_audio` | `fetching_transcript` | `writing_character_image_prompts` |
| 2 | `transcribing` | `picking_moments` | `writing_character_voice_prompts` |
| 3 | `picking_moments` | `downloading_video` | `writing_scene_prompts` |
| 4 | `detecting_scenes` | `detecting_scenes` | |
| 5 | `capturing_frames` | `capturing_frames` | |
| 6 | `writing_markdown` | `writing_markdown` | |
| 7 | `writing_character_image_prompts` | `writing_character_image_prompts` | |
| 8 | `writing_character_voice_prompts` | `writing_character_voice_prompts` | |
| 9 | `writing_scene_prompts` | `writing_scene_prompts` | |

- Steps shared with domain 1 behave as 1.2–1.5, failures included.
- `inputMode` = `whole_video` adds `sampling_frames` right before `picking_moments`, and YouTube downloads
  before both (8.3).
- Status workflow, worker, single queue and requeue on restart: as 1.1. A requeued job runs from its
  first step and replaces its outputs.
- `done` and `failed` are final; a rerun (3.4) is the way to regenerate prompts.

### Data model — `JobOutput`

| Field | Type | Meaning |
|---|---|---|
| `job_id` | string(36) | → `jobs.id`; deleted with the job |
| `kind` | enum | `video_notes` \| `character_image_prompts` \| `character_voice_prompts` \| `scene_prompts` |
| `content` | long text | Markdown as written |
| `created_at` | datetime (UTC) | |

Primary key (`job_id`, `kind`).

| Step | Writes |
|---|---|
| `writing_markdown` | `video_notes`; frames stay at `storage/{job-id}/output/images/` |
| `writing_character_image_prompts` | `character_image_prompts` |
| `writing_character_voice_prompts` | `character_voice_prompts` |
| `writing_scene_prompts` | `scene_prompts` |

A job failing at a later step keeps the rows already written; the detail screen shows them (3.6).

## 3.2 Frames & video notes

`N` = `options.maxFrames`.

### `picking_moments`

As 1.5 with the job's `videoToMarkdown` prompt, asking for at most ⌊N ÷ 2⌋ moments and keeping at
most ⌊N ÷ 2⌋ after normalisation. These are the **dialogue** frames.

### `detecting_scenes`

- `ffmpeg` scene-change detection over the whole video — the uploaded file, or the downloaded
  `source.mp4` — with threshold `FILM_SCENE_THRESHOLD`, limited to `FILM_SCENE_TIMEOUT_SEC`.
- Result: the time of every visual cut, in ms. No cut is not an error.
- An `ffmpeg` error or timeout → `failed` with `Scene detection failed: {error}`.

### Merge (`capturing_frames`)

1. Keep every dialogue frame.
2. From the cuts, drop those within 3 s of a dialogue frame, those within 3 s after the previous kept
   cut, and those later than duration − 500 ms.
3. Slots = `N` − dialogue frames. More cuts than slots → keep `slots` cuts spread evenly: the cut at
   index ⌊i × cuts ÷ slots⌋ for i = 0 … slots − 1.
4. Kept cuts are **scene** frames, titled `Scene change`.
5. Capture every frame in time order as 1.5; `options.frameCounts` = the counts of both kinds.

### Video notes (`writing_markdown`)

- Built as 1.6, every frame being a moment: scene frames head `## {timestamp} — Scene change`;
  YouTube timestamps link to the second.
- Saved as the `video_notes` row; no `.md` file, no zip.

## 3.3 Prompt passes

| Step | Prompt from `options.prompts` | Output `kind` |
|---|---|---|
| `writing_character_image_prompts` | `characterImage` | `character_image_prompts` |
| `writing_character_voice_prompts` | `characterVoice` | `character_voice_prompts` |
| `writing_scene_prompts` | `scene` | `scene_prompts` |

- One call of the `filmAnalysis` model per step (8.1, 8.2), limited to `FILM_PROMPT_TIMEOUT_SEC`: system prompt = the
  job's prompt; one user message = the app-added parts of 2.2 — video notes, for voice and scene the
  `character_image_prompts` row, the frame line — then the frames under `output/images/`, each as an image
  after its path. A job with more frames than the images per call `W` of the model's provider
  (`CLAUDE_MAX_IMAGES_PER_CALL`, `GEMINI_MAX_IMAGES_PER_CALL` or `OPENAI_MAX_IMAGES_PER_CALL`, 8.3) sends `W`
  of them spread evenly: the frame at index ⌊i × frames ÷ W⌋ for i = 0 … W − 1. The video notes still list
  every frame. The video itself is never sent, whatever `inputMode` says.
- The Markdown answer, trimmed, is stored as is. Failures: 8.2.

## 3.4 Rerun with another preset

Regenerates the three prompt sets of an analysis with another preset, without reading the video again.

| # | Rule | Result |
|---|---|---|
| 1 | Captcha token valid (skipped when `CAPTCHA_ENABLED=false`) | 403 `Captcha verification failed` |
| 2 | Source job exists | 404 `Job {id} not found` |
| 3 | Source is one of the three film analysis types | 409 `Job {id} is not a film analysis` |
| 4 | Source is `done` or `failed` and has a `video_notes` row | 409 `Job {id} has no video notes to reuse` |
| 5 | `presetId` known (optional; default preset when absent) | 400 `Prompt preset {id} not found` |
| 6 | The provider of the `filmAnalysis` model is set up (8.1) | 409 `{provider name} is not set up — open Settings` |

- At creation the API copies the source's `video_notes` row and `output/images/` into the new job, so
  deleting the source later changes nothing.
- `source_filename` = the source's. `options` per 3.1.

## 3.5 Delete

`DELETE /jobs/{id}` removes the job row, its `job_outputs` rows and `storage/{job-id}/`.

| Rule | Result |
|---|---|
| Job exists | 404 `Job {id} not found` |
| Type is one of the three film analysis types | 409 `Only film analysis jobs can be deleted` |
| Status is `done` or `failed` | 409 `Job {id} is still running` |

- Reruns made from it keep their own copies; their `Rerun of` shows `(deleted)`.
- Film Studio episodes made from it keep their own copies (4.2); their `Source` shows `(deleted)`.

## 3.6 Screens

Header menu as in 1.7.

### `/film-analysis` — Film Analysis

**Panel "New analysis"**

| Element | Upload file (default) | YouTube link |
|---|---|---|
| Source switch | `Upload file` \| `YouTube link` — resets to `Upload file` on every visit | |
| Input | `Film` drop field, the 1.2 extensions | `YouTube link` text field, placeholder `https://www.youtube.com/watch?v=…` |
| Language select | `Spoken language` | `Caption language` |
| `Prompt preset` select | presets in 2.6 order, the default one preselected and labelled `{name} (default)`; link `Edit presets` → `/settings?tab=prompt-override&id={selected}` | same |
| `Max frames` number field | 10–1000, default 1000, hint `More frames cover more characters and scenes but take longer.` | same |
| Submit button | `Analyze` | `Analyze` |
| While the request runs | upload progress bar | button reads `Checking video…` |

- Language options and the shared language preference as 1.7.
- Above the submit button, the `AI` line of 8.4.
- Submit is enabled only with a file / a non-blank link, `Max frames` within 10–1000, a captcha token
  (when the captcha is on), and no request in flight.
- An error shows an alert with the API `detail` and keeps the inputs; the captcha resets after every
  attempt.
- Success redirects to `/film-analysis/{id}`.

**Panel "Analysis history"**

- The 50 newest jobs of the three types. Row: `source_filename` (link), source badge `Upload` /
  `YouTube` / `Rerun`, `{preset name} v{n}`, current step label · created time, status badge, `View`,
  `Delete` (only `done` / `failed`).
- `Delete` → confirm `Delete this analysis? The video, frames and prompts are removed.` → the row
  disappears.
- Empty → `No analyses yet`.
- Refreshes every 3 s while any listed job is `pending` or `processing`.

### `/film-analysis/{id}` — Analysis detail

- Header: `source_filename`, status badge, `Delete` (only `done` / `failed`; afterwards →
  `/film-analysis`).
- Summary: `Language`, `Prompt preset` (`{name} v{n}`), `AI`, `Input` (8.4), `Frames` (`{dialogue}
  dialogue + {scene} scene changes`, `—` until `capturing_frames` ends), `Created`, `Started`,
  `Finished`. YouTube adds `Source`
  and `Captions` as 1.7; a rerun adds `Rerun of` (link to the source, or `(deleted)`).
- Step progress for the job's type; `failed` → error alert with `error_message`.
- Panel "Result", once any `job_outputs` row exists: tabs `Character image prompts`,
  `Character voice prompts`, `Scene prompts`, `Video notes`; the first tab with content opens. Each tab:
  Markdown preview (images from `/jobs/{id}/files/…` only — an image with an absolute URL is not loaded
  and shows its alt text; a heading link opens YouTube in a new tab) and
  `Copy`, which copies the raw Markdown and reads `Copied` for 2 s. A tab without its row reads
  `Waiting…` while the job runs, `Not generated` after a failure.
- Panel "Prompts used", collapsed: each prompt in `options.prompts`, read-only, with `Copy`.
- Panel "Rerun with another preset", only when 3.4 rules 3–4 pass: `Prompt preset` select (default
  preselected), the `AI` line of 8.4, captcha, `Rerun` → `/film-analysis/{new id}`.
- Panel "Make a film", only when the job is `done` — turns the analysis into a Film Studio episode (4.2,
  source `film_analysis`):

| Element | Detail |
|---|---|
| `Project` | `New project` (default), then every active Film Studio project by name |
| `Project name` | `New project` only; text, prefilled with the `{stem}` of `source_filename` (1.6) cut to 100 characters |
| `Frame`, `Style`, `Language` | `New project` only; as the `New project` panel of 4.5, `Language` preselecting `options.language` when it is not `auto` |
| `Target length` | seconds, 8–600, default 60 |
| `Extra direction` | optional text area |
| `AI` line | as 8.4 — the model that writes the script |
| Media line | as the `New project` panel of 4.5 |
| Button | `Make a film`, with a captcha (when the captcha is on) |

- `Make a film` creates the project first when `New project` is chosen (4.1), then the episode, then starts
  it, and opens `/films/{project id}/episodes/{number}`. A project created before a refused episode stays.
- A project created here has narration off: the panel offers no narrator voice, and `start` refuses
  narration without one (4.2). The user turns narration on in the project's `Settings` panel.
  An error shows an alert with the API `detail` and keeps the inputs.
- Refreshes every 3 s while `pending` / `processing`.
- Unknown id, or a job of another type → `Analysis not found` with a link to `/film-analysis`.

### Step labels

Steps of domain 1 keep their 1.7 labels.

| Step | Label |
|---|---|
| `detecting_scenes` | Detecting scene changes |
| `writing_character_image_prompts` | Writing character image prompts |
| `writing_character_voice_prompts` | Writing character voice prompts |
| `writing_scene_prompts` | Writing scene prompts |

---

## API endpoints

Same conventions as domain 1. Every `POST` needs the `X-Captcha-Token` header unless
`CAPTCHA_ENABLED=false`.

```
POST   /jobs/film-analysis               — multipart `file` + `language` + `presetId?` + `maxFrames?` → 201 Job
POST   /jobs/youtube-film-analysis       — JSON { "url", "language", "presetId"?, "maxFrames"? } → 201 Job
POST   /jobs/{id}/film-analysis-rerun    — JSON { "presetId"? } → 201 Job
DELETE /jobs/{id}                        — 204
GET    /jobs?type=…&limit=…              — history: the three types (route of domain 1)
GET    /jobs/{id}                        — JobDetail; `outputs` filled for the three types
GET    /jobs/{id}/files/{path}           — a frame, once the `video_notes` row exists
```

Creation runs every check of 1.2 (upload) or 1.3 (YouTube) in its order, with two more right after
`language`:

| Rule | Result |
|---|---|
| `maxFrames` is an integer 10–1000 | 400 `Max frames must be between 10 and 1000` |
| `presetId` known | 400 `Prompt preset {id} not found` |

The AI provider check of 1.2 / 1.3 covers both the `moments` and the `filmAnalysis` models (8.1).

| Route | Errors |
|---|---|
| `POST /jobs/film-analysis` | as `POST /jobs/video-to-markdown` + 400 max frames / preset |
| `POST /jobs/youtube-film-analysis` | as `POST /jobs/youtube-to-markdown` + 400 max frames / preset |
| `POST /jobs/{id}/film-analysis-rerun` | 400 preset · 403 captcha · 404 · 409 not an analysis / no video notes / AI provider not set up |
| `DELETE /jobs/{id}` | 404 · 409 other type / still running |
| `GET /jobs/{id}/files/{path}` | as domain 1, except the 409 lasts only until `video_notes` exists |
| `GET /jobs/{id}/download` | 409 `Job {id} has no zip download` |

`JobDetail.outputs`: `{ videoNotes, characterImagePrompts, characterVoicePrompts, scenePrompts }`, each a
string or `null`; `outputs` is `null` and `markdown` is `null` for the other domain's types.

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `FILM_SCENE_THRESHOLD` | `0.4` | 3.2 |
| `FILM_SCENE_TIMEOUT_SEC` | `3600` | 3.2 |
| `FILM_PROMPT_TIMEOUT_SEC` | `900` | 3.3 — every provider |

Shared with domain 1: `CAPTCHA_ENABLED`, `MAX_UPLOAD_MB`, `WHISPER_*`, `MEDIA_TIMEOUT_SEC`,
`AI_MOMENTS_TIMEOUT_SEC` (`picking_moments`), `YTDLP_BIN`, `YOUTUBE_*`. AI model keys: domain 8.

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- A film with no speech or no usable captions — it fails as in domain 1.
- Speaker diarization or any audio analysis of voices.
- Generating images, voices or video from the prompts inside this domain — Film Studio (domain 4) does it
  from a `done` analysis.
- A `.md` file or zip download of the results; editing results in place.
- Deleting a running job; bulk delete; search or filter on the history.
