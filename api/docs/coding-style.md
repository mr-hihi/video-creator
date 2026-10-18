# api coding style (delta)

| Tool | Config | Command |
| --- | --- | --- |
| ruff lint | `pyproject.toml [tool.ruff]` — `E F I B UP SIM`, line 100, py312, `alembic/versions` excluded | `uv run ruff check .` |
| ruff format | same file | `uv run ruff format .` (check: `--check`) |

- **Critical** — run `uv run ruff format .` then `uv run ruff check .` before finishing; both must be clean.
- **Preferred** — imports are sorted by ruff (`I`); first-party is `app`.
- Keep `# noqa` only for side-effect imports (`alembic/env.py` model import).
