# api testing strategy

`pytest` + `unittest.mock`, config in `pyproject.toml [tool.pytest.ini_options]`.

## Rules

- **Critical** — no DB (a unit test that opens a DB connection is a defect), no network, no real ffmpeg/whisper/claude. Mock the seam the production caller uses: `JobRepository`, `CommandRunner`, `httpx.Client`, `subprocess.Popen` (only in `test_process.py`, which also runs a real `sys.executable -c` child for
  `run_watched`: watching output needs real pipes and timing).
- **Critical** — a test body holds **assertions only**. Arrange + act live in fixtures named after what they produce.
  - ✅ fixture `missing_job_error` runs `service.get_job("missing")` under `pytest.raises` and returns the error; the test asserts on it.
  - ❌ calling the service, looping or unpacking tuples inside `def test_…`.
- **Critical** — every branch of new logic is covered: `sh run.sh test --cov=app --cov-branch --cov-report=term-missing`.
- **Preferred** — parametrized cases use `@pytest.fixture(params=…)` returning an `Outcome(actual, expected)`.
- **Preferred** — filesystem work uses `tmp_path` with a real `JobStorage`; that is not a DB and is allowed.
- HTTP layer: `TestClient(create_app())` **without** `with`, so lifespan does not run; set `app.state.container` to a `SimpleNamespace` of mocks.
- `repository.py` has no unit tests on purpose (SQL only). It has no automated test at all yet — verify claim / requeue by hand on `sh run.sh start_test`.

## Layout

One flat `tests/test_<unit>.py` per unit; `conftest.py` only sets env vars (`DATABASE_URL=sqlite://`, `LOG_DRIVER=stdout`, `BATCH_ENABLED=false`).
