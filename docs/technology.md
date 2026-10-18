# Technology

## Runtimes

| Runtime | Version | Pinned in |
| --- | --- | --- |
| Node | 24.6.0 | `.node-version` (nodenv) |
| Python | 3.13 | `api/.python-version` (uv) |
| MySQL | 5.7 (local, port 3306) | `DATABASE_URL` |

## api

| Concern | Choice |
| --- | --- |
| Package manager | `uv` (`uv.lock`) — never `pip install` |
| Web | FastAPI + uvicorn |
| DB | SQLAlchemy 2 (sync) + PyMySQL, Alembic migrations |
| Config | pydantic-settings |
| Speech-to-text | whisper.cpp `whisper-cli` (Homebrew `whisper-cpp`), model `ggml-large-v3-turbo.bin` |
| Media | ffmpeg / ffprobe (Homebrew) |
| AI model (Settings `aiModel` / `aiStepModels`) | Claude Code CLI `claude -p --json-schema` (user's login, no API key), the Gemini API `streamGenerateContent` or the OpenAI Responses API, both streamed over httpx with the provider's key; images re-encoded with Pillow |
| HTTP out | httpx (captcha verify, media providers, Gemini, OpenAI) |
| Test / lint | pytest + pytest-cov, ruff |

## frontend

| Concern | Choice |
| --- | --- |
| Package manager | npm (`package-lock.json`) |
| Framework | Next.js 16 App Router, React 19, TypeScript |
| Styling | Tailwind CSS v4 (`@theme` tokens in `globals.css`) |
| Server state | TanStack Query |
| Client state | Redux Toolkit |
| Markdown | react-markdown + remark-gfm |
| Lint | ESLint (next core-web-vitals + typescript + TanStack Query) |
