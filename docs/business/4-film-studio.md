# 4. Tạo phim (Film Studio)

> One file = one domain. Every section below belongs to the **Film Studio** domain. The domain is
> split into sub-domain files under [4-film-studio/](./4-film-studio/); this file is the overview.

Makes AI films as series. A **project** is a series with one look (orientation, style) and a cast taken
from a shared **character library**; each **episode** is one film. For an episode, the AI model (domain 8)
writes the script — scenes with an image prompt, a clip prompt and narration — from an idea or from a
finished Film Analysis (domain 3). The app then generates a reference image per character, a still image per scene, an
image-to-video clip per scene, narration and music, and assembles the episode into an MP4 with subtitles.
An episode can also start from a finished Film Clone (domain 5), whose scenes and images it copies.
It runs on its own, stopping at the points the user chose so they can check the work before more credit
is spent. The pipeline is ported from flowkit (MIT, © 2026 tuannguyenhoangit-droid).

```
Character (library) ◀──N:N──▶ FilmProject (series: orientation, style, default clip length)
                                   └─1:N─▶ Episode (one film: script, stop points, MP4 + .srt)
                                              └─1:N─▶ Scene (image · clip of 4–30 s · narration)
GenerationRequest — one image, clip, narration, music track or thumbnail asked of a provider
```

- Persona: the same single local user as domain 1. Captcha on episode creation only, switched off as in
  domain 1.
- Entities: `FilmProject`, `Character`, `FilmProjectCharacter`, `Style`, `VoiceTemplate`, `Episode`,
  `Scene`, `GenerationRequest` — tables listed in each sub-domain. Film Studio does not use the `jobs`
  table or its worker.
- Prompt: the `filmScript` prompt of a prompt preset (domain 2), copied into the episode at creation; the
  AI model of the `filmScript` step group, read when the call starts (8.1).
- External tools: `ffmpeg` / `ffprobe`, the `claude` CLI, the Gemini API or the OpenAI API (8.2), `whisper-cli` (voice sample
  text), and the media providers below.

## Media providers

Film Studio asks a provider for one of five media kinds; Film Clone (domain 5) asks the same providers for
`image`. Which provider answers is decided per request when it is created:

| Media kind | Input | Output | Provider |
|---|---|---|---|
| `image` | prompt, reference images, aspect | one image | Film Studio: `filmStudioImageProvider`; Film Clone: `filmCloneImageProvider` (6.1); `null` → the `image` route (7.2) |
| `edit_image` | source image, edit prompt, reference images | one image | as `image` |
| `video` | start image, prompt, clip length, aspect | one clip — joined from segments when the model's clips are shorter (7.1) | `filmStudioClipProvider` (6.1); `null` → the `video` route (7.2) |
| `speech` | text, the narrator voice (4.1), language | one audio file | the `speech` route (7.2) |
| `music` | prompt, minimum length | one audio file | the `music` route (7.2) |

- `google_flow` → Google Flow through the Chrome extension, in the user's signed-in Flow tab. `sd_webui`
  (`image` and `edit_image` only) → the user's Stable Diffusion WebUI / Forge. The others → the provider's
  API.
- How a provider is reached, its keys, models, limits and pacing belong to Provider Settings (domain 7).
  Film Studio stores only the provider id each request used.

## Document structure

| # | Sub-domain | Contents |
|---|---|---|
| 4.1 | [Projects & library](./4-film-studio/4.1-projects-and-library.md) | `FilmProject`, the character library, styles, voice templates, link and delete rules |
| 4.2 | [Episodes & script](./4-film-studio/4.2-episodes-and-script.md) | `Episode`, sources (idea / film analysis / film clone), status workflow, stop points, `writing_script` |
| 4.3 | [Scenes & generation](./4-film-studio/4.3-scenes-and-generation.md) | `Scene`, `GenerationRequest`, worker, retries, prompts sent, dependency and reset rules, manual edits |
| 4.4 | [Audio & assembly](./4-film-studio/4.4-audio-and-assembly.md) | narration, music, assembling the MP4, subtitles, thumbnails |
| 4.5 | [Screens](./4-film-studio/4.5-screens.md) | `/films`, project detail, episode workspace, `/films/library` |

---

## API endpoints

Same JSON and error conventions as domain 1. Generation routes answer `202` with the
`GenerationRequest` they queued. Only `POST /films/projects/{id}/episodes` needs `X-Captcha-Token`
(skipped when `CAPTCHA_ENABLED=false`).

