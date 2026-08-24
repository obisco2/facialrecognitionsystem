# One-time bootstrap: python venv + backend deps, frontend deps (bun).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Python backend (.venv)"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt

Write-Host "==> Frontend (frontend/)"
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Write-Error "bun not found. Install it from https://bun.sh before continuing."
    exit 1
}
Push-Location frontend
bun install
Pop-Location

Write-Host ""
Write-Host "Setup complete. Next:"
Write-Host "  .\dev.ps1     - run backend + frontend dev servers together"
Write-Host "  .\build.ps1   - build the frontend for the desktop app (main_web.py)"
