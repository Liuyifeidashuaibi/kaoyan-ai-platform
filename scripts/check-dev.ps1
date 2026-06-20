# Check local dev / Docker service health
$ErrorActionPreference = "Continue"
. "$PSScriptRoot\_dev-common.ps1"

function Test-Http($url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 8
        return @{ ok = $true; status = $r.StatusCode; body = $r.Content.Substring(0, [Math]::Min(120, $r.Content.Length)) }
    } catch {
        return @{ ok = $false; status = $_.Exception.Response.StatusCode.value__; body = $_.Exception.Message }
    }
}

Write-Host ""
Write-Host "=== Kaoyan AI Platform - Health Check ===" -ForegroundColor Cyan

if (Test-PortListen 6379) {
    Write-Host "[OK] Redis :6379" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Redis :6379 - run .\scripts\start-redis.ps1" -ForegroundColor Red
}

foreach ($item in @(
    @{ name = "Translator :8100"; url = "http://127.0.0.1:8100/health" },
    @{ name = "Backend :8000"; url = "http://127.0.0.1:8000/api/health" },
    @{ name = "Tasks/Redis"; url = "http://127.0.0.1:8000/api/tasks/health" },
    @{ name = "Translator proxy"; url = "http://127.0.0.1:8000/api/translator/health" },
    @{ name = "En-learn modules"; url = "http://127.0.0.1:8000/" },
    @{ name = "TTS host :8200"; url = "http://127.0.0.1:8200/health" },
    @{ name = "Frontend :3000"; url = "http://127.0.0.1:3000" }
)) {
    $res = Test-Http $item.url
    if ($res.ok) {
        Write-Host "[OK] $($item.name)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($item.name) - $($res.body)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  Site:       http://localhost:3000"
Write-Host "  Translator: http://localhost:3000/translator"
Write-Host "  API docs:   http://127.0.0.1:8000/docs"
Write-Host ""
Write-Host "Start scripts:" -ForegroundColor DarkGray
Write-Host "  start-redis.ps1 | start-celery-worker.ps1 | start-celery-beat.ps1"
Write-Host "  start-translator.ps1 | start-backend.ps1 | start-frontend.ps1"
Write-Host ""
