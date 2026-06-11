# 启动 Cloudflare Tunnel（固定域名，需先配置 cloudflare-tunnel/config.yml）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $Root "cloudflare-tunnel\config.yml"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 cloudflared。安装方式：" -ForegroundColor Red
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
    Write-Host "  或从 https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ 下载" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $ConfigPath)) {
    Write-Host "未找到 $ConfigPath" -ForegroundColor Red
    Write-Host "请复制 cloudflare-tunnel\config.yml.example 为 config.yml 并完成隧道配置。" -ForegroundColor Yellow
    Write-Host "详细步骤见 DEPLOY.md「本地后端 + Cloudflare Tunnel」章节。" -ForegroundColor Yellow
    exit 1
}

Write-Host "启动 Cloudflare Tunnel（config: $ConfigPath）" -ForegroundColor Green
Write-Host "请确保 FastAPI 已在 127.0.0.1:8000 运行（scripts\start-backend.ps1）" -ForegroundColor Cyan
cloudflared tunnel --config $ConfigPath run
