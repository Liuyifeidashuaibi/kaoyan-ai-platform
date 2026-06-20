# 单独启动 Celery Beat — 定时任务（如每日 03:00 分数线爬虫）
# 用法: .\scripts\start-celery-beat.ps1
# 需先: Redis + Celery Worker

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot
$Backend = Join-Path $Root "backend"
Import-ProjectDotEnv

if (-not (Test-PortListen 6379)) {
    Write-Host "警告: Redis 6379 未运行" -ForegroundColor Red
}

$VenvPython = Get-BackendVenvPython
Set-Location $Backend

Write-Host "=== Celery Beat（定时调度）===" -ForegroundColor Cyan
Write-Host "CELERY_BEAT_ENABLED=$($env:CELERY_BEAT_ENABLED)" -ForegroundColor DarkGray
Write-Host "关窗口或 Ctrl+C 停止 Beat" -ForegroundColor DarkGray

& $VenvPython -m celery -A app.infrastructure.tasks.celery_app beat --loglevel=info
