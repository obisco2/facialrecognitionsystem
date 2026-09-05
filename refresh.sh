#!/usr/bin/env bash
# Refresh: pull latest code, reinstall deps, rebuild frontend, restart service.
# Safe to re-run. Works locally and on the server (/var/www/attendiq/repo).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> 1/4 Git pull"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repo — skipping pull." >&2
else
  git fetch origin
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  # ff-only to avoid surprise merges; stash-less to keep local changes visible
  if ! git pull --ff-only origin "$BRANCH"; then
    echo "git pull failed (local changes?). Commit/stash first, then re-run." >&2
    exit 1
  fi
  echo "On $(git rev-parse --short HEAD) $(git log -1 --oneline | head -c 80)"
fi

echo "==> 2/4 Python deps"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt

echo "==> 3/4 Frontend rebuild"
if ! command -v bun >/dev/null 2>&1; then
  echo "bun not found. Install it from https://bun.sh before continuing." >&2
  exit 1
fi
(cd frontend && bun install && bun run build)

echo "==> 4/4 Restart (if applicable)"
RESTARTED=0
# Server layout: repo at /var/www/attendiq/repo, served copy at /var/www/attendiq/frontend
if [ -d "/var/www/attendiq/frontend" ] && [ -d "frontend/dist" ]; then
  if [ "$(pwd)" = "/var/www/attendiq/repo" ]; then
    rm -rf /var/www/attendiq/frontend
    cp -r frontend/dist /var/www/attendiq/frontend
    # best-effort ownership fix; ignore if not root/www-data
    chown -R www-data:www-data /var/www/attendiq/frontend 2>/dev/null || true
    echo "Synced frontend/dist -> /var/www/attendiq/frontend"
  fi
fi
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q "^attendiq\.service"; then
  if sudo -n systemctl restart attendiq 2>/dev/null; then
    echo "Restarted attendiq via sudo systemctl"
  else
    # fall back to plain systemctl (works when already root / no sudo needed)
    systemctl restart attendiq 2>/dev/null && echo "Restarted attendiq via systemctl" || echo "Could not restart attendiq — run: sudo systemctl restart attendiq"
  fi
  systemctl is-active --quiet attendiq && echo "attendiq: active" || echo "attendiq: NOT active — check journalctl -u attendiq"
  RESTARTED=1
fi

echo
if [ "$RESTARTED" = "0" ]; then
  echo "Refresh complete. Next:"
  echo "  ./dev.sh     — run backend + frontend dev servers"
  echo "  python main.py  — desktop app (serves frontend/dist)"
else
  echo "Refresh complete — service restarted."
  curl -sf http://127.0.0.1:8000/health 2>/dev/null | head -c 120 || true
  echo
fi
