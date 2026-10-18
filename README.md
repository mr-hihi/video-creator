# video-tool

Local tool for video operations, run as background jobs. First operation: **video → Markdown** — the
transcript of the speech plus a screenshot at each key moment, where Claude picks the moments from
the transcript. The video is an uploaded file or a YouTube link (transcript from the YouTube captions).

| App | Stack | Dev URL | Test URL |
| --- | --- | --- | --- |
| `api/` | Python 3.13 · FastAPI · SQLAlchemy/Alembic · MySQL | http://localhost:4020 | http://localhost:5070 |
| `frontend/` | Next.js 16 · React 19 · Tailwind v4 · TanStack Query · Redux Toolkit | http://localhost:4021 | http://localhost:5071 |

## Requirements

- macOS with Homebrew: `ffmpeg`, `whisper-cpp` (`brew install ffmpeg whisper-cpp`)
- `uv`, Node 24 (see `.node-version`), MySQL 5.7+
- Claude Code CLI (`claude`) logged in — used to pick key moments
- YouTube links: `yt-dlp` comes with `uv sync` (api dependency) and needs `node` on `PATH`. YouTube changes
  often; when downloads start failing run `(cd api && uv lock --upgrade-package yt-dlp && uv sync)`

## Setup

```bash
(cd api && uv sync)
(cd frontend && npm install)
sh run.sh setup_whisper                    # downloads the whisper model into api/models/
mysql -e "CREATE DATABASE video_tool CHARACTER SET utf8mb4; CREATE DATABASE video_tool_test CHARACTER SET utf8mb4;"
# put the real DATABASE_URL in api/.env.local and api/.env.test
sh run.sh migrate
sh run.sh migrate test
```

## Run

```bash
sh run.sh start        # dev: api + frontend (batch worker starts with the api)
sh run.sh start_test   # fenced test stack on 5070/5071 with the test DB
sh run.sh test         # api unit tests
```

## Output of a video → Markdown job

```
<video-name>.md
images/moment-01-00m00s.jpg
images/moment-02-01m23s.jpg
...
```

Download it as a zip from the job page, or find it under `api/storage/<job-id>/output/`.

## Docs

Start at [AGENTS.md](AGENTS.md) and [docs/README.md](docs/README.md).
