# Deployment Guide

## Ubuntu VPS with Caddy

### Prerequisites

- Ubuntu 22.04/24.04 VPS
- Domain pointed at your VPS IP
- SSH access as root or sudo user

### Step 1: Update System and Install Dependencies

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx certbot curl build-essential cmake
```

### Step 2: Install Caddy

```bash
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install caddy
```

### Step 3: Install Node/Bun for Frontend Build

```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
```

### Step 4: Clone and Set Up the Project

```bash
cd /var/www
git clone <your-repo-url> attendance
cd attendance

# Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend build
cd frontend
~/.bun/bin/bun install
~/.bun/bin/bun run build
cd ..
```

### Step 5: Create Systemd Service

```bash
cat > /etc/systemd/system/attendance.service << 'EOF'
[Unit]
Description=AttendIQ Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/attendance
ExecStart=/var/www/attendance/.venv/bin/python -m uvicorn core.backend:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chown -R www-data:www-data /var/www/attendance
chmod -R 755 /var/www/attendance

# Enable and start
systemctl daemon-reload
systemctl enable attendance
systemctl start attendance
```

### Step 6: Configure Caddy

```bash
cat > /etc/caddy/Caddyfile << 'EOF'
yourdomain.com {
    # Serve React frontend
    root * /var/www/attendance/frontend/dist
    file_server

    # Proxy API to FastAPI
    handle /api/* {
        reverse_proxy localhost:8000
    }

    # Handle SPA routing (React Router)
    try_files {path} /index.html

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
    }

    # Enable gzip
    encode gzip
}
EOF

# Reload Caddy
systemctl reload caddy
```

### Step 7: Get SSL Certificate

```bash
# Caddy auto-provisions SSL. Just make sure port 80 is open.
# If you need manual certbot:
certbot certonly --webroot -w /var/www/attendance/frontend/dist -d yourdomain.com
```

### Step 8: Open Firewall

```bash
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 22/tcp
ufw enable
```

### Step 9: Verify

```bash
# Check backend
curl http://localhost:8000/api/config

# Check frontend
curl -I https://yourdomain.com

# Check service status
systemctl status attendance
systemctl status caddy
journalctl -u attendance -f
```

---

## File Upload Size

If enrollment uploads fail, increase Caddy's body size limit:

```
request_body {
    max_size 10MB
}
```

---

## Updating the App

```bash
cd /var/www/attendance
git pull

# Rebuild frontend
cd frontend
~/.bun/bin/bun run build
cd ..

# Restart backend
systemctl restart attendance
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 502 Bad Gateway | Backend not running: `systemctl status attendance` |
| Camera not working | Check browser permissions, use HTTPS (required for `getUserMedia`) |
| Upload fails | Check `request_body { max_size }` in Caddy |
| Static files 404 | Verify `frontend/dist` exists and Caddy root matches |
| SQLite locked | Only one writer at a time; check for zombie processes |

---

## Alternative: Vercel (Frontend Only)

If you want frontend on Vercel and backend on VPS:

```bash
# Frontend: push to GitHub, connect to Vercel
# Set env var in Vercel dashboard:
# VITE_API_URL=https://yourdomain.com

# Update frontend/src/lib/api.ts to use the env var:
# const BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api'
```

Then Caddy on VPS only proxies the backend:

```
yourdomain.com {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle {
        redir https://yourdomain.com permanent
    }
}
```
