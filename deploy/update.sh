#!/bin/bash
set -e

APP_DIR="/var/www/attendiq/repo"

echo "=== AttendIQ Update ==="

cd "$APP_DIR"
echo "[1/4] Pulling latest code..."
sudo -u www-data git pull

echo "[2/4] Rebuilding frontend..."
cd "$APP_DIR/repo/frontend" 2>/dev/null || cd "$APP_DIR/frontend"
if command -v bun &> /dev/null; then
    bun install
    bun run build
elif [ -f "$HOME/.bun/bin/bun" ]; then
    ~/.bun/bin/bun install
    ~/.bun/bin/bun run build
fi
sudo rm -rf /var/www/attendiq/frontend
sudo cp -r "$APP_DIR/frontend/dist" /var/www/attendiq/frontend
sudo chown -R www-data:www-data /var/www/attendiq/frontend

echo "[3/4] Installing/updating Python deps..."
cd "$APP_DIR"
sudo -u www-data .venv/bin/pip install -r requirements.txt -q

echo "[4/4] Restarting backend..."
sudo systemctl restart attendiq

echo ""
echo "=== Update complete ==="
echo "Frontend: https://attendiq.tadstech.dev"
echo "API:      https://attendiq-api.tadstech.dev"
