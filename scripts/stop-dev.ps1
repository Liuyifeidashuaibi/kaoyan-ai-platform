# Stop local dev services (ports + Docker Redis container)
# Usage: .\scripts\stop-dev.ps1

$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_dev-common.ps1"

Write-Host ""
Write-Host "=== Stop local dev services ===" -ForegroundColor Cyan

if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker rm -f kaoyan-redis-dev 2>$null | Out-Null
    Write-Host "[OK] Removed Docker container kaoyan-redis-dev (if existed)" -ForegroundColor Green
}

Stop-PortProcess -Port 3000 -Label "frontend :3000"
Stop-PortProcess -Port 8000 -Label "backend :8000"
Stop-PortProcess -Port 8200 -Label "TTS host :8200"
Stop-PortProcess -Port 6379 -Label "redis :6379"

Write-Host ""
Write-Host "Close Celery Worker / Beat PowerShell windows manually (no fixed port)." -ForegroundColor Yellow
Write-Host "Close Ollama from system tray if needed." -ForegroundColor DarkGray
