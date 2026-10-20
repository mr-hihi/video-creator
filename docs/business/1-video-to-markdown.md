# 1. Chuyển video thành Markdown (Video to Markdown)

> One file = one domain. Every section below belongs to the **Video to Markdown** domain.

Turns a video into a Markdown note: the spoken words plus a screenshot at each key moment, where the AI
model (domain 8) picks the moments from the transcript, or from the transcript and one frame per second.
Two sources feed the same job model and share the back half of the pipeline:

| Source | Job type | Transcript from | Frames from |
|---|---|---|---|
| Uploaded file | `video_to_markdown` | whisper.cpp on the file's audio | the uploaded file |
| YouTube link | `youtube_to_markdown` | the video's YouTube captions | the video, downloaded with `yt-dlp` |

- Persona: one person on their own Mac. No login; a captcha on job creation is the only guard, and it
  can be switched off for local runs (`CAPTCHA_ENABLED` / `NEXT_PUBLIC_CAPTCHA_ENABLED` = `false`).
- Entity: `Job` (table `jobs`), shared with Film Analysis (domain 3) and Film Clone (domain 5).
- Prompt: the `videoToMarkdown` prompt of a prompt preset (domain 2), copied into the job at creation.
- AI model: the model of the `moments` step group (domain 8), read when the call starts. Input mode: the
  `inputMode` setting, copied into the job at creation.
