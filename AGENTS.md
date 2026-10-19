# AGENTS.md — video-tool workspace

> **Read documentation first.** Start at [docs/README.md](docs/README.md), then the target package's
> `AGENTS.md`. Never edit code before the Implement-phase docs of the package you touch (hook-enforced
> for frontend `.ts/.tsx`; not enforced for `api/**/*.py`).

## Project Overview

Local tool for video operations. Each operation is a **job**: the frontend uploads a video, the API
stores it and queues a job, and a batch worker inside the API process runs it. Video to Markdown writes a
`.md` file with the transcript and screenshots at the key moments; Film Analysis turns a film into
character image, character voice and scene prompts; Film Clone rewrites a film as a localized script
with new scene images. Film Studio makes AI films as series — script, reference and scene images, clips,
narration, music and an assembled MP4 — through the media providers. Every job copies the AI prompts of
a prompt preset; each AI step asks the model Settings picks for it (Claude CLI, Gemini or OpenAI).
Details: [docs/project-overview.md](docs/project-overview.md).

<!-- BEGIN AUTO-MANAGED: business-docs (/ba-add) -->
## Business domain docs — MUST READ BEFORE ANY WORK

Business specs under `docs/business/` are the **source of truth** for behavior, data model,
workflow, API surface and permissions. Code is the implementation, not the spec.

**Mandatory protocol — before writing, editing, reviewing or testing ANY code:**

1. Open the index `docs/business.md` and identify which domain(s) the task touches.
2. Read the full business doc of every touched domain — including every sub-domain file under
   `docs/business/{N}-{slug}/` when the domain is split.
3. Read the matching test cases in `docs/test-cases/{N}-{slug}.md` before changing behavior.
4. If code and spec disagree → STOP and ask. Never silently treat the code as the spec.
5. If the change alters behavior → update the business doc + test cases in the SAME change.
   Specs describe the current state; they are never a changelog.

| # | Domain | Business doc | Test cases |
|---|---|---|---|
| 1 | Video to Markdown | `docs/business/1-video-to-markdown.md` | `docs/test-cases/1-video-to-markdown.md` |
| 2 | Prompt Presets | `docs/business/2-prompt-presets.md` | `docs/test-cases/2-prompt-presets.md` |
| 3 | Film Analysis | `docs/business/3-film-analysis.md` | `docs/test-cases/3-film-analysis.md` |
| 4 | Film Studio (split) | `docs/business/4-film-studio.md` | `docs/test-cases/4-film-studio.md` |
| 5 | Film Clone | `docs/business/5-film-clone.md` | `docs/test-cases/5-film-clone.md` |
| 6 | Settings | `docs/business/6-settings.md` | `docs/test-cases/6-settings.md` |
| 7 | Provider Settings | `docs/business/7-provider-settings.md` | `docs/test-cases/7-provider-settings.md` |
| 8 | AI Models | `docs/business/8-ai-models.md` | `docs/test-cases/8-ai-models.md` |

Skip only for: typo / formatting fixes, dependency bumps, and pure read-only questions.
<!-- END AUTO-MANAGED: business-docs -->

## Package inventory

| Package | Kind | Purpose | Docs |
| --- | --- | --- | --- |
| `api/` | App — backend (Python 3.13, FastAPI) | REST API + in-process batch worker (ffmpeg, whisper.cpp, `claude` CLI / Gemini API / OpenAI API, `yt-dlp`) and media generation worker (provider HTTP APIs) | [api/AGENTS.md](api/AGENTS.md) |
| `frontend/` | App — frontend (Next.js 16, Node 24) | Video to Markdown, Film Analysis, Film Clone, Film Studio and Settings menus | [frontend/AGENTS.md](frontend/AGENTS.md) |
| `tools/local-servers/` | Scripts (Python, run by the user) | HTTP adapters for the local OmniVoice, ACE-Step and YuE models | [tools/local-servers/README.md](tools/local-servers/README.md) |
| `tools/mock-providers/` | Script (Python, test stack only) | Mock Google Flow extension + SD WebUI / OmniVoice / ACE-Step stand-ins, so E2E runs need no credit | [tools/mock-providers/README.md](tools/mock-providers/README.md) |
| `tools/mock-ai/` | Scripts (Python, test stack only) | Mock `claude` CLI, Gemini, OpenAI and whisper.cpp, with failure scenarios and a call log, so AI steps run E2E without credit | [tools/mock-ai/README.md](tools/mock-ai/README.md) |
| `extension/google-flow/` | Chrome extension (MV3, loaded unpacked) | Google Flow bridge ported from flowkit (MIT); talks to the API on `FLOW_WS_PORT` | [extension/google-flow/README.md](extension/google-flow/README.md) |

