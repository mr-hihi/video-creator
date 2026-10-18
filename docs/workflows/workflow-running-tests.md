# Workflow — running tests

| Package | Command | Must be |
| --- | --- | --- |
| api | `sh run.sh test` | all green |
| api (coverage) | `sh run.sh test --cov=app --cov-branch --cov-report=term-missing` | new logic fully branch-covered |
| api (lint) | `cd api && uv run ruff check . && uv run ruff format --check .` | clean |
| frontend | `cd frontend && npm run lint && npm run build` | clean build |

- Run the package you changed, and the other package too when the HTTP contract moved.
- Unit tests never need MySQL, ffmpeg, whisper or claude — if one does, it is not a unit test.
