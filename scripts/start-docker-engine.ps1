# Start Docker engine without blocking (CLI, no dashboard if configured)
# Usage: .\scripts\start-docker-engine.ps1

$ErrorActionPreference = "Stop"

function Wait-DockerReady {
    param([int]$TimeoutSec = 120)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            docker info 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "Checking Docker engine..." -ForegroundColor Cyan

$status = docker desktop status 2>&1 | Out-String
if ($status -match "Status\s+running") {
    Write-Host "[OK] Docker engine already running" -ForegroundColor Green
} else {
    Write-Host "Starting Docker engine (background)..." -ForegroundColor Cyan
    docker desktop start -d
    if (-not (Wait-DockerReady)) {
        Write-Host "Docker engine did not become ready in time." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Docker engine started" -ForegroundColor Green
}

if (-not (Wait-DockerReady -TimeoutSec 5)) {
    Write-Host "Docker CLI cannot reach the engine." -ForegroundColor Red
    exit 1
}
