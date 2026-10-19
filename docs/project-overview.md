# Project overview

## What it is

A local, single-user tool that runs **video operations as jobs**. Operations are added one job type at
a time; the job table, queue and worker are shared by all of them.

## Job types

| Type | Input | Output | Status |
| --- | --- | --- | --- |
| `video_to_markdown` | a video (`.mp4 .mov .mkv .webm .avi .m4v`) + language (`auto` or ISO code) | `<name>.md` + `images/` + `result.zip` | shipped |
| `youtube_to_markdown` | a YouTube link + caption language (`auto` or ISO code) | same, with the YouTube link and timestamp links in the `.md` | shipped |
| `film_analysis` / `youtube_film_analysis` | a film (upload or YouTube link) + language + max frames (10–1000) | video notes + character image, character voice and scene prompts, stored in `job_outputs` | shipped |
| `film_analysis_rerun` | a finished analysis + another prompt preset | the three prompt sets again, from the copied notes and frames | shipped |
| `film_clone` / `youtube_film_clone` | a film (upload or YouTube link) + language + max frames (10–1000) | video notes, an asset library and one shot per frame for a Film Clone (stages 1–2) | shipped |

A **Film Clone** (`film_clones`) continues after its job: the user picks a target country and what to
change, the AI model proposes replacements, the app writes one scene per shot and makes a new image per scene
through the media providers. Business spec: [business/5-film-clone.md](business/5-film-clone.md).

**Film Studio** (`film_*` tables) makes AI films as series: a project holds the look and a cast from a
shared character library and a story bible; each episode, of any length, runs eight stages on its own — the AI
model writes an outline of parts, then each part's scenes (from an idea, a finished Film Analysis or a finished
Film Clone), then rewrites the story bible and the episode summary later episodes read; reference images, scene
images, image-to-video clips, narration and music are made through the media providers, and ffmpeg assembles
the MP4 and `.srt`.
It pauses at the stop points the user ticked. Ported from flowkit (MIT). Business spec:
[business/4-film-studio.md](business/4-film-studio.md).

Images, clips, speech and music are made by **media providers** (Google Flow, Google AI, fal.ai, Replicate,
OpenAI, ElevenLabs, local Stable Diffusion WebUI / OmniVoice / ACE-Step / YuE) through a second worker in
the API process (`film_generation_requests`). Keys, models, routing and pacing are set on `/settings`:
[business/6-settings.md](business/6-settings.md), [business/7-provider-settings.md](business/7-provider-settings.md).

Every job copies the prompts of a **prompt preset** (`prompt_presets`, versioned, 20 kept) when it is
created; the user edits presets in the `Prompt override` tab of `/settings`. Business specs:
[business/2-prompt-presets.md](business/2-prompt-presets.md),
[business/3-film-analysis.md](business/3-film-analysis.md).

`video_to_markdown` pipeline: extract 16 kHz audio (ffmpeg) → transcribe (whisper.cpp) → the AI model
chosen in Settings (Claude via `claude -p`, Gemini or OpenAI) picks key moments from the transcript — and, in the
`whole_video` input mode, from one frame per second too → capture one frame per moment
(ffmpeg) → write Markdown where each moment is a `##` heading with its screenshot and the transcript
that follows it.

## Job lifecycle

```
pending ──claim──▶ processing ──▶ done
                       │  └──────▶ failed (error_message kept, step kept)
                       └─ API stopped mid-job ─▶ back to pending on next start
```

`youtube_to_markdown` reads the transcript from the video's YouTube captions instead of whisper, then
downloads the video with `yt-dlp` only to capture the frames. Business spec:
[business/1-video-to-markdown.md](business/1-video-to-markdown.md).

Steps reported while `processing`:

| Type | Steps |
| --- | --- |
| `video_to_markdown` | `extracting_audio → transcribing → picking_moments → capturing_frames → writing_markdown` |
| `youtube_to_markdown` | `fetching_transcript → picking_moments → downloading_video → capturing_frames → writing_markdown` |
| `film_analysis` | `extracting_audio → transcribing → picking_moments → detecting_scenes → capturing_frames → writing_markdown → writing_character_image_prompts → writing_character_voice_prompts → writing_scene_prompts` |
| `youtube_film_analysis` | `fetching_transcript → picking_moments → downloading_video → detecting_scenes → capturing_frames → writing_markdown →` the three prompt steps |
| `film_analysis_rerun` | the three prompt steps |
| `film_clone` / `youtube_film_clone` | as `film_analysis` / `youtube_film_analysis` up to `writing_markdown`, then `extracting_assets → analyzing_shots` |

## Packages

| Package | Role |
| --- | --- |
| `api/` | Stores uploads, owns the `jobs`, `job_outputs`, `prompt_presets*`, `film_clone*`, `film_*` (Film Studio), `app_settings`, `providers*` and `film_generation_requests` tables, runs the batch and generation workers and the Google Flow extension socket, serves results |
| `frontend/` | Menus: Video to Markdown (form, job list, job detail + zip), Film Analysis (form, history, detail with copyable prompts, rerun, delete), Film Clone (form, history, clone detail with assets, shots, localization and script), Film Studio (projects, library, episode workspace), Settings (General with provider sub-tabs, AI models, Prompt override with editor, history and import / export, Film Clone, Film Studio) |
| `tools/local-servers/` | HTTP adapters the user runs next to OmniVoice, ACE-Step and YuE (not part of the API process) |
| `tools/mock-providers/` | Mock Google Flow extension and local-provider stand-ins for E2E runs on the test stack (not part of the API process) |
| `tools/mock-ai/` | Mock `claude` CLI, Gemini, OpenAI and whisper.cpp for E2E runs on the test stack (not part of the API process) |
| `extension/google-flow/` | Chrome extension (ported from flowkit, MIT) that runs Google Flow calls in the user's signed-in Flow tab; loaded unpacked, talks to the API over a WebSocket |

## Users

One person on their own Mac, uploading screen recordings, meetings or tutorials. No login and no
multi-tenant concerns. A captcha on job creation is the only abuse guard; local runs turn it off with
`CAPTCHA_ENABLED=false`.
