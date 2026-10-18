## 1. Video to Markdown (1-video-to-markdown.md)

Test cases for [business/1-video-to-markdown.md](../business/1-video-to-markdown.md). Acronym `VTM`.

## Test environment

- Stack: `sh run.sh migrate test`, then the user starts `sh run.sh start_test` in their own terminal —
  frontend http://localhost:5071, API http://localhost:5070, DB `video_tool_test`, storage
  `api/storage-test/`. Verify with `curl -s http://localhost:5070/jobs?limit=1`.
- Captcha: the local / test env files set `CAPTCHA_ENABLED=false` and `NEXT_PUBLIC_CAPTCHA_ENABLED=false`, so
  no widget shows and `curl` needs no header. Steps marked *(captcha on)* apply only when both are `true`; then
  the always-pass Turnstile keys pass the widget by itself, `curl` sends
  `-H 'X-Captcha-Token: XXXX.DUMMY.TOKEN.XXXX'`, and an empty header counts as a rejected token.
- App labels: **Frontend** = browser on :5071 · **API** = `curl` on :5070 · **API unit** = `sh run.sh test`
  with mocks only (no DB, no network).
- Reference data (metadata checked with `yt-dlp -J` on 2026-09-27):

| Id | Input | Facts |
|---|---|---|
| V1 | `https://www.youtube.com/watch?v=vfjegxHDOwI` | `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này!`, 670 s (`11:10`), `language` = `vi`, no manual track, auto track `vi-orig`, the rest machine-translated (incl. `en`) |
| V2 | `https://www.youtube.com/watch?v=dQw4w9WgXcQ` | `Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)`, 213 s (`03:33`), `language` = `en`, manual `de-DE`, `en`, `es-419`, `ja`, `pt-BR`, auto `en-orig` |
| V3 | `https://www.youtube.com/watch?v=xxxxxxxxxxx` | `yt-dlp`: `ERROR: [youtube] xxxxxxxxxxx: This video is unavailable` |
| F1 | `downloads/30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4` | local copy of V1 (21 MB) for upload cases |

- "Job" checks: `curl -s http://localhost:5070/jobs/{id}` and the files under `api/storage-test/{id}/`.

---

## Uploaded file

### TC-VTM-01: Upload a video and get the Markdown
- **App:** Frontend
- **Precondition:** Test stack running; whisper model present (`sh run.sh setup_whisper`); `claude` CLI logged in.
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. Keep source `Upload file`
  3. Drop F1 on the `Video` field
  4. Select `Vietnamese` from the `Spoken language` dropdown
  5. *(captcha on)* Wait for the captcha to pass
  6. Click `Upload and convert`
  7. Wait until the status badge shows `done`
- **Expected:**
  - URL becomes `/jobs/{id}`; the step list shows `Extracting audio`, `Transcribing speech`, `Picking key moments`, `Capturing frames`, `Writing Markdown` in that order
  - Summary shows `Language` = `Vietnamese` and `Prompt preset` = `{default preset name} v{n}`; no `Source` / `Captions` rows
  - Result preview shows a `#` title, the line `> Source: 30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4 · Duration: 11:10 · Language: vi`, and ≥ 1 `##` heading in the form `mm:ss — {title}` with an image
  - Headings are plain text, not links
  - `Download .zip` gives `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này_ _vfjegxHDOwI.zip` containing that `.md` and `images/moment-01-00m00s.jpg`

### TC-VTM-02: Unsupported file type
- **App:** Frontend
- **Precondition:** A file `notes.txt` on disk.
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. Drop `notes.txt` on the `Video` field, *(captcha on)* wait for the captcha, click `Upload and convert`
- **Expected:**
  - Error alert: `Unsupported file type '.txt'. Use one of: .avi, .m4v, .mkv, .mov, .mp4, .webm`
  - URL stays `/`; no new row in `Recent jobs`

