# 首次配置 Cloudflare Tunnel（需浏览器操作，只需做一次）
$ErrorActionPreference = "Stop"
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "正在安装 cloudflared..." -ForegroundColor Yellow
    winget install --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
}

Write-Host @"

========== 步骤 1/3：登录 Cloudflare ==========
即将打开浏览器，请选择要用的域名并完成授权。

"@ -ForegroundColor Cyan
cloudflared tunnel login

Write-Host @"

========== 步骤 2/3：创建隧道 ==========
"@ -ForegroundColor Cyan
cloudflared tunnel create kaoyan-api

Write-Host @"

========== 步骤 3/3：绑定 DNS ==========
请将 api.你的域名.com 换成你的子域名（域名须在 Cloudflare 中）：

  cloudflared tunnel route dns kaoyan-api api.你的域名.com

然后：
  1. copy cloudflare-tunnel\config.yml.example cloudflare-tunnel\config.yml
  2. 编辑 config.yml，填写 credentials-file 和 hostname
  3. 在 Vercel 设置 BACKEND_URL 和 NEXT_PUBLIC_API_URL 为 https://api.你的域名.com
  4. 运行 .\scripts\start-local-stack.ps1

"@ -ForegroundColor Green
