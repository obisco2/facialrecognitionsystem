#!/bin/bash
set -e

REPO="https://github.com/TADSTech/facialrecognitionsystem.git"
APP_DIR="/var/www/attendiq"

echo "=== AttendIQ Deployment Script ==="

# --- 1. Install system dependencies ---
echo "[1/8] Installing system dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip curl build-essential cmake git ufw

# --- 2. Install Caddy ---
echo "[2/8] Installing Caddy..."
if ! command -v caddy &> /dev/null; then
    sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null
    sudo apt update
    sudo apt install caddy -y
fi
echo "Caddy installed: $(caddy version)"

# --- 3. Clone / pull repo ---
echo "[3/8] Fetching code from GitHub..."
sudo mkdir -p "$APP_DIR"
sudo chown -R www-data:www-data "$APP_DIR"

if [ -d "$APP_DIR/repo/.git" ]; then
    cd "$APP_DIR/repo"
    sudo -u www-data git pull
else
    sudo -u www-data git clone "$REPO" "$APP_DIR/repo"
    cd "$APP_DIR/repo"
fi

# --- 4. Build frontend ---
echo "[4/8] Building frontend..."
if [ ! -f "$APP_DIR/frontend/index.html" ] || [ "$APP_DIR/repo/frontend/dist" -nt "$APP_DIR/frontend/index.html" ]; then
    if command -v bun &> /dev/null; then
        cd "$APP_DIR/repo/frontend"
        bun install
        bun run build
    elif [ -f "$HOME/.bun/bin/bun" ]; then
        cd "$APP_DIR/repo/frontend"
        "$HOME/.bun/bin/bun" install
        "$HOME/.bun/bin/bun" run build
    else
        echo "Bun not found — installing..."
        curl -fsSL https://bun.sh/install | bash
        source ~/.bashrc
        cd "$APP_DIR/repo/frontend"
        ~/.bun/bin/bun install
        ~/.bun/bin/bun run build
    fi
    # Sync dist to serve directory
    sudo rm -rf "$APP_DIR/frontend"
    sudo cp -r "$APP_DIR/repo/frontend/dist" "$APP_DIR/frontend"
    sudo chown -R www-data:www-data "$APP_DIR/frontend"
fi

# --- 5. Setup Python venv + deps ---
echo "[5/8] Setting up Python environment..."
cd "$APP_DIR/repo"
if [ ! -d ".venv" ]; then
    sudo -u www-data python3 -m venv .venv
fi
sudo -u www-data .venv/bin/pip install --upgrade pip
sudo -u www-data .venv/bin/pip install -r requirements.txt

# --- 6. Create systemd service ---
echo "[6/8] Creating systemd service..."
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
sudo systemctl enable attendiq
sudo systemctl restart attendiq

# --- 7. Deploy Caddyfile ---
echo "[7/8] Deploying Caddyfile..."
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

# --- 8. Open firewall ---
echo "[8/8] Configuring firewall..."
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw --force enable

# --- Done ---
sleep 2
echo ""
echo "=== Deployment complete ==="
echo "Frontend: https://attendiq.tadstech.dev"
echo "API:      https://attendiq-api.tadstech.dev"
echo ""
echo "To update later, run: bash $APP_DIR/repo/deploy/update.sh"
