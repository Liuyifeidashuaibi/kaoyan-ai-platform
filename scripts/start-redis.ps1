# 单独启动 Redis（:6379）— 本窗口保持运行，关窗口即停
# 用法: .\scripts\start-redis.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot
Import-ProjectDotEnv

if (Test-PortListen 6379) {
    Write-Host "Redis 6379 已在运行，无需重复启动。" -ForegroundColor Yellow
    Write-Host "测试: redis-cli ping  或  docker exec kaoyan-redis-dev redis-cli ping" -ForegroundColor Cyan
    Read-Host "按 Enter 关闭本窗口（不会停止已运行的 Redis）"
    exit 0
}

Write-Host "=== 启动 Redis :6379 ===" -ForegroundColor Cyan
Write-Host ".env 应配置 REDIS_URL=redis://127.0.0.1:6379/0" -ForegroundColor DarkGray

# 优先 Docker（Windows 最常见）
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $conf = Join-Path $Root "docker\redis.conf"
    if (-not (Test-Path $conf)) {
        Write-Host "缺少 $conf" -ForegroundColor Red
        exit 1
    }
    Write-Host "使用 Docker 启动 Redis（前台，关窗口会停）..." -ForegroundColor Green
    docker run --rm --name kaoyan-redis-dev `
        -p 6379:6379 `
        -v "${conf}:/usr/local/etc/redis/redis.conf:ro" `
        redis:7-alpine redis-server /usr/local/etc/redis/redis.conf
    exit $LASTEXITCODE
}

# 其次 WSL
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    Write-Host "使用 WSL 启动 redis-server..." -ForegroundColor Green
    wsl redis-server --port 6379 --maxmemory 512mb --maxmemory-policy allkeys-lru
    exit $LASTEXITCODE
}

# 本机 redis-server
if (Get-Command redis-server -ErrorAction SilentlyContinue) {
    Write-Host "使用本机 redis-server..." -ForegroundColor Green
    redis-server --port 6379 --maxmemory 512mb --maxmemory-policy allkeys-lru
    exit $LASTEXITCODE
}

Write-Host "未找到 Docker / WSL / redis-server。" -ForegroundColor Red
Write-Host "请安装 Docker Desktop 后重试，或在 WSL 中: sudo apt install redis-server" -ForegroundColor Yellow
Read-Host "按 Enter 退出"
exit 1
