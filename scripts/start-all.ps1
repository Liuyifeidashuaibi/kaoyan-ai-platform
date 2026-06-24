# One-click start: Docker engine + all containers + Ollama + Translator
# Usage: .\scripts\start-all.ps1
#        .\scripts\start-all.ps1 -Build    # rebuild images

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. "$PSScriptRoot\_dev-common.ps1"

Write-Host ""
Write-Host "=== Kaoyan AI Platform - One-Click Start ===" -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "start-docker-engine.ps1")
if ($LASTEXITCODE -ne 0) { exit 1 }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "Missing .env. Run: copy .env.example .env" -ForegroundColor Red
    exit 1
}

Import-ProjectDotEnv


# word_lib: auto-import ECDICT stardict.db / ecdict.csv when present
Write-Host "Checking word_lib.db ..." -ForegroundColor Cyan
python (Join-Path $Root "scripts\ensure_word_lib.py")
if ($LASTEXITCODE -ne 0) { exit 1 }

Start-OllamaIfNeeded | Out-Null

Write-Host ""
Write-Host "Starting Docker containers..." -ForegroundColor Cyan
if ($Build) {
    docker compose up -d --build
} else {
    docker compose up -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose failed" -ForegroundColor Red
    exit 1
}

Ensure-BackendPiper

& (Join-Path $PSScriptRoot "hide-docker-ui.ps1") | Out-Null

Write-Host ""
Write-Host "Waiting for services..." -ForegroundColor Cyan
Start-Sleep -Seconds 10

& (Join-Path $PSScriptRoot "check-dev.ps1")

Write-Host ""
Write-Host "Done. Site: http://localhost:3000" -ForegroundColor Green
Write-Host "Stop: .\scripts\stop-all.ps1" -ForegroundColor DarkGray
