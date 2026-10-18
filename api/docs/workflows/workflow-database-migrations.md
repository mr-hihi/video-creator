# Workflow — database migrations (Alembic)

Template: [template-database-migration.md](../templates/template-database-migration.md).

1. Edit the model in `models.py`.
2. Ask the user to run `sh run.sh migrate dev <slug>`: it only autogenerates `alembic/versions/NNNN_<slug>.py` (highest existing id + 1; `alembic.ini` `file_template = %%(rev)s_%%(slug)s`). Or write the revision by hand from the template.
3. Review and edit the generated ops **before applying**: `DATETIME(6)` variant for time columns, `utf8mb4` for new tables, a `downgrade()` that reverses everything.
4. Render the SQL without a DB to check it: `APP_ENV=local uv run alembic upgrade head --sql`.
5. Apply: `sh run.sh migrate` (dev) and `sh run.sh migrate test`.

- **Critical** — never edit a migration that has been applied beyond your local dev DB; add a new one. Applied only locally → `APP_ENV=local uv run alembic downgrade -1`, edit, re-apply.
- **Critical** — `sqlalchemy.url` is not in `alembic.ini`; `alembic/env.py` reads `DATABASE_URL` from `Settings`.
