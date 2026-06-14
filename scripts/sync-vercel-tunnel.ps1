# 将 cloudflare-tunnel/.tunnel-url 同步到 Vercel 生产环境并触发部署
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$UrlFile = Join-Path $Root "cloudflare-tunnel\.tunnel-url"

if (-not (Test-Path $UrlFile)) {
    Write-Host "缺少 cloudflare-tunnel\.tunnel-url，请先运行 start-tunnel-quick.ps1" -ForegroundColor Red
    exit 1
}

$Url = (Get-Content $UrlFile | Where-Object { $_ -match "^https://" }) | Select-Object -First 1
if (-not $Url) {
    Write-Host ".tunnel-url 中未找到 https 地址" -ForegroundColor Red
    exit 1
}

Write-Host "同步到 Vercel: $Url" -ForegroundColor Cyan
Set-Location $Root
$Url | npx vercel env add BACKEND_URL production --force
$Url | npx vercel env add NEXT_PUBLIC_API_URL production --force
npx vercel --prod --yes
Write-Host "完成。请保持后端与 cloudflared 运行。" -ForegroundColor Green
