# frontend docs

## Documentation Structure

| Doc | Covers |
| --- | --- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Routes, rendering, data layer, polling, captcha, env |
| [structure.md](structure.md) | Atomic-design folder map and placement rules |
| [state-management.md](state-management.md) | TanStack Query vs Redux vs local state |
| [styling.md](styling.md) | Tailwind v4 tokens, dark mode, Markdown preview styles |
| [components.md](components.md) | Props typing, one component per file, existing atoms/molecules |
| [coding-conventions.md](coding-conventions.md) | TypeScript / React delta from root conventions |
| [coding-style.md](coding-style.md) | ESLint setup |
| [testing-strategy.md](testing-strategy.md) | What validates a frontend change today |
| [decisions.md](decisions.md) | frontend ADRs |
| [workflows/README.md](workflows/README.md) | Workflow registry |
| [templates/README.md](templates/README.md) | Template registry |

## Required Reading Order

1. [../../docs/project-overview.md](../../docs/project-overview.md)
2. [../AGENTS.md](../AGENTS.md)
3. [ARCHITECTURE.md](ARCHITECTURE.md) + [structure.md](structure.md) + [state-management.md](state-management.md)
4. The workflow for the task + [coding-conventions.md](coding-conventions.md) + similar existing components

## Workflow Process

| Phase | Read |
| --- | --- |
| Analyze | project-overview, AGENTS.md task matrix |
| Research | ARCHITECTURE, structure, state-management |
| Plan | decisions, workflows → templates |
| Implement | coding-conventions, coding-style, structure, styling / components |
| Validate | testing-strategy |
