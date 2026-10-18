# Workflow — adding a package

1. Reserve the next digit in the port block (4022 / 5072 for an admin app) and record it in the port-allocator inventory.
2. Create the folder at the workspace root with its own `CLAUDE.md` (`@AGENTS.md`), `AGENTS.md` and `docs/` hub (conventions / style / structure = only the delta from root).
3. Add it to `run.sh` (`cmd_start`, `cmd_start_test`, `cmd_clear_log`), to the root `.gitignore` if it produces runtime data, and give it the env matrix (`.env.example` + ignored `.env*`).
4. Update [../../AGENTS.md](../../AGENTS.md) inventory, [../dependency-graph.md](../dependency-graph.md), [../structure.md](../structure.md), [../technology.md](../technology.md).
5. A shared types package (`shared/`) is added only when both apps import it — record the reason in [../decisions.md](../decisions.md).
