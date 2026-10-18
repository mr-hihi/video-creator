#!/bin/bash
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_PORT=4020
FRONTEND_PORT=4021
# Isolated local test stack (E2E): 5xxx mirror, fenced-off test DB. Never reuses dev DB/ports.
TEST_API_PORT=5070
TEST_FRONTEND_PORT=5071

WHISPER_MODEL_NAME="ggml-large-v3-turbo.bin"
WHISPER_MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$WHISPER_MODEL_NAME"

stop_tree() {
  for child in $(pgrep -P "$1"); do stop_tree "$child"; done
  kill "$1" 2>/dev/null
}

cmd_start() {
  trap 'stop_tree $API_PID; stop_tree $FE_PID; exit 0' SIGINT SIGTERM
  cd "$ROOT_DIR/api" && APP_ENV=local uv run uvicorn app.main:app --reload --reload-dir app --port $API_PORT &
  API_PID=$!
  cd "$ROOT_DIR/frontend" && npm run dev -- --port $FRONTEND_PORT &
  FE_PID=$!
  echo "API:      http://localhost:$API_PORT"
  echo "Frontend: http://localhost:$FRONTEND_PORT"
  wait
}

cmd_start_test() {
  # API runs with APP_ENV=test / .env.test (fenced test DB). Frontend points at the test API.
  trap 'stop_tree $API_PID; stop_tree $FE_PID; exit 0' SIGINT SIGTERM
  for p in "$TEST_API_PORT" "$TEST_FRONTEND_PORT"; do
    if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Error: port $p already in use — stop that process first."; exit 1
    fi
  done
  cd "$ROOT_DIR/api" && APP_ENV=test uv run uvicorn app.main:app --port $TEST_API_PORT &
  API_PID=$!
  cd "$ROOT_DIR/frontend" && NEXT_PUBLIC_API_URL="http://localhost:$TEST_API_PORT" \
    npm run dev -- --port $TEST_FRONTEND_PORT &
  FE_PID=$!
  echo "TEST API:      http://localhost:$TEST_API_PORT (fenced test DB)"
  echo "TEST Frontend: http://localhost:$TEST_FRONTEND_PORT"
  wait
}

# Applies pending migrations. Dev by default; `sh run.sh migrate test` targets the
# fenced test database instead. `migrate dev <name>` only *creates* a migration from a
# model edit (review it, then apply) — the others only apply what is already committed.
cmd_migrate() {
  set -e
  cd "$ROOT_DIR/api"
  case "${1}" in
    ""|deploy)  APP_ENV=local uv run alembic upgrade head ;;
    dev)        LAST_REV_ID=$(ls alembic/versions | grep -oE '^[0-9]{4}' | sort -n | tail -1)
                NEXT_REV_ID=$(printf "%04d" $(( 10#${LAST_REV_ID:-0} + 1 )))
                APP_ENV=local uv run alembic revision --autogenerate --rev-id "$NEXT_REV_ID" -m "${2:-change}"
                echo "Review alembic/versions/${NEXT_REV_ID}_*.py, then run: sh run.sh migrate" ;;
    test)       APP_ENV=test uv run alembic upgrade head ;;
    status)     APP_ENV=local uv run alembic current ;;
    *) echo "Usage: sh run.sh migrate {deploy|dev [name]|test|status}"; exit 1 ;;
  esac
}

cmd_test() {
  cd "$ROOT_DIR/api" && uv run pytest "$@"
}

cmd_setup_whisper() {
  set -e
  command -v whisper-cli >/dev/null 2>&1 || { echo "whisper-cli missing — run: brew install whisper-cpp"; exit 1; }
  mkdir -p "$ROOT_DIR/api/models"
  if [ -f "$ROOT_DIR/api/models/$WHISPER_MODEL_NAME" ]; then
    echo "Model already present: api/models/$WHISPER_MODEL_NAME"; return
  fi
  curl -L --fail -o "$ROOT_DIR/api/models/$WHISPER_MODEL_NAME.part" "$WHISPER_MODEL_URL"
  mv "$ROOT_DIR/api/models/$WHISPER_MODEL_NAME.part" "$ROOT_DIR/api/models/$WHISPER_MODEL_NAME"
  echo "Model saved: api/models/$WHISPER_MODEL_NAME"
}

cmd_youtube() {
  set -e
  URL="$1"; HEIGHT="${2:-720}"; AUDIO_KBPS="${3:-128}"
  if [ -z "$URL" ]; then echo "Usage: sh run.sh youtube <url> [height=720] [audio_kbps=128]"; exit 1; fi
  command -v ffmpeg >/dev/null 2>&1 || { echo "ffmpeg missing — run: brew install ffmpeg"; exit 1; }
  mkdir -p "$ROOT_DIR/downloads"
  # yt-dlp enables only deno by default; YouTube's player challenge fails without a JS runtime.
  uvx --from 'yt-dlp[default]@latest' yt-dlp \
    --js-runtimes node \
    --no-playlist \
    -f "bv*+ba/b" \
    -S "res:$HEIGHT,vcodec:h264,acodec:m4a,abr~$AUDIO_KBPS" \
    --merge-output-format mp4 \
    -o "$ROOT_DIR/downloads/%(title)s [%(id)s].%(ext)s" \
    "$URL"
}

cmd_clear_log() {
  echo "Clearing logs..."
  [ -d "$ROOT_DIR/api/logs" ] && find "$ROOT_DIR/api/logs" -type f -name "*.log" -delete
  [ -d "$ROOT_DIR/frontend/.next" ] && find "$ROOT_DIR/frontend/.next" -type f -name "*.log" -delete 2>/dev/null
  echo "All logs cleared."
}

# --- Deploy: FILL THESE IN. No credentials are committed. ---
cmd_deploy_stg() {
  set -e
  STG_HOST=""; STG_PORT="22"; STG_USER=""
  STG_API_DIR=""; STG_FE_DIR=""
  if [ -z "$STG_HOST" ]; then echo "Fill deploy vars in run.sh first."; exit 1; fi
  echo "=== [1/4] Build frontend ==="; cd "$ROOT_DIR/frontend" && npm run build
  echo "=== [2/4] Lock api deps ===";   cd "$ROOT_DIR/api" && uv sync --frozen
  echo "=== [3/4] Upload (rsync/scp) ==="   # TODO: rsync frontend build + api source to remote paths
  echo "=== [4/4] Migrate + restart ==="    # TODO: run cmd_migrate on the remote; restart service
}

cmd_deploy_prod() {
  echo "Copy cmd_deploy_stg, use PROD_* vars, then remove this line."; exit 1
}

case "${1}" in
  start)         cmd_start ;;
  start_test)    cmd_start_test ;;
  migrate)       shift; cmd_migrate "$@" ;;
  test)          shift; cmd_test "$@" ;;
  setup_whisper) cmd_setup_whisper ;;
  youtube)       shift; cmd_youtube "$@" ;;
  clear_log)     cmd_clear_log ;;
  deploy)        cmd_deploy_stg ;;
  deploy_prod)   cmd_deploy_prod ;;
  *) echo "Usage: sh run.sh {start|start_test|migrate|test|setup_whisper|youtube|clear_log|deploy|deploy_prod}"; exit 1 ;;
esac
