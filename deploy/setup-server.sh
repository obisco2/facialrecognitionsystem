#!/bin/bash
set -e

echo "=== AttendIQ Final Setup (run after server reboot) ==="

# --- Add 2GB swap to prevent OOM during dlib compilation ---
if [ ! -f /swapfile ]; then
    echo "[1/7] Creating 2GB swap file..."
    sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile || echo "WARNING: Failed to enable swap. This is expected on ZFS/LXC containers. Continuing..."
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab || true
    echo "Swap enabled:"
    free -h || true
else
    echo "[1/7] Swap already exists"
    sudo swapon --show
fi

# --- Install system deps ---
echo "[2/7] Installing system dependencies..."
sudo apt update && sudo apt install -y python3 python3-venv python3-pip curl build-essential cmake git ufw

# --- Install Caddy ---
echo "[3/7] Installing Caddy..."
if ! command -v caddy &> /dev/null; then
    sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
    sudo apt update && sudo apt install caddy -y
fi
echo "Caddy: $(caddy version)"

# --- Clone repo ---
echo "[4/7] Cloning repo..."
if [ -d /var/www/attendiq/repo/.git ]; then
    cd /var/www/attendiq/repo
    git pull
else
    # Find active local repository to copy from, otherwise clone
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_DIR="$(dirname "$SCRIPT_DIR")"
    if [ -d "$REPO_DIR/.git" ]; then
        echo "Copying from local path: $REPO_DIR"
        sudo cp -r "$REPO_DIR" /var/www/attendiq/repo
    else
        echo "Cloning from GitHub..."
        sudo git clone git@github.com:TADSTech/facialrecognitionsystem.git /var/www/attendiq/repo
    fi
fi
sudo chown -R www-data:www-data /var/www/attendiq/repo

# --- Build frontend ---
echo "[5/7] Building frontend..."
cd /var/www/attendiq/repo/frontend
if [ ! -d node_modules ]; then
    curl -fsSL https://bun.sh/install | bash
    ~/.bun/bin/bun install
fi
~/.bun/bin/bun run build
sudo rm -rf /var/www/attendiq/frontend
sudo cp -r dist /var/www/attendiq/frontend
sudo chown -R www-data:www-data /var/www/attendiq/frontend

# --- Python venv + deps ---
echo "[6/7] Installing Python dependencies (with swap for dlib)..."
cd /var/www/attendiq/repo
sudo chown -R www-data:www-data .
if [ ! -d ".venv" ]; then
    sudo -u www-data python3 -m venv .venv
fi
sudo -u www-data .venv/bin/pip install --upgrade pip
sudo -u www-data .venv/bin/pip install setuptools'<81'
sudo -u www-data .venv/bin/pip install 'face_recognition_models @ git+https://github.com/ageitgey/face_recognition_models'
# Force single-threaded compilation to prevent OOM on 2GB RAM VPS
sudo -u www-data MAKEFLAGS="-j1" CMAKE_BUILD_PARALLEL_LEVEL=1 .venv/bin/pip install -r requirements.txt

# --- Systemd + Caddy ---
echo "[7/7] Configuring services..."
sudo tee /etc/systemd/system/attendiq.service > /dev/null << 'UNIT'
[Unit]
Description=AttendIQ Backend API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/attendiq/repo
ExecStart=/var/www/attendiq/repo/.venv/bin/python -m uvicorn core.backend:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now attendiq

sudo tee /etc/caddy/Caddyfile > /dev/null << 'CADDY'
attendiq.tadstech.dev {
    root * /var/www/attendiq/frontend
    file_server
    try_files {path} /index.html
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }
    encode gzip
}

attendiq-api.tadstech.dev {
    reverse_proxy localhost:8000
    request_body {
        max_size 50MB
    }
    header {
        Access-Control-Allow-Origin https://attendiq.tadstech.dev
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization"
        Access-Control-Allow-Credentials true
    }
    @options method OPTIONS
    handle @options {
        respond 204
    }
    encode gzip
}
CADDY

sudo systemctl reload caddy

sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 22/tcp && sudo ufw --force enable

echo ""
echo "=== DONE ==="
echo "Frontend: https://attendiq.tadstech.dev"
echo "API:      https://attendiq-api.tadstech.dev"
curl -s http://localhost:8000/api/config | head -c 200 || echo "(backend starting...)"
