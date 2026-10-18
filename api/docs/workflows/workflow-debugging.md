# Workflow — debugging a job

| Symptom | Look at | Likely cause |
| --- | --- | --- |
| Job stays `pending` | API log line `Batch worker started` | `BATCH_ENABLED=false`, or the API is not running |
| `failed`: `whisper-cli is not installed…` | `which whisper-cli` | `brew install whisper-cpp` missing, or `WHISPER_BIN` wrong |
| `failed`: `Whisper model not found…` | `api/models/` | run `sh run.sh setup_whisper` |
| `failed`: `claude failed…` / `no structured output` | `claude -p "hi"` in a terminal; Settings → General → Providers → Claude CLI → `Test connection` | CLI logged out, rate limit, or the CLI rejects the model picked in Settings → AI models |
| `failed`: `gemini failed…` / `openai failed…` / `… returned no answer: …` | the job's `AI` row (`aiUsed`) and the provider card's `Test connection` | wrong or expired key, rate limit, model not available to the key, safety block |
| `failed`: `{provider} is not set up — open Settings` | Settings → General → Providers | the step's model belongs to a provider without a key |
| `failed`: `No speech was detected` | the video's audio track | silent video or wrong `language` |
| `failed`: `… timed out after Ns` | `*_TIMEOUT_SEC` in `.env` | long video — raise the timeout |
| Job restarted from scratch | API log `Requeued N job(s)` | API reloaded / restarted mid-job (expected) |

- Logs: `api/logs/app-YYYY-MM-DD.log` (`LOG_DRIVER=file`), one line per job start / done / failure with the job id.
- Working files stay under `api/storage/<job_id>/work/` (`audio.wav`, `transcript.json`) for inspection.
- Re-run a failed job: upload again (there is no retry endpoint).
