# Refresh: pull latest code, reinstall deps, rebuild frontend.
# Safe to re-run. Windows equivalent of refresh.sh (no systemd handling).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> 1/3 Git pull"
if (-not (Test-Path ".git")) {
    Write-Warning "Not a git repo — skipping pull."
} else {
    git fetch origin
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    git pull --ff-only origin $branch
    if ($LASTEXITCODE -ne 0) { throw "git pull failed (local changes?). Commit/stash first, then re-run." }
    Write-Host ("On " + (git rev-parse --short HEAD).Trim())
}

Write-Host "==> 2/3 Python deps"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt

Write-Host "==> 3/3 Frontend rebuild"
if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    throw "bun not found. Install it from https://bun.sh before continuing."
}
Set-Location "$PSScriptRoot\frontend"
bun install
bun run build
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Refresh complete. Next:"
Write-Host "  .\dev.ps1     — run backend + frontend dev servers"
Write-Host "  python main.py  — desktop app (serves frontend/dist)"
