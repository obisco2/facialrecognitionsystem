#!/usr/bin/env bash
# One-time bootstrap: python venv + backend deps, frontend deps (bun).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> Python backend (.venv)"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

echo "==> Frontend (frontend/)"
if ! command -v bun >/dev/null 2>&1; then
  echo "bun not found. Install it from https://bun.sh before continuing." >&2
  exit 1
fi
(cd frontend && bun install)

echo
echo "Setup complete. Next:"
echo "  ./dev.sh     — run backend + frontend dev servers together"
echo "  ./build.sh   — build the frontend for the desktop app (main_web.py)"
