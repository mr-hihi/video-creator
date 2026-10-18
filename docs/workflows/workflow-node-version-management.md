# Workflow — runtime versions

| Runtime | Pin | Manager | Check |
| --- | --- | --- | --- |
| Node | `.node-version` (24.6.0) | nodenv | `node -v` inside `frontend/` |
| Python | `api/.python-version` (3.13) | uv | `cd api && uv run python -V` |

- Next.js 16 needs Node ≥ 20.9. If a `next` command fails with a syntax or engine error, check `node -v` against `.node-version` first.
- Bump a runtime by editing the pin file, reinstalling (`npm install` / `uv sync`), then running [workflow-running-tests.md](workflow-running-tests.md).
- **Critical** — never `pip install` into the system Python; use `uv add` / `uv sync`.
