<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# AGENTS.md — frontend

> **Read documentation first.** Start at [docs/README.md](docs/README.md). Workspace-wide rules live in
> [../AGENTS.md](../AGENTS.md) and [../docs/](../docs/README.md); this hub holds only the frontend delta.

## Project Overview

Next.js 16 App Router UI (Node 24, npm) for video-tool, with the menus Video to Markdown (upload or
YouTube link, follow the job, preview the Markdown, download the `.zip`), Film Analysis (character and scene
prompts with copy, rerun, delete), Film Clone (assets, shots, localization, script and scene images),
Film Studio (projects with a story bible, character / style / voice library, episodes outlined in parts of scenes, clips, narration and the assembled film),
and Settings (script language and provider connections, AI models with the media routes and models, prompt
presets — edit, version, import / export — and the Film Clone and Film Studio media providers).
Desktop-first, responsive down to phone width. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Documentation links

| Topic | Doc |
| --- | --- |
| Index | [docs/README.md](docs/README.md) |
| Architecture (routes, data layer, rendering) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Atomic-design layout | [docs/structure.md](docs/structure.md) |
| State ownership | [docs/state-management.md](docs/state-management.md) |
| Styling (Tailwind v4 tokens) | [docs/styling.md](docs/styling.md) |
| Components | [docs/components.md](docs/components.md) |
| Conventions (TS delta) / style (ESLint) | [docs/coding-conventions.md](docs/coding-conventions.md) · [docs/coding-style.md](docs/coding-style.md) |
| Testing | [docs/testing-strategy.md](docs/testing-strategy.md) |
| Decisions | [docs/decisions.md](docs/decisions.md) |
| Workflows / templates | [docs/workflows/README.md](docs/workflows/README.md) · [docs/templates/README.md](docs/templates/README.md) |
| API contract | [../docs/dependency-graph.md](../docs/dependency-graph.md) |

## AI Agent Guidelines

### Do

- Read the bundled Next.js 16 guide in `node_modules/next/dist/docs/` before using an App Router API you have not used here.
- Place UI at the right atomic level and never import upward (an atom never imports a molecule; a molecule never an organism).
- Route every server call through a hook in `src/features/<feature>/queries.ts` → `src/lib/api/client.ts`.
- Keep the captcha provider switch inside `src/lib/captcha/`.

### Don't

- Call `fetch` / `XMLHttpRequest` in a component.
- Put server data in Redux.
- Put a secret in a `NEXT_PUBLIC_*` variable — every one ships in the browser bundle.
- Render API-provided HTML; Markdown goes through `react-markdown` (no `rehype-raw`).
- Write a comment in JSX, or leave `console.log`.
- Show a spinner on a button; disable the button instead.

### When to read what

| Task | Read first | Then | Scaffold template |
| --- | --- | --- | --- |
| New component | [structure.md](docs/structure.md) | [workflow-adding-a-component.md](docs/workflows/workflow-adding-a-component.md) | [template-component.md](docs/templates/template-component.md) |
| New page / route | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [workflow-adding-a-page.md](docs/workflows/workflow-adding-a-page.md) | [template-page.md](docs/templates/template-page.md) |
| API integration | [state-management.md](docs/state-management.md) | [workflow-implementing-api-calls.md](docs/workflows/workflow-implementing-api-calls.md) | [template-api-client.md](docs/templates/template-api-client.md) |
| UI state | [state-management.md](docs/state-management.md) | [workflow-adding-redux-state.md](docs/workflows/workflow-adding-redux-state.md) | [template-redux-state.md](docs/templates/template-redux-state.md) |
| Styling change | [styling.md](docs/styling.md) | [components.md](docs/components.md) | — |
| Bug / blank page | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [workflow-debugging.md](docs/workflows/workflow-debugging.md) | — |
| Tests | [testing-strategy.md](docs/testing-strategy.md) | [../docs/workflows/workflow-running-tests.md](../docs/workflows/workflow-running-tests.md) | — |

### Reading by phase

| Phase | Do | Read |
| --- | --- | --- |
| Analyze | Pick the task row above | [../docs/project-overview.md](../docs/project-overview.md) |
| Research | Understand routes, data layer, similar components | [ARCHITECTURE.md](docs/ARCHITECTURE.md), [structure.md](docs/structure.md), [state-management.md](docs/state-management.md) |
| Plan | Choose the state owner; workflow first, then template; `REQUIRED READING (frontend)` per step | [decisions.md](docs/decisions.md), [workflows/README.md](docs/workflows/README.md) |
| Implement | Code in the package style | [coding-conventions.md](docs/coding-conventions.md), [coding-style.md](docs/coding-style.md), [structure.md](docs/structure.md), [styling.md](docs/styling.md) / [components.md](docs/components.md) |
| Validate | `npm run lint && npm run build` | [testing-strategy.md](docs/testing-strategy.md) |

### Dispatching subagents (MANDATORY)

Every brief opens with `REQUIRED READING (frontend): <files for the phase>`, e.g.
`REQUIRED READING (frontend): frontend/docs/structure.md, frontend/docs/coding-conventions.md, frontend/docs/coding-style.md, frontend/docs/state-management.md`.
A subagent loads no `AGENTS.md`; the `PreToolUse(Task)` hook blocks a brief without the line, and the
edit hook blocks `.ts/.tsx` edits until this package's conventions, style and structure docs are read.

## Important Notes

- **Critical** — `NEXT_PUBLIC_*` values are inlined at build time; `.env.stg` / `.env.prod` must be copied to `.env.production.local` (or exported) before `next build`.
- **Critical** — the block at the top of this file is regenerated by `next dev`; keep it.
- `.next/` is build cache — delete it when a build behaves strangely; never commit it.
- `package.json` `dev` has no port; `run.sh` passes `--port 4021` / `5071`.