### TC-VTM-03: File over `MAX_UPLOAD_MB`
- **App:** API
- **Precondition:** `MAX_UPLOAD_MB=1` in `api/.env.test`, test stack restarted.
- **Steps:**
  1. From `video-tool/`: `curl -i -X POST http://localhost:5070/jobs/video-to-markdown -H 'X-Captcha-Token: XXXX.DUMMY.TOKEN.XXXX' -F 'file=@downloads/30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4' -F 'language=auto'`
- **Expected:**
  - `HTTP 413`, `detail` = `Upload exceeds the 1048576 byte limit`
  - No new job in `GET /jobs`; no new folder left under `api/storage-test/`

## YouTube — creation & link parsing

### TC-VTM-04: YouTube link, auto captions, end to end
- **App:** Frontend
- **Precondition:** Test stack running; `claude` CLI logged in; network up.
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. Click `YouTube link` in the source switch
  3. Fill `YouTube link` with `https://youtu.be/vfjegxHDOwI?si=abc123`
  4. Select `Auto-detect` from the `Caption language` dropdown
  5. *(captcha on)* Wait for the captcha; click `Convert`
  6. Wait until the status badge shows `done`
- **Expected:**
  - The button reads `Checking video…` while the request runs, then the URL becomes `/jobs/{id}`
  - Header shows `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4`
  - Step list shows `Fetching YouTube transcript`, `Picking key moments`, `Downloading video`, `Capturing frames`, `Writing Markdown` in that order; no `Extracting audio` / `Transcribing speech`
  - Summary: `Source` = `https://www.youtube.com/watch?v=vfjegxHDOwI`, `Captions` = `Auto-generated`
  - `GET /jobs/{id}` → `type` = `youtube_to_markdown`, `options` holds `"url": "https://www.youtube.com/watch?v=vfjegxHDOwI"`, `"videoId": "vfjegxHDOwI"`, `"language": "auto"`, `"captionKind": "auto"`, `preset` = the default preset's `{ id, name, version }`, and `prompts` with the single key `videoToMarkdown`
  - Markdown source line: `> Source: https://www.youtube.com/watch?v=vfjegxHDOwI · Duration: 11:10 · Language: vi`
  - Every `##` heading is `## [mm:ss](https://www.youtube.com/watch?v=vfjegxHDOwI&t={seconds}s) — {title}`; its image alt text is `mm:ss — {title}` without a link
  - `api/storage-test/{id}/source.mp4` exists with height ≤ 720 and no audio stream (`ffprobe -show_streams` lists only `codec_type=video`)
  - `Download .zip` gives `30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này_ _vfjegxHDOwI.zip`

### TC-VTM-05: Every accepted link form gives the same canonical URL
- **App:** API
- **Precondition:** Test stack running.
- **Steps:** for each input below, `curl -s -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'X-Captcha-Token: XXXX.DUMMY.TOKEN.XXXX' -H 'Content-Type: application/json' -d '{"url":"{input}","language":"auto"}'`
  1. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
  2. `  youtube.com/watch?v=dQw4w9WgXcQ&t=42s  `
  3. `https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=share`
  4. `https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG&index=3`
  5. `https://youtu.be/dQw4w9WgXcQ`
  6. `http://www.youtube.com/embed/dQw4w9WgXcQ`
  7. `https://www.youtube.com/shorts/dQw4w9WgXcQ`
  8. `https://www.youtube.com/live/dQw4w9WgXcQ`
- **Expected:**
  - Every call → `HTTP 201`, `options.url` = `https://www.youtube.com/watch?v=dQw4w9WgXcQ`, `options.videoId` = `dQw4w9WgXcQ`
  - `sourceFilename` = `Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) [dQw4w9WgXcQ].mp4`
  - 8 separate jobs in `GET /jobs` — the same video twice is never merged

### TC-VTM-06: Playlist-only link
- **App:** API
- **Steps:**
  1. POST as in TC-VTM-05 with `url` = `https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG`
- **Expected:**
  - `HTTP 400`, `detail` = `Playlist links are not supported. Open one video and copy its link`
  - No job created

