# Workflow — running the workspace

**Critical** — an agent never starts the dev stack; ask the user to run it in a separate terminal, then verify with `curl`.
An agent may start the test stack in the background for E2E checks, reusing one already up, and stops it once the run
is recorded.

## First-time setup

```bash
brew install whisper-cpp                 # provides whisper-cli
sh run.sh setup_whisper                  # downloads api/models/ggml-large-v3-turbo.bin (~1.6 GB)
claude --version                         # the CLI must be logged in for moment picking
(cd api && uv sync)
(cd frontend && npm install)
mysql -e "CREATE DATABASE video_tool CHARACTER SET utf8mb4; CREATE DATABASE video_tool_test CHARACTER SET utf8mb4;"
# set DATABASE_URL in api/.env.local and api/.env.test
sh run.sh migrate && sh run.sh migrate test
```

## Daily

| Goal | Command | Verify |
| --- | --- | --- |
| Dev stack | `sh run.sh start` | `curl -s localhost:4020/jobs` → `[...]`, open http://localhost:4021 |
| Test stack | `sh run.sh start_test` | `curl -s localhost:5070/jobs` |

- The batch worker starts with the API (`BATCH_ENABLED=true`) and stops with it. Jobs left `processing` go back to `pending` on the next start.
- With `--reload`, saving a file under `api/app/` restarts the API and re-runs any in-flight job from the start.
