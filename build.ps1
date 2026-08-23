# Build the frontend for production. core/backend.py auto-mounts
# frontend/dist once it exists (falls back to web/ otherwise), so this is
# also what main_web.py (the pywebview desktop shell) serves.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\frontend"

bun install
bun run build

Write-Host ""
Write-Host "Built frontend/dist - served automatically by core/backend.py."
Write-Host "Run the desktop app with: .\.venv\Scripts\Activate.ps1; python main_web.py"
