# video-tool docs (workspace)

Workspace-wide docs only. Package-specific docs live in `api/docs/` and `frontend/docs/`.

## Documentation Structure

| Doc | Covers |
| --- | --- |
| [project-overview.md](project-overview.md) | What the tool does, job model, packages at a glance |
| [business.md](business.md) · [test-cases.md](test-cases.md) | Business specs per domain + their test cases |
| [dependency-graph.md](dependency-graph.md) | frontend → api edge, the HTTP contract, external tools |
| [workspace-tooling.md](workspace-tooling.md) | `run.sh` commands, ports, env files |
| [technology.md](technology.md) | Stack per package, runtime versions |
| [structure.md](structure.md) | Workspace layout, where things live, boundaries |
| [coding-conventions.md](coding-conventions.md) | Shared conventions (naming, comments, errors, git) |
| [coding-style.md](coding-style.md) | Shared lint / format rules |
| [testing-strategy.md](testing-strategy.md) | Unit vs E2E split, fenced test stack |
| [decisions.md](decisions.md) | Workspace-level ADRs |
| [design/](design/video-to-markdown.md) | Feature design notes: [video-to-markdown](design/video-to-markdown.md) |
| [workflows/README.md](workflows/README.md) | Workflow registry |

## Required Reading Order

1. [project-overview.md](project-overview.md)
2. [../AGENTS.md](../AGENTS.md) — inventory + AI Agent Guidelines
3. [dependency-graph.md](dependency-graph.md) + [structure.md](structure.md) + [workspace-tooling.md](workspace-tooling.md)
4. The target package's `docs/README.md`, its workflows and its conventions

## Workflow Process

| Phase | Goal | Read |
| --- | --- | --- |
| Analyze | Frame the task, pick the package | project-overview, inventory, dependency-graph |
| Research | Understand the package and blast radius | package `ARCHITECTURE.md` + `structure.md`, workspace-tooling |
| Plan | Choose workflow(s) then template(s); `REQUIRED READING` per step | root + package `decisions.md`, package `workflows/README.md` |
| Implement | Write code | package `coding-conventions.md` + `coding-style.md` + `structure.md` |
| Validate | Tests + lint; check the other side of a contract change | [testing-strategy.md](testing-strategy.md) |