### TC-VTM-07: Not a YouTube video link
- **App:** API
- **Steps:** POST as in TC-VTM-05 with each `url`:
  1. `https://vimeo.com/76979871`
  2. `https://www.youtube.com/watch?v=short`
  3. `https://www.youtube.com/@somechannel`
  4. `hello`
- **Expected:**
  - Every call → `HTTP 400`, `detail` = `Not a YouTube video link`; no job created

### TC-VTM-08: Invalid language, missing url, rejected captcha
- **App:** API
- **Steps:**
  1. POST V2 with `"language":"vietnamese"`
  2. POST `{"language":"auto"}` (no `url`)
  3. *(captcha on)* POST V2 with header `X-Captcha-Token:` (empty)
- **Expected:**
  1. `HTTP 400`, `detail` = `Invalid language 'vietnamese'`
  2. `HTTP 422`, `detail` is an array naming `url`
  3. `HTTP 403`, `detail` = `Captcha verification failed`
  - No job created by any of the three

### TC-VTM-09: Unavailable video
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/, click `YouTube link`
  2. Fill `YouTube link` with V3, *(captcha on)* wait for the captcha, click `Convert`
- **Expected:**
  - Error alert: `YouTube refused the video: This video is unavailable`
  - While the request runs the button reads `Checking video…` and is disabled
  - The link stays in the field; *(captcha on)* the captcha is reset and `Convert` is disabled until it passes again
  - No new row in `Recent jobs`

### TC-VTM-10: Video longer than `YOUTUBE_MAX_DURATION_MIN`
- **App:** API
- **Precondition:** `YOUTUBE_MAX_DURATION_MIN=5` in `api/.env.test`, test stack restarted.
- **Steps:**
  1. POST V1 as in TC-VTM-05
- **Expected:**
  - `HTTP 400`, `detail` = `Video is 11:10 long; the limit is 5 min`; no job created
  - With V2 (03:33) the same setting answers `HTTP 201`

### TC-VTM-11: Live or upcoming video
- **App:** API unit
- **Precondition:** No stable public live stream exists; the metadata reader is faked.
- **Steps:**
  1. Create a YouTube job whose faked metadata has `live_status` = `is_live`, then `is_upcoming`, then `post_live`
  2. Repeat with `not_live` and `was_live`
- **Expected:**
  - The first three raise the 400 error `Live or upcoming videos are not supported`; no job row is added
  - `not_live` and `was_live` create a `pending` job
  - Manual check (optional): any stream showing `LIVE` on YouTube answers the same 400 through `curl`

### TC-VTM-12: YouTube unreachable
- **App:** API unit
- **Precondition:** The metadata reader's command runner is faked. Not runnable on the live stack: with the network off the captcha check fails first (403).
- **Steps:**
  1. Create a YouTube job for V2 while the faked `yt-dlp` call fails with a connection error
  2. Repeat with a timeout, then with the `yt-dlp` binary missing
- **Expected:**
  - All three → HTTP 502, `detail` starts with `Could not reach YouTube: `; no job row added
  - The metadata call is made with a 30 s timeout

## YouTube — transcript

### TC-VTM-13: Manual captions win over auto captions
- **App:** Frontend
- **Steps:**
  1. Create a YouTube job for V2 with `Caption language` = `Auto-detect`
  2. Wait for `done`
- **Expected:**
  - Summary `Captions` = `Uploaded by author`; `options.captionKind` = `manual`
  - Markdown source line ends with `Language: en`

### TC-VTM-14: Manual track in a language other than the spoken one
- **App:** Frontend
- **Steps:**
  1. Create a YouTube job for V2 with `Caption language` = `Japanese`
  2. Wait for `done`
- **Expected:**
  - `options.captionKind` = `manual`; source line ends with `Language: ja`
  - Transcript paragraphs are the Japanese captions; moment titles are in Japanese

### TC-VTM-15: Only a machine-translated track in the requested language
- **App:** Frontend
- **Steps:**
  1. Create a YouTube job for V1 with `Caption language` = `English`
  2. Wait until the status badge shows `failed`