```
GET    /films/projects?status=active|archived              — FilmProject[] newest first (default active)
POST   /films/projects                                     — 201 FilmProjectDetail (4.1)
GET    /films/projects/{id}                                — FilmProjectDetail = FilmProject + characters + episodes + open requests of its characters
PATCH  /films/projects/{id}                                — settings (4.1) → FilmProjectDetail
POST   /films/projects/{id}/archive                        — FilmProject
POST   /films/projects/{id}/unarchive                      — FilmProject
DELETE /films/projects/{id}                                — 204
PUT    /films/projects/{id}/characters/{characterId}       — link → 204
DELETE /films/projects/{id}/characters/{characterId}       — unlink → 204
POST   /films/projects/{id}/characters/{characterId}/generate-reference — 202
POST   /films/projects/{id}/characters/{characterId}/edit-reference     — { "prompt" } → 202
POST   /films/projects/{id}/characters/generate-missing    — 202 GenerationRequest[] (references not done)

GET    /films/characters?type=…&q=…                        — Character[] by name
POST   /films/characters                                   — 201 Character
GET    /films/characters/{id}                              — Character + linked projects
PATCH  /films/characters/{id}                              — Character
DELETE /films/characters/{id}                              — 204
POST   /films/characters/{id}/reference                    — multipart `file` (upload) → Character

GET    /films/styles                                       — Style[] built-in first, then custom by name
POST   /films/styles                                       — 201 Style
PATCH  /films/styles/{id}                                  — Style (custom only)
DELETE /films/styles/{id}                                  — 204 (custom only)
GET    /films/voices                                       — VoiceTemplate[] by name
POST   /films/voices                                       — multipart `file` + `name` + `sampleText?` → 201
PATCH  /films/voices/{id}                                  — { "name", "sampleText", "description" }
DELETE /films/voices/{id}                                  — 204
POST   /films/voices/{id}/consent                          — multipart `file` → VoiceTemplate
DELETE /films/voices/{id}/consent                          — 204

POST   /films/projects/{id}/episodes                       — 201 Episode (4.2)
GET    /films/episodes/{id}                                — EpisodeDetail = Episode + scenes + open requests
PATCH  /films/episodes/{id}                                — editable fields (4.2) → Episode
DELETE /films/episodes/{id}                                — 204
POST   /films/episodes/{id}/start | continue | stop | resume — Episode (4.2)
POST   /films/episodes/{id}/rewrite-script                 — Episode
POST   /films/episodes/{id}/assemble                       — Episode (4.4)
POST   /films/episodes/{id}/thumbnails                     — 202 GenerationRequest[] (4.4)
POST   /films/episodes/{id}/thumbnail                      — { "candidate": 1-4 } → Episode

POST   /films/episodes/{id}/scenes                         — { "afterPosition"?, … } → 201 Scene (4.3)
PATCH  /films/scenes/{id}                                  — prompts, narration, characters, position, trim
DELETE /films/scenes/{id}                                  — 204
POST   /films/scenes/{id}/image                            — multipart `file` (upload) → Scene
POST   /films/scenes/{id}/generate-image | generate-clip | generate-narration — 202
POST   /films/scenes/{id}/edit-image                       — { "prompt" } → 202
POST   /films/requests/{id}/cancel                         — GenerationRequest (4.3 § Cancel)

GET    /films/files/{path}                                 — one file under storage/films/
GET    /films/episodes/{id}/download?file=video|subtitles|thumbnail — attachment (4.4)
```

Errors per route are listed in the sub-domain that owns the rule.

## Configuration (`api/.env`)

| Key | Default | Used in |
|---|---|---|
| `FILM_WORKER_POLL_INTERVAL_SEC` | `5` | 4.3 |
| `FILM_REQUEST_MAX_ATTEMPTS` | `5` | 4.3 |
| `FILM_SCRIPT_TIMEOUT_SEC` | `600` | 4.2 — every provider |
| `FILM_ASSEMBLY_TIMEOUT_SEC` | `3600` | 4.4 |
| `FILM_MUSIC_VOLUME` | `0.2` | 4.4 |
| `FILM_UPLOAD_MAX_MB` | `20` | 4.1, 4.3 |

Shared: `CAPTCHA_ENABLED`, `MEDIA_TIMEOUT_SEC`, `WHISPER_*`. AI model keys: domain 8. Provider keys,
models and pacing: Provider Settings (domain 7).

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- AI review or scoring of clips.
- 4K upscale, start-and-end-frame clips (Veo chaining) and reference-to-video clips.
- YouTube upload, SEO text and channel rules.
- Credit or cost tracking.
- Both orientations in one project; a version history of generated images, clips or audio — a new one
  replaces the old.
- Text overlays, intro / outro / logo branding, sound-effect layering.
- Duplicating or exporting a project.
