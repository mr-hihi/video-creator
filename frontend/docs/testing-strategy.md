# frontend testing strategy

No unit or component test runner is installed yet.

| Check | Command | Catches |
| --- | --- | --- |
| Lint | `npm run lint` | hook rules, query-key rules, Next rules |
| Type + build | `npm run build` | type errors, route / server-client boundary errors |
| Manual / E2E | `sh run.sh start_test` (user runs it), then drive http://localhost:5071 | real upload → job → preview flow against the fenced API |

- **Critical** — both commands pass before a frontend change is done.
- **Preferred** — keep logic in pure functions under `features/*/utils.ts` and `lib/` so a future Vitest/RTL setup can test it without rendering.
- Adding a test runner is a decision: record it in [decisions.md](decisions.md) and update this file.
