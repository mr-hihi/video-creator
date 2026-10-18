# api docs

## Documentation Structure

| Doc | Covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, request flow, batch worker, `video_to_markdown` pipeline |
| [structure.md](structure.md) | Folder map, where each role lives |
| [coding-conventions.md](coding-conventions.md) | Python-specific delta from root conventions |
| [coding-style.md](coding-style.md) | ruff rules |
| [testing-strategy.md](testing-strategy.md) | pytest fixture style, mocks, coverage |
| [decisions.md](decisions.md) | api ADRs |
| [workflows/README.md](workflows/README.md) | Workflow registry |
| [templates/README.md](templates/README.md) | Template registry |

## Required Reading Order

1. [../../docs/project-overview.md](../../docs/project-overview.md)
2. [../AGENTS.md](../AGENTS.md)
3. [ARCHITECTURE.md](ARCHITECTURE.md) + [structure.md](structure.md)
4. The workflow for the task + [coding-conventions.md](coding-conventions.md) + similar existing code

## Workflow Process

| Phase | Read |
| --- | --- |
| Analyze | project-overview, AGENTS.md task matrix |
| Research | ARCHITECTURE, structure |
| Plan | decisions, workflows → templates |
| Implement | coding-conventions, coding-style, structure (+ root) |
| Validate | testing-strategy |
