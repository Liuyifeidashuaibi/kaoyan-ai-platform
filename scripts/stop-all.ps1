# Stop all services (Docker Compose, or local dev if Docker is unavailable)
# Usage: .\scripts\stop-all.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "=== Stop all services ===" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Stopping local dev processes instead..." -ForegroundColor Yellow
    & "$PSScriptRoot\stop-dev.ps1"
    exit $LASTEXITCODE
}

docker compose down
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose down failed. Trying local dev stop..." -ForegroundColor Yellow
    & "$PSScriptRoot\stop-dev.ps1"
    exit $LASTEXITCODE
}

. "$PSScriptRoot\_dev-common.ps1"
Stop-PortProcess -Port 8200 -Label "TTS host :8200"

Write-Host "Docker services stopped." -ForegroundColor Green
Write-Host "Close Ollama manually from system tray if it is running." -ForegroundColor DarkGray
