# 单独启动 Next.js 前端（:3000）
# 用法: .\scripts\start-frontend.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

$Root = Get-ProjectRoot

if (Test-PortListen 3000) {
    Write-Host "前端 3000 已在运行 → http://localhost:3000" -ForegroundColor Yellow
    Read-Host "按 Enter 关闭本窗口"
    exit 0
}

Set-Location $Root

if (-not (Test-Path (Join-Path $Root "node_modules"))) {
    Write-Host "首次运行，正在 npm install..." -ForegroundColor Yellow
    npm install
}

Write-Host "=== 前端 :3000 ===" -ForegroundColor Green
Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "翻译页: http://localhost:3000/translator" -ForegroundColor Cyan

npm run dev
