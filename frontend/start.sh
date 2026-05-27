#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-5173}"
AUTO_INSTALL="${AUTO_INSTALL:-true}"

cd "$ROOT_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available. Install Node.js first."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/node_modules" ]]; then
  if [[ "$AUTO_INSTALL" == "true" ]]; then
    echo "Installing frontend dependencies..."
    npm install
  else
    echo "Missing node_modules. Run: npm install"
    exit 1
  fi
fi

echo "Starting frontend on http://$HOST:$PORT"
exec npm run dev -- --host "$HOST" --port "$PORT"
