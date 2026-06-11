# 快速临时隧道（无需自有域名，每次 URL 会变，仅适合测试）
# 启动后会输出类似 https://xxxx.trycloudflare.com 的地址
$ErrorActionPreference = "Stop"

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "未找到 cloudflared。安装：" -ForegroundColor Red
    Write-Host "  winget install --id Cloudflare.cloudflared" -ForegroundColor Yellow
    exit 1
}

Write-Host "启动临时 Cloudflare Tunnel → http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "请将输出的 https://....trycloudflare.com 填入 Vercel 的 BACKEND_URL 与 NEXT_PUBLIC_API_URL" -ForegroundColor Cyan
Write-Host "请确保 FastAPI 已在 127.0.0.1:8000 运行" -ForegroundColor Cyan
cloudflared tunnel --url http://127.0.0.1:8000
