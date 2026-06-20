# 本机一键：每个服务单独一个窗口（Redis + Celery + 翻译 + 后端 + 前端）
# Docker 无窗口一键: .\scripts\start-all.ps1
# 关闭: .\scripts\stop-dev.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot

function Try-StartWindow {
    param(
        [int]$Port,
        [string]$Title,
        [string]$ScriptName
    )
    if (Test-PortListen $Port) {
        Write-Host "[跳过] $Title 已在运行" -ForegroundColor Yellow
        return
    }
    $scriptPath = Join-Path $PSScriptRoot $ScriptName
    Start-InNewDevWindow -Title $Title -ScriptPath $scriptPath
    Start-Sleep -Seconds 2
}

Write-Host "`n=== 考研 AI 平台 · 本机分窗口启动 ===" -ForegroundColor Cyan
Write-Host "将依次打开: Redis → Celery Worker → Celery Beat → 翻译 → 后端 → 前端`n" -ForegroundColor DarkGray

# Celery 无端口，开新窗口（若已有 Worker 窗口请先关掉，避免重复）
if (-not (Test-PortListen 6379)) {
    Start-InNewDevWindow -Title "Redis :6379" -ScriptPath (Join-Path $PSScriptRoot "start-redis.ps1")
    Start-Sleep -Seconds 3
} else {
    Write-Host "[跳过] Redis 6379 已在运行" -ForegroundColor Yellow
}

Start-InNewDevWindow -Title "Celery Worker" -ScriptPath (Join-Path $PSScriptRoot "start-celery-worker.ps1")
Start-Sleep -Seconds 2

Start-InNewDevWindow -Title "Celery Beat" -ScriptPath (Join-Path $PSScriptRoot "start-celery-beat.ps1")
Start-Sleep -Seconds 2

Try-StartWindow -Port 8100 -Title "Translator :8100" -ScriptName "start-translator.ps1"
Try-StartWindow -Port 8000 -Title "后端 :8000" -ScriptName "start-backend.ps1"
Try-StartWindow -Port 3000 -Title "前端 :3000" -ScriptName "start-frontend.ps1"

Write-Host "`n启动完成。正在检查..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
& (Join-Path $PSScriptRoot "check-dev.ps1")

Write-Host "单独启动某个服务:" -ForegroundColor Cyan
Write-Host "  .\scripts\start-redis.ps1"
Write-Host "  .\scripts\start-celery-worker.ps1"
Write-Host "  .\scripts\start-celery-beat.ps1"
Write-Host "  .\scripts\start-translator.ps1"
Write-Host "  .\scripts\start-backend.ps1"
Write-Host "  .\scripts\start-frontend.ps1"
