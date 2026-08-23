#!/usr/bin/env bash
# Build the frontend for production. core/backend.py auto-mounts
# frontend/dist once it exists (falls back to web/ otherwise), so this is
# also what main_web.py (the pywebview desktop shell) serves.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/frontend"

bun install
bun run build

echo
echo "Built frontend/dist — served automatically by core/backend.py."
echo "Run the desktop app with: source .venv/bin/activate && python main_web.py"
