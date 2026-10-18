# Coding style (shared)

- **Critical** — lint (and format, where configured) must be clean before a change is done. Fix the code; don't disable a rule inline.
- **Preferred** — a rule override, when truly needed, goes in the tool's config file scoped to one path.
- There is no pre-commit hook yet. Run each package's commands yourself.

Package deltas: [api](../api/docs/coding-style.md) · [frontend](../frontend/docs/coding-style.md).