- Output of a `done` job: `{name}.md` + `images/` + `result.zip` (1.6).
- External tools: `ffmpeg` / `ffprobe`, `whisper-cli`, the `claude` CLI, the Gemini API or the OpenAI API
  (8.2), `yt-dlp`
  (runs with Node as its JS runtime — YouTube's player challenge fails without one).

## 1.1 Job & lifecycle

### Data model — `Job`

| Field | Type | Meaning |
|---|---|---|
| `id` | string(36) | UUID v4 |
| `type` | enum | `video_to_markdown` \| `youtube_to_markdown`; Film Analysis adds `film_analysis` \| `youtube_film_analysis` \| `film_analysis_rerun` (3.1); Film Clone adds `film_clone` \| `youtube_film_clone` (5.1) |
| `status` | enum | `pending` \| `processing` \| `done` \| `failed` |
| `step` | enum \| null | step running now, or the step that failed; `null` before the first step |
| `source_filename` | string(255) | display name; its stem also names the `.md` and `.zip` (1.6) |
| `options` | JSON | per-source input — 1.2, 1.3; `preset` + `prompts` copied from a prompt preset (2.5); `inputMode` copied from the settings (8.1) |
| `ai_used` | JSON | the model each AI step used, keyed by step (8.1); `{}` before the first AI step |
| `error_message` | text \| null | set when `failed` |
| `created_at` / `updated_at` / `started_at` / `finished_at` | datetime (UTC) | |

### Status workflow

```
pending ──claim──▶ processing ──▶ done
                       ├───────▶ failed   (error_message + step kept)
                       └─ API stopped mid-job ─▶ pending again on the next start
```

| Status | Meaning |
|---|---|
| `pending` | created, waiting for the worker |
| `processing` | the worker runs its steps; `step` names the current one |
| `done` | Markdown, images and zip are written |
| `failed` | a step raised; `error_message` holds the reason |

**Transition rules:**
- A creation request only validates and inserts the row; every step runs in the batch worker inside
  the API process, one job at a time, oldest `pending` first.
- `done` and `failed` are final. There is no retry — the user creates a new job.
- A job interrupted by an API stop returns to `pending` and re-runs from its first step (a YouTube job
  downloads again).

### Steps per type

`inputMode` = `subtitles`:

| # | `video_to_markdown` | `youtube_to_markdown` |
|---|---|---|
| 1 | `extracting_audio` | `fetching_transcript` |
| 2 | `transcribing` | `picking_moments` |
| 3 | `picking_moments` | `downloading_video` |
| 4 | `capturing_frames` | `capturing_frames` |
| 5 | `writing_markdown` | `writing_markdown` |

- YouTube reads the transcript first, so a video without usable captions fails before any download.
- YouTube downloads after `picking_moments`, so a model failure wastes no download.
- `inputMode` = `whole_video` adds `sampling_frames` right before `picking_moments`, and YouTube downloads
  before both (8.3).

## 1.2 Source — uploaded file

`options`: `{ "language": "auto" | "{iso}" }` — the spoken language handed to whisper — plus `preset`
and `prompts` (2.5), `inputMode` (8.1).

### Validation at creation

| Rule | Result |
|---|---|
| Captcha token valid (checked first; skipped when `CAPTCHA_ENABLED=false`) | 403 `Captcha verification failed` |
| Request has a `file` part | 422 |
| Extension in `.mp4 .mov .mkv .webm .avi .m4v`, case-insensitive | 400 `Unsupported file type '{ext}'. Use one of: .avi, .m4v, .mkv, .mov, .mp4, .webm` |
| `language` matches `^(auto\|[a-z]{2,3})$` | 400 `Invalid language '{value}'` |
| `presetId` (optional form field) names a preset; absent → the default preset | 400 `Prompt preset {id} not found` |
| The provider of the `moments` model is set up (8.1) | 409 `{provider name} is not set up — open Settings` |
| File size ≤ `MAX_UPLOAD_MB` | 413 `Upload exceeds the {bytes} byte limit`; the partial file is removed |

- `source_filename` = the uploaded file name, cut to 255 characters.
- The file is saved as `storage/{job-id}/source.{ext}`.

### Steps

| Step | Behaviour |
|---|---|
| `extracting_audio` | `ffprobe` reads the duration; `ffmpeg` writes 16 kHz mono PCM WAV |
| `transcribing` | whisper.cpp with `language` (`auto` = detect). Bracketed markers (`[BLANK_AUDIO]`, `(music)`) are dropped; the detected language is kept when `auto` |

| Failure | `error_message` |
|---|---|
| Whisper model file missing | `Whisper model not found at {path}. Run \`sh run.sh setup_whisper\` or set WHISPER_MODEL_PATH.` |
| No segment left after filtering | `No speech was detected in the video` |

## 1.3 Source — YouTube link

### `options`

| Key | Written at | Value |
|---|---|---|
| `url` | creation | canonical `https://www.youtube.com/watch?v={videoId}` |
| `videoId` | creation | 11 characters from `[A-Za-z0-9_-]` |
| `language` | creation | `auto` or an ISO code — the caption language wanted (1.4) |
| `captionKind` | `fetching_transcript` | `manual` (uploaded by the author) \| `auto` (YouTube speech recognition) |
| `preset`, `prompts` | creation | 2.5 |
| `inputMode` | creation | 8.1 |

### Link parsing

Surrounding whitespace is trimmed; the scheme may be `https://`, `http://` or absent.

| Host | Path | `videoId` from |
|---|---|---|
| `youtube.com`, `www.youtube.com`, `m.youtube.com` | `/watch` | the `v` query parameter |
| same | `/shorts/{id}`, `/live/{id}`, `/embed/{id}` | the path |
| `youtu.be` | `/{id}` | the path |

- Every other query parameter (`t`, `list`, `index`, `si`, `feature`) is ignored: a playlist link that
  carries `v=` converts that one video.
- `youtube.com/playlist?list=…` → 400 `Playlist links are not supported. Open one video and copy its link`.
- Any other input → 400 `Not a YouTube video link`.

### Validation at creation

Checks run in this order. The metadata check calls `yt-dlp` inside the request (typically 2–5 s,
capped at 30 s) so a bad link fails in the form instead of as a `failed` job.

| # | Rule | Result |
|---|---|---|
| 1 | Captcha token valid (skipped when `CAPTCHA_ENABLED=false`) | 403 `Captcha verification failed` |
| 2 | JSON body has `url` | 422 |
| 3 | `language` matches `^(auto\|[a-z]{2,3})$` | 400 `Invalid language '{value}'` |
| 4 | `presetId` (optional) names a preset; absent → the default preset | 400 `Prompt preset {id} not found` |
| 5 | The provider of the `moments` model is set up (8.1) | 409 `{provider name} is not set up — open Settings` |
| 6 | Link parses (above) | 400 as listed above |
| 7 | `yt-dlp` reports an error about this video (unavailable, private, removed, age-restricted, members-only) | 400 `YouTube refused the video: {reason}` — `{reason}` is the text after the last `ERROR: [youtube] {id}: ` |
| 8 | `live_status` is `is_live`, `is_upcoming` or `post_live` | 400 `Live or upcoming videos are not supported` |
| 9 | `duration` ≤ `YOUTUBE_MAX_DURATION_MIN` × 60 s | 400 `Video is {duration} long; the limit is {N} min` — `{duration}` formatted as in 1.6 |
| — | `yt-dlp` cannot run, passes 30 s, or its reason reads as network trouble (`Unable to download …`, `HTTP Error …`, `… not a bot`, `timed out`) | 502 `Could not reach YouTube: {error}` |

- `source_filename` = `{title} [{videoId}].mp4`, the title shortened so the whole name fits 255 characters.
- The same `videoId` submitted twice creates two independent jobs.

### `downloading_video`

- `yt-dlp` fetches the video stream only — no audio, frames need no sound — at height ≤
  `YOUTUBE_VIDEO_HEIGHT`, h264 preferred, into `storage/{job-id}/source.mp4`. A Film Analysis or Film Clone
  job in `whole_video`, or a Film Analysis job in `full_video`, fetches the audio stream too, merged into the
  same file (8.3).
- Every worker-side `yt-dlp` call is limited to `YOUTUBE_TIMEOUT_SEC`.
- Any failure (network, `Sign in to confirm you're not a bot`, timeout) → `failed` at
  `downloading_video` with `yt-dlp`'s error text. No automatic retry.

## 1.4 Transcript from YouTube captions (`fetching_transcript`)

The worker reads the metadata again — caption track URLs are short-lived — picks one track, and
converts it to transcript segments. Whisper is not used.

### Terms

| Term | Meaning |
|---|---|
| Spoken language `L` | metadata `language`; else the language of the `{lang}-orig` track under `automatic_captions` |
| Manual track | an entry under `subtitles` — uploaded by the author, in any language |
| Auto track in `L` | `{L}-orig` under `automatic_captions` — YouTube's speech recognition |
| Machine-translated track | any other entry under `automatic_captions` — **never used** |

Language codes compare on the primary subtag: `en-US`, `en-GB` and `en` all count as `en`.

### Track selection

| `language` | 1st choice | 2nd choice | Nothing found → `failed` with |
|---|---|---|---|
| `auto` | manual track in `L` | auto track in `L` | `This video has no transcript on YouTube` |
| `{X}` | manual track in `X` | auto track in `X`, only when `X` = `L` | `No '{X}' captions on YouTube for this video. Available: {list}` |

- `auto` when `L` is unknown: the first manual track in code order.
- A video with no manual and no auto track at all → `This video has no transcript on YouTube`, for any
  `language`.
- `{list}`: the usable tracks as `{code} ({kind})`, manual first, comma-separated — e.g. `vi (auto)`, or
  `de (manual), en (manual), es (manual), ja (manual), pt (manual), en (auto)`.
- On success `options.captionKind` is saved and `Transcript.language` is the chosen track's primary code.

### Conversion (`json3` caption format)

- One caption event with text → one segment: `start_ms = tStartMs`, `end_ms = tStartMs + dDurationMs`.
- Dropped: events with no text, line-break-only events (`aAppend`), text wholly in brackets (`[Music]`,
  `[Âm nhạc]`, `[Applause]`) — the same marker rule as whisper output (1.2).
- A line identical to the previous kept line is dropped (rolling auto captions repeat lines).
- Line breaks inside an event become spaces; consecutive lines are one space apart in the paragraph.
- Nothing left after filtering → `failed` with `No speech was detected in the video`.

## 1.5 Key moments & screenshots (both sources)

### `picking_moments`

- One call of the `moments` model (8.1, 8.2) with a JSON schema; one call per window when `inputMode` is
  `whole_video` (8.3).
- System prompt: the job's `options.prompts.videoToMarkdown`; the code default when absent (2.2).
- Added by the app (2.2): the output shape as the schema; in `subtitles` mode a user message with
  `Choose at most {MAX_MOMENTS} key moments` and the transcript as one line per segment,
  `[{start_ms}ms] {text}`; in `whole_video` mode the window message of 8.3.
- The reply is untrusted input and is normalised:
  1. Clamp `atMs` to `[0, duration − 500 ms]` (a seek at the very end yields no frame).
  2. Drop moments with a blank title.
  3. Sort by time; drop a moment less than 3 s after the previous kept one.
  4. Keep the first `MAX_MOMENTS`.
- Duration: `ffprobe` for an upload; the metadata `duration` for YouTube.

A failing call fails the step with the messages of 8.2. A moment that misses `atMs` / `title` or has a
non-integer `atMs` fails it with `{ai} returned a malformed moment: {detail}`.

### `capturing_frames`

- One JPEG per moment, `ffmpeg` fast seek, width ≤ 1280 px, never upscaled.
- Taken from the uploaded file, or from the downloaded `source.mp4` for YouTube.
- File name `images/moment-{NN}-{H}h{MM}m{SS}s.jpg`; the hour part only from one hour on — e.g.
  `moment-02-01m23s.jpg`, `moment-10-1h02m05s.jpg`.

## 1.6 Markdown output (`writing_markdown`)

### Layout

```markdown
# {title}

> Source: {source} · Duration: {duration} · Language: {language}

{summary}

{transcript before the first moment — usually empty}

## {timestamp} — {moment title}

![{timestamp} — {moment title}](images/moment-01-00m00s.jpg)

{transcript of this moment}
```

### Rules

- `{title}`: the model's title; blank → the safe stem of `source_filename` (below).
- Each segment goes under the last moment that starts at or before it.
- The segments of one moment form one paragraph.
- Timestamps: `mm:ss`, or `h:mm:ss` from one hour on.
- Image paths stay relative (`images/…`), so the same file works inside the zip and in the preview.
- `[` and `]` in alt text become `(` and `)`.

### Per source

| Part | Uploaded file | YouTube link |
|---|---|---|
| `{source}` | `source_filename` | `options.url` |
| `## {timestamp}` | plain text — `## 01:23 — {title}` | link to that second — `## [01:23](https://www.youtube.com/watch?v={videoId}&t=83s) — {title}` |
| alt text | `01:23 — {title}` | `01:23 — {title}` (no link) |

### Files

| Path | Content |
|---|---|
| `storage/{job-id}/output/{stem}.md` | the Markdown |
| `storage/{job-id}/output/images/` | the frames |
| `storage/{job-id}/result.zip` | everything under `output/`, downloaded as `{stem}.zip` |

`{stem}` = `source_filename` without its extension, every run of characters outside letters, digits,
`_ - . ` and space replaced by `_`, then trimmed of spaces, dots and underscores; empty → `video`.
Example: `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4` →
`30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này_ _vfjegxHDOwI`.

## 1.7 Screens

### Header (every page)

- App name, then the menu `Video to Markdown` (`/`) · `Film Analysis` (`/film-analysis`) ·
  `Film Clone` (`/film-clone`) · `Film Studio` (`/films`) · `Settings` (`/settings`).
- The item of the current page is highlighted; `/jobs/{id}` highlights `Video to Markdown`,
  `/film-analysis/{id}` highlights `Film Analysis`, every `/film-clone…` page highlights `Film Clone`,
  every `/films…` page highlights `Film Studio`, every `/settings…` page highlights `Settings`.

### `/` — Home

**Panel "New conversion"**

| Element | Upload file (default) | YouTube link |
|---|---|---|
| Source switch | `Upload file` \| `YouTube link` — resets to `Upload file` on every visit | |
| Input | `Video` drop field, accepts the 1.2 extensions | `YouTube link` text field, placeholder `https://www.youtube.com/watch?v=…` |
| Language select | `Spoken language` | `Caption language` |
| `Prompt preset` select | presets in 2.6 order, the default one preselected and labelled `{name} (default)`; link `Edit presets` → `/settings?tab=prompt-override&id={selected}` | same |
| Submit button | `Upload and convert` | `Convert` |
| While the request runs | upload progress bar | button reads `Checking video…` |

- Language options: `Auto-detect` (`auto`), `Vietnamese` (`vi`), `English` (`en`), `Japanese` (`ja`).
  The chosen value is one preference shared by both forms.
- Above the submit button, the `AI` line of 8.4.
- Submit is enabled only with a file / a non-blank link, a captcha token (when the captcha is on), and no
  request in flight.
- An error shows an alert with the API `detail` and keeps the input.
- The captcha resets after every attempt — tokens are single-use, so a retry with a spent token is 403.
- `NEXT_PUBLIC_CAPTCHA_ENABLED=false` renders no captcha widget and sends no `X-Captcha-Token` header.
- Success redirects to `/jobs/{id}`.

**Panel "Recent jobs"**

- The 50 newest `video_to_markdown` / `youtube_to_markdown` jobs; Film Analysis jobs are not listed.
  Row: `source_filename` (link), source badge `Upload` / `YouTube`, current step label · created time,
  status badge, `View`.
- Refreshes every 3 s while any listed job is `pending` or `processing`.

### `/jobs/{id}` — Job detail

- Header: `source_filename` + status badge.
- Summary: `Language`, `Prompt preset` (2.5), `AI`, `Input` (8.4), `Created`, `Started`,
  `Finished`. YouTube jobs add `Source` (the `url`, opens in a new tab) and `Captions`
  (`Uploaded by author` \| `Auto-generated` \| `—` until `fetching_transcript` ends).
- Step progress lists the steps of the job's type (1.1), each `completed` / `current` / `failed` / `upcoming`.
- `failed` → error alert with `error_message`.
- `done` → panel "Result": Markdown preview (images served from `/jobs/{id}/files/…`; an image with an
  absolute URL is not loaded; a heading link opens YouTube in a new tab) + `Download .zip`.
- Refreshes every 3 s while `pending` / `processing`; stops at `done` / `failed`.

### Step labels

| Step | Label |
|---|---|
| `extracting_audio` | Extracting audio |
| `transcribing` | Transcribing speech |
| `fetching_transcript` | Fetching YouTube transcript |
| `picking_moments` | Picking key moments |
| `downloading_video` | Downloading video |
| `sampling_frames` | Sampling frames |
| `capturing_frames` | Capturing frames |
| `writing_markdown` | Writing Markdown |

---

## API endpoints

JSON is camelCase; datetimes are ISO-8601 UTC (`…Z`); errors are `{ "detail": string }`, except 422
where `detail` is an array of `{ msg, … }`. Both `POST` routes need the `X-Captcha-Token` header unless
`CAPTCHA_ENABLED=false`.

```
POST /jobs/video-to-markdown         — multipart `file` + `language` + `presetId?` → 201 Job
POST /jobs/youtube-to-markdown       — JSON { "url", "language", "presetId"? } → 201 Job
GET  /jobs?type=…&limit=1..200       — Job[] newest first (default 50); `type` repeatable, absent → every type
GET  /jobs/{id}                      — JobDetail = Job + `markdown` (non-null only when done)
GET  /jobs/{id}/files/{path}         — one file from the job's output/
GET  /jobs/{id}/download             — application/zip attachment `{stem}.zip`
```

The home page calls `GET /jobs?type=video_to_markdown&type=youtube_to_markdown`. Film Analysis routes
are listed in domain 3, Film Clone routes in domain 5, preset routes in domain 2.

| Route | Errors |
|---|---|
| `POST /jobs/video-to-markdown` | 400 type / language / preset · 403 captcha · 409 AI provider not set up · 413 too large · 422 no `file` |
| `POST /jobs/youtube-to-markdown` | 400 link / video / live / duration / language / preset · 403 captcha · 409 AI provider not set up · 422 no `url` · 502 YouTube unreachable |
| `GET /jobs` | 422 bad `limit` / unknown `type` |
| `GET /jobs/{id}` | 404 `Job {id} not found` |
| `GET /jobs/{id}/files/{path}` | 404 unknown job / missing file / path outside `output/` · 409 `Job {id} has no result yet` |
| `GET /jobs/{id}/download` | 404 unknown job · 409 not done |

`Job`: `id`, `type`, `status`, `step`, `sourceFilename`, `options`, `aiUsed` (8.1), `errorMessage`,
`createdAt`, `startedAt`, `finishedAt`. `options` keys are listed in 1.2 and 1.3.

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `CAPTCHA_ENABLED` | `true` — `false` in the local / test env files; the frontend mirror is `NEXT_PUBLIC_CAPTCHA_ENABLED` | 1.2, 1.3, 1.7 |
| `MAX_UPLOAD_MB` | `4096` | 1.2 |
| `WHISPER_MODEL_PATH` | `models/ggml-large-v3-turbo.bin` | 1.2 |
| `WHISPER_TIMEOUT_SEC` | `7200` | 1.2 |
| `MEDIA_TIMEOUT_SEC` | `1800` | `ffmpeg` / `ffprobe` calls |
| `AI_MOMENTS_TIMEOUT_SEC` | `600` | 1.5, 8.3 — every provider |
| `MAX_MOMENTS` | `12` | 1.5 |
| `YTDLP_BIN` | `yt-dlp` — installed into `api/.venv` by `uv sync` | 1.3, 1.4 |
| `YOUTUBE_MAX_DURATION_MIN` | `180` | 1.3 |
| `YOUTUBE_VIDEO_HEIGHT` | `720` | 1.3 |
| `YOUTUBE_TIMEOUT_SEC` | `1800` | worker-side `yt-dlp` calls (1.3, 1.4) |
| `BATCH_POLL_INTERVAL_SEC` | `5` | 1.1 |

## Capacities

None. A single-user local tool with no login and no RBAC (workspace ADR W2). The captcha on both
`POST` routes is the only guard; `CAPTCHA_ENABLED=false` turns it off for local runs.

## Non-goals

- Several links in one submission; playlists or channels.
- Title / thumbnail preview before submitting.
- A whisper fallback for a YouTube video without usable captions.
- Machine-translated YouTube captions.
- Search or filter on the job list; retrying a failed job; deleting Video to Markdown jobs or cleaning
  `storage/` (Film Analysis jobs can be deleted — 3.5).
