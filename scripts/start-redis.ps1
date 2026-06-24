# 单独启动 Redis（:6379）— 本窗口保持运行，关窗口即停
# 用法: .\scripts\start-redis.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot
Import-ProjectDotEnv

Set-DevConsoleUtf8

if (Test-PortListen 6379) {
    Write-Host "Redis 6379 已在运行，无需重复启动。" -ForegroundColor Yellow
    Write-Host "测试: docker exec kaoyan-redis-dev redis-cli ping" -ForegroundColor Cyan
    Read-Host "按 Enter 关闭本窗口（不会停止已运行的 Redis）"
    exit 0
}

Write-Host "=== 启动 Redis :6379 ===" -ForegroundColor Cyan
Write-Host ".env 应配置 REDIS_URL=redis://127.0.0.1:6379/0" -ForegroundColor DarkGray

# 单独调试时用前台模式；start-dev.ps1 会用后台 Docker
if (Start-RedisDev -Foreground) {
    exit 0
}

Write-Host "未找到 Docker / WSL / redis-server。" -ForegroundColor Red
Write-Host "请安装 Docker Desktop 后重试，或在 WSL 中: sudo apt install redis-server" -ForegroundColor Yellow
Read-Host "按 Enter 退出"
exit 1
