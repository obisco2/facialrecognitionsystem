#!/usr/bin/env bash
# Run the FastAPI backend (:8000, hot-reload) and the Vite frontend dev
# server (:5173, proxies /api -> :8000) together. Ctrl+C stops both.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -d .venv ]; then
  echo "No .venv found — run ./setup.sh first." >&2
  exit 1
fi
source .venv/bin/activate

pids=()
cleanup() {
  echo
  echo "Stopping services..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "==> Backend  · http://127.0.0.1:8000"
uvicorn core.backend:app --reload --port 8000 &
pids+=($!)

echo "==> Frontend · http://127.0.0.1:5173"
(cd frontend && bun run dev) &
pids+=($!)

wait
