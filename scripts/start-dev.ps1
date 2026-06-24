# 本机一键：Redis 后台自动起 + 各服务分窗口（Celery / 翻译 / 后端 / 前端）
# Docker 无窗口一键: .\scripts\start-all.ps1
# 关闭: .\scripts\stop-dev.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"
Set-DevConsoleUtf8

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
Write-Host "Redis 后台自动启动 → Celery Worker → Celery Beat → 翻译 → 后端 → 前端`n" -ForegroundColor DarkGray

# Redis 后台 Docker 启动，无需单独窗口
if (-not (Start-RedisDev)) {
    Write-Host "[WARN] Redis 未就绪，Celery/缓存可能异常" -ForegroundColor Yellow
}

Start-InNewDevWindow -Title "Celery Worker" -ScriptPath (Join-Path $PSScriptRoot "start-celery-worker.ps1")
Start-Sleep -Seconds 2

Start-InNewDevWindow -Title "Celery Beat" -ScriptPath (Join-Path $PSScriptRoot "start-celery-beat.ps1")
Start-Sleep -Seconds 2

Try-StartWindow -Port 8200 -Title "TTS Host :8200" -ScriptName "start-tts-host.ps1"
Try-StartWindow -Port 8000 -Title "后端 :8000" -ScriptName "start-backend.ps1"
Try-StartWindow -Port 3000 -Title "前端 :3000" -ScriptName "start-frontend.ps1"

Write-Host "`n启动完成。正在检查..." -ForegroundColor Cyan
Start-Sleep -Seconds 5
& (Join-Path $PSScriptRoot "check-dev.ps1")

Write-Host "单独启动某个服务:" -ForegroundColor Cyan
Write-Host "  .\scripts\start-redis.ps1"
Write-Host "  .\scripts\start-celery-worker.ps1"
Write-Host "  .\scripts\start-celery-beat.ps1"
Write-Host "  .\scripts\start-tts-host.ps1"
Write-Host "  .\scripts\start-backend.ps1"
Write-Host "  .\scripts\start-frontend.ps1"
