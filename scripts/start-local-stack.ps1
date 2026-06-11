# 在新窗口中分别启动后端与 Cloudflare Tunnel
$ErrorActionPreference = "Stop"
$Scripts = $PSScriptRoot

Write-Host "正在打开后端窗口..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Scripts "start-backend.ps1")

Start-Sleep -Seconds 2

$config = Join-Path (Split-Path -Parent $Scripts) "cloudflare-tunnel\config.yml"
if (Test-Path $config) {
    Write-Host "正在打开 Tunnel 窗口（固定域名）..." -ForegroundColor Green
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Scripts "start-tunnel.ps1")
} else {
    Write-Host "未找到 config.yml，改用临时隧道（URL 每次会变）..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $Scripts "start-tunnel-quick.ps1")
}

Write-Host "完成。请保持两个 PowerShell 窗口运行。" -ForegroundColor Cyan