- **Expected:**
  - Error alert: `No 'en' captions on YouTube for this video. Available: vi (auto)`
  - Step `Fetching YouTube transcript` is marked failed; every later step is `upcoming`
  - No `source.mp4` under `api/storage-test/{id}/` — nothing was downloaded
  - `options.captionKind` is absent; summary `Captions` = `—`

### TC-VTM-16: Requested language not available at all, several manual tracks
- **App:** API
- **Steps:**
  1. POST V2 with `"language":"vi"`, then poll `GET /jobs/{id}` until `failed`
- **Expected:**
  - `step` = `fetching_transcript`
  - `errorMessage` = `No 'vi' captions on YouTube for this video. Available: de (manual), en (manual), es (manual), ja (manual), pt (manual), en (auto)`

### TC-VTM-17: Video with no captions at all
- **App:** API unit
- **Precondition:** Faked metadata with empty `subtitles` and `automatic_captions`.
- **Steps:**
  1. Run the YouTube handler with `language` = `auto`, then with `language` = `vi`
- **Expected:**
  - Both raise `This video has no transcript on YouTube` at `fetching_transcript`
  - The video downloader is never called

### TC-VTM-18: Track selection matrix
- **App:** API unit
- **Steps:** run track selection with faked metadata:

  | # | `language` | `L` | Manual | Auto | Expected track |
  |---|---|---|---|---|---|
  | 1 | `auto` | `en` | `en-US` | `en-orig` | manual `en-US` |
  | 2 | `auto` | `en` | — | `en-orig`, `vi` | auto `en-orig` |
  | 3 | `auto` | `en` | `ja` | — | none → `This video has no transcript on YouTube` |
  | 4 | `auto` | unknown | `ja`, `de` | — | manual `de` |
  | 5 | `ja` | `en` | `ja` | `en-orig`, `ja` | manual `ja` |
  | 6 | `en` | `en` | — | `en-orig` | auto `en-orig` |
  | 7 | `vi` | `en` | — | `en-orig`, `vi` | none → `No 'vi' captions … Available: en (auto)` |
- **Expected:** each row picks the track in the last column; `captionKind` = `manual` / `auto` to match

### TC-VTM-19: Caption conversion
- **App:** API unit
- **Steps:** convert a `json3` fixture with these events:
  1. `{tStartMs: 0, dDurationMs: 671800}` (no `segs`)
  2. `{tStartMs: 240, dDurationMs: 3439, segs: "được làm việc khá là kỹ càng với các nhà"}`
  3. `{tStartMs: 1670, dDurationMs: 2009, aAppend: 1, segs: "\n"}`
  4. `{tStartMs: 1680, dDurationMs: 3920, segs: "[Âm nhạc]"}`
  5. `{tStartMs: 3679, dDurationMs: 3801, segs: "đầu tư giỏi nhất ở Nhật Bản ấy thì họ"}`
  6. `{tStartMs: 5590, dDurationMs: 1890, segs: "đầu tư giỏi nhất ở Nhật Bản ấy thì họ"}`
- **Expected:**
  - Exactly 2 segments: `(240, 3679, "được làm việc khá là kỹ càng với các nhà")` and `(3679, 7480, "đầu tư giỏi nhất ở Nhật Bản ấy thì họ")`
  - The Markdown paragraph built from them is `được làm việc khá là kỹ càng với các nhà đầu tư giỏi nhất ở Nhật Bản ấy thì họ` (one space between)
  - A fixture whose only events are 1, 3 and 4 fails with `No speech was detected in the video`

## YouTube — download & lifecycle

### TC-VTM-20: Download fails
- **App:** API unit
- **Precondition:** Faked downloader raising `ERROR: [youtube] vfjegxHDOwI: Sign in to confirm you're not a bot`.
- **Steps:**
  1. Run the YouTube handler through the worker
- **Expected:**
  - Job `failed`, `step` = `downloading_video`, `error_message` contains `Sign in to confirm you're not a bot`
  - `capturing_frames` never starts; no retry is scheduled

