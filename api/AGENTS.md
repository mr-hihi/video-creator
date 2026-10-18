# AGENTS.md — api

> **Read documentation first.** Start at [docs/README.md](docs/README.md). Workspace-wide rules live in
> [../AGENTS.md](../AGENTS.md) and [../docs/](../docs/README.md); this hub holds only the api delta.

## Project Overview

FastAPI service (Python 3.13, `uv`) that stores uploaded videos, owns the job, prompt preset, film clone,
Film Studio, settings, provider and generation request tables in MySQL, and runs a long-polling batch worker and a media
generation worker **inside the API process**. The batch worker shells out to ffmpeg, whisper.cpp and `yt-dlp`,
and asks the AI model Settings picks for each step — the `claude` CLI, the Gemini API or the OpenAI API; the
generation worker calls the media providers over HTTP. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation links

| Topic | Doc |
| --- | --- |
| Index | [docs/README.md](docs/README.md) |
| Architecture (layers, batch, pipeline) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Module layout | [docs/structure.md](docs/structure.md) |
| Conventions (Python delta) | [docs/coding-conventions.md](docs/coding-conventions.md) |
| Style (ruff) | [docs/coding-style.md](docs/coding-style.md) |
| Testing (pytest) | [docs/testing-strategy.md](docs/testing-strategy.md) |
| Decisions | [docs/decisions.md](docs/decisions.md) |
| Workflows / templates | [docs/workflows/README.md](docs/workflows/README.md) · [docs/templates/README.md](docs/templates/README.md) |
| Shared stack, tooling, contract | [../docs/technology.md](../docs/technology.md) · [../docs/workspace-tooling.md](../docs/workspace-tooling.md) · [../docs/dependency-graph.md](../docs/dependency-graph.md) |

## AI Agent Guidelines

### Do

- Keep the path `router → service → repository`; the service depends on the repository, never on a SQLAlchemy session.
- Reach every external program through an adapter over `CommandRunner` (`app/common/process.py`).
- Add a job type as a handler registered in `app/container.py` — never a new worker or thread.
- Map new domain errors to HTTP in `app/modules/jobs/http_errors.py`.

### Don't

- Import SQLAlchemy or `Session` in a service, handler or router.
- Call `subprocess` directly outside `CommandRunner`.
- Raise `HTTPException` from a service.
- Block the upload request on processing — the request only saves the file and inserts the job.
- Open a DB connection in a unit test.
- Log transcript text or upload contents.

### When to read what

| Task | Read first | Then | Scaffold template |
| --- | --- | --- | --- |
| New video operation (job type) | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [workflow-adding-a-new-job-type.md](docs/workflows/workflow-adding-a-new-job-type.md) | [template-worker-batch.md](docs/templates/template-worker-batch.md) |
| New / changed endpoint | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [workflow-implementing-a-new-api-endpoint.md](docs/workflows/workflow-implementing-a-new-api-endpoint.md) | [template-api-endpoint.md](docs/templates/template-api-endpoint.md) |
| Schema change | [structure.md](docs/structure.md) | [workflow-database-migrations.md](docs/workflows/workflow-database-migrations.md) | [template-database-migration.md](docs/templates/template-database-migration.md) |
| New module / feature | [structure.md](docs/structure.md) | [workflow-adding-a-new-feature.md](docs/workflows/workflow-adding-a-new-feature.md) | [template-non-ddd-structure.md](docs/templates/template-non-ddd-structure.md) |
| Job failing / stuck | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [workflow-debugging.md](docs/workflows/workflow-debugging.md) | — |
| Tests | [testing-strategy.md](docs/testing-strategy.md) | [../docs/workflows/workflow-running-tests.md](../docs/workflows/workflow-running-tests.md) | — |

### Reading by phase

| Phase | Do | Read |
| --- | --- | --- |
| Analyze | Pick the task row above | [../docs/project-overview.md](../docs/project-overview.md) |
| Research | Understand layers, batch, pipeline | [ARCHITECTURE.md](docs/ARCHITECTURE.md), [structure.md](docs/structure.md), [../docs/technology.md](../docs/technology.md) |
| Plan | Workflow first, then template; `REQUIRED READING (api)` per step | [decisions.md](docs/decisions.md), [workflows/README.md](docs/workflows/README.md) |
| Implement | Code in the package style | [coding-conventions.md](docs/coding-conventions.md), [coding-style.md](docs/coding-style.md), [structure.md](docs/structure.md) + root conventions |
| Validate | Tests (C2) + ruff | [testing-strategy.md](docs/testing-strategy.md) |

### Dispatching subagents (MANDATORY)

Every brief opens with `REQUIRED READING (api): <files for the phase>`, e.g.
`REQUIRED READING (api): api/docs/ARCHITECTURE.md, api/docs/coding-conventions.md, api/docs/coding-style.md, api/docs/structure.md, docs/coding-conventions.md`.
A subagent loads no `AGENTS.md`; the `PreToolUse(Task)` hook blocks a brief without the line.

## Important Notes

- **Critical** — `APP_ENV` picks `.env.<APP_ENV>` on top of `.env`; tests force `DATABASE_URL=sqlite://`, `LOG_DRIVER=stdout`, `BATCH_ENABLED=false` in `tests/conftest.py`.
- **Critical** — never commit `storage/`, `storage-test/`, `models/`, `logs/`, `.env*` (except `.env.example`).
- Run `sh run.sh migrate` before the first start; the worker's `requeue_processing` needs the `jobs` table.
