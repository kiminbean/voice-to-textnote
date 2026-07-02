#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
mkdir -p logs

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export PYTHONUNBUFFERED=1

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

export MODEL_PRELOAD_ENABLED="${MODEL_PRELOAD_ENABLED:-false}"
export STT_BACKEND="${STT_BACKEND:-faster_whisper}"

BACKEND_API_HOST="${BACKEND_API_HOST:-0.0.0.0}"
BACKEND_API_PORT="${BACKEND_API_PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

exec "$PYTHON_BIN" -m uvicorn backend.app.main:app \
  --host "$BACKEND_API_HOST" \
  --port "$BACKEND_API_PORT" \
  --loop asyncio \
  --http h11