### TC-VTM-21: API restarted during `downloading_video`
- **App:** Frontend
- **Precondition:** Test stack running.
- **Steps:**
  1. Create a YouTube job for V1
  2. When the step shows `Downloading video`, ask the user to stop the test stack (Ctrl+C) and start `sh run.sh start_test` again
  3. Open `/jobs/{id}` again
- **Expected:**
  - Right after the restart `GET /jobs/{id}` shows `status` = `pending` or `processing` with `step` = `fetching_transcript`
  - The job re-runs every step, downloads again, and ends `done`

## Screens

### TC-VTM-22: Form states on the YouTube source
- **App:** Frontend
- **Steps:**
  1. Navigate to http://localhost:5071/, click `YouTube link`
  2. Leave `YouTube link` blank; *(captcha on)* wait for the captcha
  3. Fill `YouTube link` with `   `
  4. Fill `YouTube link` with V2
  5. Select `Vietnamese` from `Caption language`, then click `Upload file`
  6. Reload the page
- **Expected:**
  - Steps 2–3: `Convert` is disabled
  - Step 4: `Convert` is enabled
  - Step 5: `Spoken language` shows `Vietnamese` — one preference shared by both forms
  - Step 6: the source switch is back on `Upload file` and the language is `Auto-detect` again (Redux state is not kept across a reload)

### TC-VTM-23: Recent jobs shows the source
- **App:** Frontend
- **Precondition:** TC-VTM-01 and TC-VTM-04 have run.
- **Steps:**
  1. Navigate to http://localhost:5071/
- **Expected:**
  - The TC-VTM-04 row carries badge `YouTube`, the TC-VTM-01 row badge `Upload`
  - Each row shows `{step label} · {created time}`, a status badge and `View`
  - With a job in progress the list refreshes every 3 s; with none in progress it stops refreshing

### TC-VTM-24: Heading link opens YouTube at the moment
- **App:** Frontend
- **Precondition:** TC-VTM-04 is `done`.
- **Steps:**
  1. Navigate to `/jobs/{id}` of TC-VTM-04
  2. In the result preview, click the timestamp of the second `##` heading
- **Expected:**
  - A new tab opens `https://www.youtube.com/watch?v=vfjegxHDOwI&t={seconds}s`, where `{seconds}` equals the heading's `mm:ss` in seconds
  - The job page stays open in the original tab
  - Clicking `Source` in the summary opens `https://www.youtube.com/watch?v=vfjegxHDOwI` in a new tab

### TC-VTM-25: Captcha switched off for local runs
- **App:** Frontend + API
- **Precondition:** `CAPTCHA_ENABLED=false` in `api/.env.test`, `NEXT_PUBLIC_CAPTCHA_ENABLED=false` in `frontend/.env.local`; stack restarted.
- **Steps:**
  1. Navigate to http://localhost:5071/ and click `YouTube link`
  2. Fill `YouTube link` with V1
  3. `curl -s -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"hello"}'` (no captcha header)
- **Expected:**
  - No captcha widget is rendered and no request goes to `challenges.cloudflare.com`
  - Step 2: `Convert` is enabled without any captcha
  - Step 3: `HTTP 400`, `detail` = `Not a YouTube video link` — the request passes the captcha check instead of answering 403
  - The API log has `Captcha is disabled (CAPTCHA_ENABLED=false); every token is accepted` at startup

### TC-VTM-26: Header menu
- **App:** Frontend
- **Precondition:** TC-VTM-01 has run.
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. Click `Film Analysis` in the header
  3. Click `Film Clone` in the header
  4. Click `Film Studio` in the header
  5. Click `Settings` in the header
  6. Click `Video to Markdown` in the header
  7. Navigate to `/jobs/{id}` of TC-VTM-01
