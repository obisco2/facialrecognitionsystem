# Run the FastAPI backend (:8000, hot-reload) and the Vite frontend dev
# server (:5173, proxies /api -> :8000) together. Ctrl+C stops both.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Error "No .venv found - run .\setup.ps1 first."
    exit 1
}

$backend = Start-Process -PassThru -NoNewWindow powershell -ArgumentList `
    "-NoProfile", "-Command", ". .\.venv\Scripts\Activate.ps1; uvicorn core.backend:app --reload --port 8000"

$frontend = Start-Process -PassThru -NoNewWindow powershell -ArgumentList `
    "-NoProfile", "-Command", "cd frontend; bun run dev"

Write-Host "==> Backend  - http://127.0.0.1:8000"
Write-Host "==> Frontend - http://127.0.0.1:5173"
Write-Host "Press Ctrl+C to stop both."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Write-Host ""
    Write-Host "Stopping services..."
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
