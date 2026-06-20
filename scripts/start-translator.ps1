# 单独启动 Translator 翻译服务（:8100）
# 用法: .\scripts\start-translator.ps1

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_dev-common.ps1"

Import-ProjectDotEnv
$TranslatorRoot = Get-TranslatorRoot
$startScript = Join-Path $TranslatorRoot "scripts\start-server.ps1"

if (-not (Test-Path $startScript)) {
    Write-Host "未找到: $startScript" -ForegroundColor Red
    Write-Host "请在 .env 设置 TRANSLATOR_ROOT=你的 translatorai 路径" -ForegroundColor Yellow
    Read-Host "按 Enter 退出"
    exit 1
}

Write-Host "=== Translator :8100 ===" -ForegroundColor Cyan
Write-Host "项目: $TranslatorRoot" -ForegroundColor DarkGray
Write-Host "需本机 Ollama 已运行 (11434)" -ForegroundColor DarkGray

& $startScript
