# Workflow — adding a new module

Template: [template-non-ddd-structure.md](../templates/template-non-ddd-structure.md).

1. Check whether the feature is a new **job type** of the existing `jobs` module — if so use [workflow-adding-a-new-job-type.md](workflow-adding-a-new-job-type.md) instead.
2. Create `app/modules/<module>/` from the template: `models.py`, `repository.py`, `service.py`, `schemas.py`, `router.py`, `errors.py`, `http_errors.py`.
3. Wire it in `container.py` (add a field to `Container`) and `main.py` (`include_router`, `register_<module>_error_handlers`).
4. Add the table with [workflow-database-migrations.md](workflow-database-migrations.md); import the models in `alembic/env.py`.
5. Tests for service (mocked repository) and router (`TestClient`).
