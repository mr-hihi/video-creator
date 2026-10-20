# Dependency graph

```
frontend ──HTTP──▶ api ──SQLAlchemy──▶ MySQL (video_tool / video_tool_test)
                    ├──subprocess──▶ ffmpeg / ffprobe
                    ├──subprocess──▶ whisper-cli (+ api/models/*.bin)
                    ├──subprocess──▶ claude (CLI, user's login)
                    ├──HTTPS──────▶ Gemini API (generativelanguage.googleapis.com, `google` provider key)
                    ├──HTTPS──────▶ OpenAI Responses API (api.openai.com, `openai` provider key)
                    ├──subprocess──▶ yt-dlp (api/.venv, Node as JS runtime) ──▶ YouTube
                    ├──HTTPS──────▶ captcha provider siteverify
                    ├──HTTPS──────▶ media providers (Google AI, fal.ai, Replicate, OpenAI, ElevenLabs)
                    └──HTTP───────▶ local servers at their base URL (SD WebUI, tools/local-servers/*)
```

There is no shared code package. The only internal edge is the HTTP contract below.

## HTTP contract (api → frontend)

JSON bodies are camelCase; datetimes are ISO-8601 in UTC (`...Z`); errors are `{ "detail": string }`, except FastAPI validation (422) where `detail` is an array of `{ msg, … }`.

| Route | Answer | Errors |
| --- | --- | --- |
| `POST /jobs/video-to-markdown` (multipart `file`, `language`, `presetId?`; header `X-Captcha-Token`) | 201 `Job` | 400 bad type/language/preset · 403 captcha · 413 too large · 422 no `file` |
| `POST /jobs/youtube-to-markdown` (JSON `{ url, language, presetId? }`; header `X-Captcha-Token`) | 201 `Job` | 400 bad link / video / live / too long / language / preset · 403 captcha · 422 no `url` · 502 YouTube unreachable |
| `POST /jobs/film-analysis` (multipart `file`, `language`, `presetId?`, `maxFrames?`; captcha) | 201 `Job` | as the upload route + 400 max frames |
| `POST /jobs/youtube-film-analysis` (JSON `{ url, language, presetId?, maxFrames? }`; captcha) | 201 `Job` | as the YouTube route + 400 max frames |
| `POST /jobs/{id}/film-analysis-rerun` (JSON `{ presetId? }`; captcha) | 201 `Job` | 400 preset · 403 captcha · 404 · 409 not an analysis / no video notes |
| `GET /jobs?type=…&limit=1..200` | `Job[]` newest first; `type` repeatable | 422 bad limit / type |
| `GET /jobs/{id}` | `JobDetail` = `Job` + `markdown` (Video to Markdown, `done`) + `outputs` (Film Analysis) | 404 |
| `DELETE /jobs/{id}` | 204 | 404 · 409 not an analysis / still running |
| `GET /jobs/{id}/files/{path}` | raw file from the job output | 404 unknown job / missing / outside output · 409 not ready |
| `GET /jobs/{id}/download` | `application/zip` attachment | 404 unknown job · 409 not done / film analysis |
| `/prompt-presets` routes (list, create, get, save, delete, default, duplicate, versions, restore, export, import, defaults) | see [business/2-prompt-presets.md](business/2-prompt-presets.md) | 400 · 404 · 409 · 413 · 422 |
| `/film-clones` routes (create upload / YouTube with captcha, list, detail, delete, localization, write-script, resume, relocalize, asset and scene edits, generate, files) | see [business/5-film-clone.md](business/5-film-clone.md) § API endpoints | 400 · 403 · 404 · 409 · 413 · 422 · 502 |
| `/films` routes (projects, cast, characters, styles, voices, episodes with captcha on create, stage actions, scenes, thumbnails, downloads, files) | see [business/4-film-studio.md](business/4-film-studio.md) § API endpoints | 400 · 403 · 404 · 409 · 413 · 422 |
| `GET` / `PATCH /settings` | `{ scriptLanguage, aiModel, aiStepModels, inputMode, filmAnalysisInputMode, filmCloneInputMode, filmCloneImageProvider, filmStudioImageProvider, filmStudioClipProvider }` — [business/6-settings.md](business/6-settings.md) | 400 · 422 |
| `PATCH /settings/ai-models` (JSON `{ aiModel?, aiStepModels?, inputMode?, filmAnalysisInputMode?, routes?, models? }`) | `{ settings, providers }`, saved all or none — see [business/6-settings.md](business/6-settings.md) § API endpoints | 400 · 404 · 422 |
| `/settings/providers` routes (list, provider update, test, Flow resume / open tab) | see [business/7-provider-settings.md](business/7-provider-settings.md) § API endpoints | 400 · 404 · 409 · 422 |

`Job.type` is one of `video_to_markdown`, `youtube_to_markdown`, `film_analysis`, `youtube_film_analysis`,
`film_analysis_rerun`, `film_clone`, `youtube_film_clone`. `Job.options` holds the per-source input (`language`, `url`, `videoId`, `captionKind?`,
`maxFrames`, `frameCounts?`, `rerunOfJobId`) plus `preset` and `prompts` copied from a prompt preset and
`inputMode` copied from Settings — `inputMode` for Video to Markdown, `filmAnalysisInputMode` for Film
Analysis, `filmCloneInputMode` for the stage 1 job of a film clone (not on a rerun, except a rerun of a
`full_video` analysis). `Job`, `FilmClone` and `Episode` carry `aiUsed`
(`{ "{step}": { provider, model, label } }`, the model each AI step started with); `FilmCloneDetail` carries
`aiActivity` — [business/8-ai-models.md](business/8-ai-models.md). Every route that creates a job, clone or
episode also answers 409 `{provider name} is not set up — open Settings` when the model of a step group the run
uses belongs to a provider that is not set up, and 409 `{group label} needs a Google AI model — open Settings`
when a group that needs Google AI (`audio` in `whole_video`, `filmAnalysis` in `full_video`) has another model.

## Rules

- **Critical** — change the contract on both sides in one change: `api/app/modules/{jobs,prompt_presets,film_clones,films,app_settings,providers}/schemas.py` + `router.py` and `frontend/src/features/{jobs,promptPresets,filmClones,films,settings,providers}/types.ts` + `queries.ts`.
- **Critical** — Markdown image paths stay relative (`images/…`) — see [frontend ADR F3](../frontend/docs/decisions.md).
- **Preferred** — add new job types under new routes (`POST /jobs/<type>`), keeping the shared `Job` shape.
