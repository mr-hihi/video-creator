# Workspace tooling

`run.sh` at the workspace root is the only orchestrator — there is no nx / turbo / npm workspace.

## Commands

| Command | Does |
| --- | --- |
| `sh run.sh start` | api (`APP_ENV=local`, uvicorn `--reload` on `app/`) on 4020 + frontend on 4021 |
| `sh run.sh start_test` | api (`APP_ENV=test`, no reload) on 5070 + frontend on 5071 pointed at it; refuses if a port is busy |
| `sh run.sh migrate` | `alembic upgrade head` on the dev DB |
| `sh run.sh migrate dev <name>` | autogenerate revision `NNNN_<name>.py` (highest id + 1) from model changes — does not apply it |
| `sh run.sh migrate test` / `status` | upgrade the test DB / show the current revision |
| `sh run.sh test [pytest args]` | API unit tests |
| `sh run.sh setup_whisper` | checks `whisper-cli`, downloads `ggml-large-v3-turbo.bin` into `api/models/` |
| `sh run.sh clear_log` | deletes `api/logs/*.log` and `.next` logs |
| `sh run.sh deploy` / `deploy_prod` | placeholders — fill the variables first |

## Ports

| Role | Dev | Test | Reserved |
| --- | --- | --- | --- |
| API | 4020 | 5070 | block 4020–4029 / 5070–5079 |
| Frontend | 4021 | 5071 | |
| Google Flow extension socket (inside the API process, `FLOW_WS_PORT`) | 4024 | 5074 | set the same port in the extension popup (`Agent port`) |

## Env files

| App | Selected by | Files |
| --- | --- | --- |
| api | `APP_ENV` (`local`, `test`, `stg`, `prod`) | `.env` (defaults) then `.env.<APP_ENV>` overrides |
| frontend | Next.js | `next dev` reads `.env` + `.env.local`; `.env.test` is read only when `NODE_ENV=test` (unused today — `start_test` passes `NEXT_PUBLIC_API_URL` inline); `.env.stg` / `.env.prod` must be copied in before `next build` |

- **Critical** — only `.env.example` is committed. Add every new key to `.env.example` in the same change.
- Local/test env files set `CAPTCHA_ENABLED=false` / `NEXT_PUBLIC_CAPTCHA_ENABLED=false`; the always-pass Turnstile test keys stay for turning it back on. stg/prod keys stay blank in git.