There is no shared library and no JS workspace manager. `run.sh` is the only workspace tool.

## Workspace tooling

| Task | Command |
| --- | --- |
| Start dev stack (api :4020 + frontend :4021) | `sh run.sh start` |
| Start fenced test stack (:5070 / :5071, test DB) | `sh run.sh start_test` |
| Apply / create migrations | `sh run.sh migrate [deploy\|dev <name>\|test\|status]` |
| API unit tests | `sh run.sh test` |
| Download the whisper model | `sh run.sh setup_whisper` |

Full reference: [docs/workspace-tooling.md](docs/workspace-tooling.md).

## Internal dependency graph

```
frontend ──HTTP (NEXT_PUBLIC_API_URL)──▶ api ──▶ MySQL · ffmpeg · whisper-cli · claude CLI · Gemini API · OpenAI API · yt-dlp · media provider APIs
extension ──WebSocket (FLOW_WS_PORT)──▶ api
```

An API contract change (routes, JSON fields, status codes) reaches `frontend/src/features/jobs/types.ts`
and `queries.ts`. See [docs/dependency-graph.md](docs/dependency-graph.md).

## Documentation links

| Topic | Doc |
| --- | --- |
| Index + reading order | [docs/README.md](docs/README.md) |
| Product overview | [docs/project-overview.md](docs/project-overview.md) |
| Dependency graph + API contract | [docs/dependency-graph.md](docs/dependency-graph.md) |
| Workspace tooling (`run.sh`, ports) | [docs/workspace-tooling.md](docs/workspace-tooling.md) |
| Technology | [docs/technology.md](docs/technology.md) |
| Workspace structure | [docs/structure.md](docs/structure.md) |
| Shared conventions / style | [docs/coding-conventions.md](docs/coding-conventions.md) · [docs/coding-style.md](docs/coding-style.md) |
| Testing strategy | [docs/testing-strategy.md](docs/testing-strategy.md) |
| Workspace decisions (ADRs) | [docs/decisions.md](docs/decisions.md) |
| Feature design notes | [docs/design/video-to-markdown.md](docs/design/video-to-markdown.md) |
| Workflows | [docs/workflows/README.md](docs/workflows/README.md) |

## AI Agent Guidelines

### Do

- Resolve which package a task touches (inventory above) before reading anything else.
- Read that package's Implement docs before editing: `coding-conventions.md`, `coding-style.md`, `structure.md`.
- Follow the existing layer path. API: router → service → repository. Frontend: page → template → organism → query hook → `lib/api/client.ts`.
- Change the API and `frontend/src/features/jobs/types.ts` in the same change when the contract moves.

### Don't

- Commit `.env*` (except `.env.example`), `api/storage*/`, `api/models/`, `logs/`.
- Put secrets in `NEXT_PUBLIC_*` or in any committed file.
- Add a comment that restates code. Only a hidden constraint earns one line.
- Leave behaviour untested in `api/`.

### When to read what

| Package | Task | Read first | Then | Scaffold template |
| --- | --- | --- | --- | --- |
| api | New job type (video operation) | `api/docs/ARCHITECTURE.md` | `api/docs/workflows/workflow-adding-a-new-job-type.md` | `api/docs/templates/template-worker-batch.md` |
| api | New / changed endpoint | `api/docs/ARCHITECTURE.md` | `api/docs/workflows/workflow-implementing-a-new-api-endpoint.md` | `api/docs/templates/template-api-endpoint.md` |
| api | DB schema change | `api/docs/structure.md` | `api/docs/workflows/workflow-database-migrations.md` | `api/docs/templates/template-database-migration.md` |
| api | New module | `api/docs/structure.md` | `api/docs/workflows/workflow-adding-a-new-feature.md` | `api/docs/templates/template-non-ddd-structure.md` |
| frontend | New component | `frontend/docs/structure.md` | `frontend/docs/workflows/workflow-adding-a-component.md` | `frontend/docs/templates/template-component.md` |
| frontend | New page / route | `frontend/docs/ARCHITECTURE.md` | `frontend/docs/workflows/workflow-adding-a-page.md` | `frontend/docs/templates/template-page.md` |
| frontend | API call | `frontend/docs/state-management.md` | `frontend/docs/workflows/workflow-implementing-api-calls.md` | `frontend/docs/templates/template-api-client.md` |
| frontend | UI state | `frontend/docs/state-management.md` | `frontend/docs/workflows/workflow-adding-redux-state.md` | `frontend/docs/templates/template-redux-state.md` |
| both | Contract change | `docs/dependency-graph.md` | both packages' endpoint / API-call workflows | — |
| any | Tests | `docs/testing-strategy.md` | `docs/workflows/workflow-running-tests.md` | — |

