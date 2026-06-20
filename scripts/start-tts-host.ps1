# Start Qwen3-TTS GPU host service on :8200 (for Docker backend)
# Usage: .\scripts\start-tts-host.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
. "$PSScriptRoot\_dev-common.ps1"

if (Test-PortListen 8200) {
    Write-Host "[OK] TTS host :8200 already running" -ForegroundColor Green
    exit 0
}

$qwenVenvPy = Join-Path $Root "data\tts\.venv\Scripts\python.exe"
$python = if (Test-Path $qwenVenvPy) { $qwenVenvPy } else { (Get-Command python).Source }

$model = Join-Path $Root "data\tts\qwen\Qwen3-TTS-12Hz-0.6B-CustomVoice"
if (-not (Test-Path (Join-Path $model "config.json"))) {
    Write-Host "Qwen3 model not found. Run: .\scripts\setup-tts.ps1 -DownloadQwen" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Qwen3 TTS host :8200..." -ForegroundColor Cyan
$env:PROJECT_ROOT = $Root
$env:QWEN3_TTS_MODEL = "data/tts/qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
Start-Process -FilePath $python -ArgumentList @(
    (Join-Path $Root "scripts\tts_host_server.py")
) -WorkingDirectory $Root -WindowStyle Hidden

$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    if (Test-PortListen 8200) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8200/health" -UseBasicParsing -TimeoutSec 5
            Write-Host "[OK] TTS host :8200 ($($r.Content))" -ForegroundColor Green
            exit 0
        } catch {
            # port open but model still loading
        }
    }
}

Write-Host "[WARN] TTS host :8200 not ready yet (model may still be loading)" -ForegroundColor Yellow
