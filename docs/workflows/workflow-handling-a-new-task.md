# Workflow — handling a new task

1. **Analyze** — read [project-overview.md](../project-overview.md); decide which package(s) the task touches via the inventory in [AGENTS.md](../../AGENTS.md).
2. **Research** — read the package's `docs/ARCHITECTURE.md` + `docs/structure.md`; for a contract change read [dependency-graph.md](../dependency-graph.md).
3. **Plan** — read [decisions.md](../decisions.md) and the package's `docs/decisions.md`; pick the workflow from the package's `workflows/README.md`, then its template. Write steps, each opening with `REQUIRED READING (<package>): …`.
4. **Implement** — read the package's `coding-conventions.md`, `coding-style.md`, `structure.md`. The edit hook enforces this only for `.ts/.tsx/.js/.jsx` (frontend); `api/**/*.py` edits are not gated, so the rule is on you there.
5. **Validate** — [workflow-running-tests.md](workflow-running-tests.md); for a contract change validate both packages.
6. Report what changed and what was verified. Commit only when asked.
