#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() {
  printf "\n==> %s\n" "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "Missing required command: %s\n" "$1" >&2
    exit 1
  fi
}

require_command docker
require_command curl

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

require_command python
require_command uvicorn

if ! python - <<'PY'
import subprocess

try:
    subprocess.run(
        ["docker", "info"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=15,
    )
except (subprocess.SubprocessError, OSError):
    raise SystemExit(1)
PY
then
  printf "Docker is not ready. Open Docker Desktop and wait until docker info succeeds.\n" >&2
  exit 1
fi

export REQUEST_LOGGING_ENABLED="${REQUEST_LOGGING_ENABLED:-true}"
export AUTO_CREATE_DB_TABLES="${AUTO_CREATE_DB_TABLES:-true}"
export CACHE_BACKEND="${CACHE_BACKEND:-memory}"
export MODEL_CALL_TIMEOUT_SECONDS="${MODEL_CALL_TIMEOUT_SECONDS:-60}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export OLLAMA_HTTP_TIMEOUT_SECONDS="${OLLAMA_HTTP_TIMEOUT_SECONDS:-60}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:-30m}"
export OLLAMA_CONTEXT_LENGTH="${OLLAMA_CONTEXT_LENGTH:-2048}"
export SMALL_MODEL="${SMALL_MODEL:-ollama/llama3.2}"
export PORT="${PORT:-8080}"

log "Starting Postgres"
docker compose up -d postgres

if [[ "$CACHE_BACKEND" == "redis" ]]; then
  log "Starting Redis"
  docker compose up -d redis
fi

log "Waiting for Postgres"
postgres_ready=false
for _ in {1..30}; do
  if docker compose exec -T postgres pg_isready -U routewise -d routewise >/dev/null 2>&1; then
    postgres_ready=true
    break
  fi
  sleep 1
done

if [[ "$postgres_ready" != "true" ]]; then
  printf "Postgres did not become ready. Check Docker Desktop and run: docker compose ps\n" >&2
  exit 1
fi

log "Creating database tables"
python -c "import asyncio; from app.db.session import init_db; asyncio.run(init_db())"

log "Checking Ollama at ${OLLAMA_BASE_URL}"
if ! curl --fail --silent --show-error --max-time 10 "${OLLAMA_BASE_URL%/}/api/tags" >/dev/null; then
  printf "Ollama is not reachable at %s.\n" "$OLLAMA_BASE_URL" >&2
  printf "Open the Ollama app or run: ollama serve\n" >&2
  exit 1
fi

if [[ "$SMALL_MODEL" == ollama/* ]]; then
  ollama_model="${SMALL_MODEL#ollama/}"
  log "Warming Ollama model ${ollama_model}"
  if ! curl --fail --silent --show-error --max-time "$OLLAMA_HTTP_TIMEOUT_SECONDS" \
    "${OLLAMA_BASE_URL%/}/api/chat" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${ollama_model}\",\"messages\":[{\"role\":\"user\",\"content\":\"Hi\"}],\"stream\":false,\"keep_alive\":\"${OLLAMA_KEEP_ALIVE}\",\"options\":{\"num_predict\":1,\"num_ctx\":${OLLAMA_CONTEXT_LENGTH}}}" \
    >/dev/null; then
    printf "Could not warm Ollama model %s.\n" "$ollama_model" >&2
    printf "If the model is missing, run: ollama pull %s\n" "$ollama_model" >&2
    exit 1
  fi
fi

log "Starting RouteWise API on http://localhost:${PORT}"
exec uvicorn app.main:app --port "$PORT" --ws none --loop asyncio
