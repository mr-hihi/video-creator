# api structure (non-DDD, layered)

```
api/
├── app/
│   ├── main.py            # create_app(), lifespan (build container, start/stop worker)
│   ├── config.py          # Settings (pydantic-settings), APP_ENV → .env.<APP_ENV>
│   ├── container.py       # composition root: builds services, adapters, worker
│   ├── db.py              # Base, UtcDateTime, create_session_factory
│   ├── logger.py          # DailyFileHandler, configure_logging (LOG_DRIVER)
│   ├── common/            # cross-module adapters: process.py (CommandRunner), captcha.py
│   ├── batch/worker.py    # BatchWorker + JobHandler protocol
│   └── modules/<module>/  # one folder per module
│       ├── router.py      # HTTP only
│       ├── service.py     # rules; depends on repository + storage
│       ├── repository.py  # SQL only
│       ├── models.py      # SQLAlchemy models + StrEnums
│       ├── schemas.py     # pydantic request/response DTOs (camelCase)
│       ├── errors.py      # domain errors
│       ├── http_errors.py # error → status code table
│       ├── storage.py     # filesystem paths for the module
│       └── <job_type>/    # one sub-package per job type: handler.py + its adapters + pure logic
├── alembic/versions/      # migrations, NNNN_<slug>.py
├── tests/                 # flat test_<unit>.py, conftest.py sets env
├── storage/ storage-test/ models/ logs/   # runtime, ignored
```

## Modules

| Module | Owns |
| --- | --- |
| `jobs/` | `jobs`, `job_outputs`, the job types and their pipelines (domains 1, 3) |
| `ai_models/` | `AiCaller` and its Claude CLI, Gemini and OpenAI clients, the shared SSE reading and image encoding, the step-model lookup and set-up check, the `aiUsed` response shape (domain 8) |
| `prompt_presets/` | presets, versions, the default prompts and the text the app appends (domain 2) |
| `app_settings/` | `app_settings` (domain 6); the `PATCH /settings/ai-models` save (`ai_model_service.py`, `schemas.py`), which also writes `provider_routes` and `providers.models` (A14) |
| `providers/` | `providers`, `provider_routes`, catalog, encrypted keys, connection test (domain 7) |
| `media_generation/` | `film_generation_requests`, the generation worker, retry policy, media adapters (4.3, 7) |
| `film_clones/` | the four `film_clone*` tables, clone steps, AI reply normalising, clone image targets (domain 5) |
| `films/` | the seven `film_*` tables, episode stages, script writer, scene edits, film request targets, assembly, thumbnails (domain 4) |

## Placement rules

- **Critical** — pure logic (parsing, normalising, rendering) sits in its own module with no I/O: `transcript.py`, `moments.py`, `markdown.py`.
- **Critical** — an adapter for one external program lives next to the job type that uses it (`video_to_markdown/ffmpeg_media.py`). Move it to `app/common/` only when a second job type needs it.
- **Preferred** — the job type sub-package's `handler.py` only orchestrates steps; it holds no parsing or SQL.
- New module → copy [templates/template-non-ddd-structure.md](templates/template-non-ddd-structure.md).
