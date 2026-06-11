# 启动本地 FastAPI 后端（端口 8000）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Backend

if (-not (Test-Path $VenvPython)) {
    Write-Host "未找到 backend\.venv，正在创建虚拟环境并安装依赖..." -ForegroundColor Yellow
    python -m venv .venv
    & ".\.venv\Scripts\pip.exe" install -r requirements.txt
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "警告: 项目根目录缺少 .env，请复制 .env.example 并填写 DASHSCOPE_API_KEY" -ForegroundColor Yellow
}

Write-Host "启动 FastAPI: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "API 文档: http://127.0.0.1:8000/docs" -ForegroundColor Green
& $VenvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