### Reading by phase

| Phase | Do | Read |
| --- | --- | --- |
| Analyze | Frame the task, locate the package(s) | `docs/project-overview.md`, inventory, `docs/dependency-graph.md` |
| Research | Understand the package + blast radius | the package's `docs/ARCHITECTURE.md` + `docs/structure.md`, `docs/workspace-tooling.md` |
| Plan | Pick workflow(s) first, then template(s); give each step its `REQUIRED READING` | `docs/decisions.md` + the package's `docs/decisions.md`, its `workflows/README.md` → `templates/README.md` |
| Implement | Write code in the package's style | the package's `coding-conventions.md` + `coding-style.md` + `structure.md` (+ root ones), chosen workflow/template |
| Validate | Test + lint the package; check the other side of a contract change | `docs/testing-strategy.md`, the package's `docs/testing-strategy.md` |

### Dispatching subagents (MANDATORY)

A subagent starts fresh: it never loads `AGENTS.md`, only its brief. Every plan step and every brief
MUST open with a `REQUIRED READING` line that names the **package** and that phase's files, e.g.
`REQUIRED READING (api): api/docs/ARCHITECTURE.md, api/docs/coding-conventions.md, api/docs/coding-style.md, api/docs/structure.md, docs/coding-conventions.md`.
The `PreToolUse(Task)` hook blocks a brief without that line. It checks only that the line exists,
so naming the right files is the dispatcher's job.

## Important Notes

- **Critical** — never start the dev stack (`run.sh start` / `npm run dev` / `uvicorn` on 4020 / 4021) from an agent; ask the user to run it, then verify with `curl`. An agent may start the fenced test stack (`sh run.sh start_test`, 5070 / 5071) in the background for E2E checks, reusing one already up, and stops it once the run is recorded.
- **Critical** — the batch worker lives inside the API process: stopping the API stops batch work, and restarting it requeues interrupted jobs.
- Run migrations before the first start: `sh run.sh migrate` (dev) / `sh run.sh migrate test`.
- Whisper needs `brew install whisper-cpp` + `sh run.sh setup_whisper`; AI calls need a logged-in `claude` CLI, or the `google` / `openai` provider key when Settings picks a Gemini / OpenAI model.
- Env files: every app has `.env.example` (committed) + `.env`, `.env.local`, `.env.stg`, `.env.prod`, `.env.test` (ignored).
- Deploy targets in `run.sh` are blank placeholders — fill them locally, never commit credentials.
- Open Claude Code **in `video-tool/`**: from the parent `hihi-tools/` checkout the `.claude/` hooks never load, and this file loads only on demand once a file under `video-tool/` is read.

<!-- SHARED-CLAUDE-START -->

## nodejs caution

Claude Code requires Node.js 18+, and the Node.js used inside a Claude Code session may differ from
the version the project requires. Determine the correct version from `.node-version` or
`package.json#engines`, and run commands through whatever version manager the project uses (e.g.
nvm, asdf, Volta, nodenv). If a Node.js command errors, check those files first and re-run with the
project's version.

Occasionally, errors may occur during pre-commit when executing git commit, and resolving them can
be quite difficult. Ask the user for permission before adding --no-verify.

## .claude directory

The `.claude` directory is primarily for managing Claude Code configuration files, but it can also
be used for the following purposes:

- `.claude/docs/`: local working notes / scratch docs — not git-managed
- `.claude/temp/`: A place to store temporary files needed for verification work
- `.claude/reports/`: A place to store task investigation results

As a general rule, files placed under `.claude/` are not managed by git. However,
`.claude/settings.json` and `.claude/**/*.project.*` are kept under git control.

## docs directory

Alongside `.claude/`, the project has a top-level `docs/` directory — git-managed and committed to the
repo. That `docs/` directory is the canonical documentation hub — not `.claude/docs/`.

## coding discipline

When writing or changing code (these bias toward caution over speed — use judgment on trivial tasks):

- **Think first.** State your assumptions. If a request has multiple interpretations or anything is
  unclear, stop and ask — don't pick silently. If a simpler approach exists, say so.
- **Simplicity.** Write the minimum code that solves the task. No speculative features, no
  abstractions for single-use code, no configurability nobody asked for. If 200 lines could be 50,
  rewrite it.
- **Surgical changes.** Touch only what the request needs. Don't refactor or reformat adjacent code;
  match the existing style. Remove only the orphans your own change created — flag pre-existing dead
  code, don't delete it.
- **Goal-driven.** Turn the task into a verifiable check and loop until it passes (e.g. "fix the
  bug" → write a failing test that reproduces it, then make it pass).

<!-- SHARED-CLAUDE-END -->
