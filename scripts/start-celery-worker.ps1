# 单独启动 Celery Worker — 处理 PDF/OCR/爬虫/RAG 等异步任务
# 用法: .\scripts\start-celery-worker.ps1
# 需先启动 Redis: .\scripts\start-redis.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot
$Backend = Join-Path $Root "backend"
Import-ProjectDotEnv

if (-not (Test-PortListen 6379)) {
    Write-Host "警告: Redis 6379 未运行，请先执行 .\scripts\start-redis.ps1" -ForegroundColor Red
}

$VenvPython = Get-BackendVenvPython
Set-Location $Backend

Write-Host "=== Celery Worker ===" -ForegroundColor Cyan
Write-Host "队列: default, heavy" -ForegroundColor DarkGray
Write-Host "Broker: $($env:CELERY_BROKER_URL)" -ForegroundColor DarkGray
Write-Host "关窗口或 Ctrl+C 停止 Worker" -ForegroundColor DarkGray

& $VenvPython -m celery -A app.infrastructure.tasks.celery_app worker `
    --loglevel=info `
    -Q default,heavy `
    --concurrency=2