#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-true}"
AUTO_INDEX_RAG="${AUTO_INDEX_RAG:-false}"
MILVUS_DB_DEFAULT="$ROOT_DIR/data/milvus_lite.db"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Missing virtual environment: $VENV_DIR"
  echo "Create or point VENV_DIR to the existing backend .venv first."
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Copy backend/.env.example to backend/.env and fill the required values."
  exit 1
fi

if ! python3 -m uvicorn --version >/dev/null 2>&1; then
  echo "uvicorn is not available in $VENV_DIR. Run: pip install -r requirements.txt"
  exit 1
fi

rag_enabled="$(awk -F= '/^RAG_ENABLED=/{print tolower($2)}' "$ENV_FILE" | tail -n 1 | tr -d '[:space:]')"
milvus_db_path="$(awk -F= '/^MILVUS_LITE_DB_PATH=/{print $2}' "$ENV_FILE" | tail -n 1 | tr -d '[:space:]')"

if [[ -z "${milvus_db_path}" ]]; then
  milvus_db_path="$MILVUS_DB_DEFAULT"
elif [[ "$milvus_db_path" != /* ]]; then
  milvus_db_path="$ROOT_DIR/${milvus_db_path#./}"
fi

if [[ "$rag_enabled" == "true" ]]; then
  if [[ "$AUTO_INDEX_RAG" == "true" || ! -f "$milvus_db_path" ]]; then
    echo "Preparing role knowledge index..."
    python3 "$ROOT_DIR/scripts/index_role_knowledge.py"
  fi
fi

reload_args=()
if [[ "$RELOAD" == "true" ]]; then
  reload_args+=(--reload)
fi

echo "Starting backend on http://$HOST:$PORT"
exec python3 -m uvicorn app.main:app --host "$HOST" --port "$PORT" "${reload_args[@]}"