- **Expected:**
  - Every page shows the header items `Video to Markdown`, `Film Analysis`, `Film Clone`, `Film Studio`, `Settings` in that order
  - Step 1: `Video to Markdown` is highlighted
  - Step 2: URL becomes `/film-analysis`, `Film Analysis` is highlighted
  - Step 3: URL becomes `/film-clone`, `Film Clone` is highlighted
  - Step 4: URL becomes `/films`, `Film Studio` is highlighted
  - Step 5: URL becomes `/settings`, `Settings` is highlighted
  - Step 6: URL becomes `/`
  - Step 7: `Video to Markdown` is highlighted

### TC-VTM-27: Recent jobs lists only Video to Markdown jobs
- **App:** Frontend + API
- **Precondition:** TC-VTM-01 has run; a Film Analysis job exists (TC-FA-01).
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. `curl -s 'http://localhost:5070/jobs?type=video_to_markdown&type=youtube_to_markdown'`
  3. `curl -s -o /dev/null -w '%{http_code}' 'http://localhost:5070/jobs?type=nope'`
- **Expected:**
  - Step 1: `Recent jobs` has the TC-VTM-01 row and no TC-FA-01 row
  - Step 2: every item has `type` `video_to_markdown` or `youtube_to_markdown`
  - Step 3: `422`

## Prompt preset

### TC-VTM-28: Conversion uses the chosen preset
- **App:** Frontend + API
- **Precondition:** `claude` CLI logged in. Preset `Caps moments` created with `POST /prompt-presets` `{"name":"Caps moments"}`, then `PUT` with the default prompts except `videoToMarkdown` = the default text followed by `Write every moment title in uppercase letters.` — so it is at v2.
- **Steps:**
  1. Navigate to http://localhost:5071/
  2. Check the `Prompt preset` dropdown
  3. Drop F1 on the `Video` field
  4. Select `Caps moments` from the `Prompt preset` dropdown
  5. *(captcha on)* Wait for the captcha; click `Upload and convert`
  6. Wait until the status badge shows `done`
- **Expected:**
  - Step 2: the default preset is preselected and labelled `{name} (default)`; `Edit presets` links to `/settings?tab=prompt-override&id={its id}`
  - Summary shows `Prompt preset` = `Caps moments v2`
  - `GET /jobs/{id}` → `options.preset.name` = `Caps moments`, `options.prompts.videoToMarkdown` ends with `Write every moment title in uppercase letters.`
  - Every `##` moment title in the preview is in uppercase

### TC-VTM-29: Unknown preset at creation
- **App:** API
- **Steps:**
  1. `curl -i -X POST http://localhost:5070/jobs/youtube-to-markdown -H 'Content-Type: application/json' -d '{"url":"https://www.youtube.com/watch?v=vfjegxHDOwI","language":"auto","presetId":"00000000-0000-0000-0000-000000000000"}'`
  2. From `video-tool/`: `curl -i -X POST http://localhost:5070/jobs/video-to-markdown -F 'file=@downloads/30 Năm Kinh Nghiệm Đầu Tư Gói Gọn Trong Video Này! [vfjegxHDOwI].mp4' -F 'language=auto' -F 'presetId=00000000-0000-0000-0000-000000000000'`
- **Expected:**
  - Both: `HTTP 400`, `detail` = `Prompt preset 00000000-0000-0000-0000-000000000000 not found`
  - No job created; no new folder under `api/storage-test/`

### TC-VTM-30: The job keeps the prompt it was created with
- **App:** API unit
- **Precondition:** Faked `claude` runner recording its `--system-prompt` argument.
- **Steps:**
  1. Create a `video_to_markdown` job with preset P at v1 (`videoToMarkdown` = `Prompt one`)
  2. Save P with `videoToMarkdown` = `Prompt two` (v2)
  3. Run the job through the worker
  4. Run, through the worker, a job inserted with `options` = `{ "language": "auto" }` (no `preset`, no `prompts`)
- **Expected:**
  - Step 3: the runner received `Prompt one`; the job's `options.preset.version` is still `1`
  - Step 4: the runner received the code default of `videoToMarkdown`; the job ends `done`
