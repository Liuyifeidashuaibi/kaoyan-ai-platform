# Setup Piper + Qwen3-TTS for en-learn read-aloud
# Usage: .\scripts\setup-tts.ps1
#        .\scripts\setup-tts.ps1 -DownloadQwen   # also download ~2.5GB Qwen3 model

param(
    [switch]$DownloadQwen
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "=== TTS Setup (Piper + Qwen3) ===" -ForegroundColor Cyan

$piperDir = Join-Path $Root "data\tts\piper"
$qwenDir = Join-Path $Root "data\tts\qwen"
New-Item -ItemType Directory -Path $piperDir -Force | Out-Null
New-Item -ItemType Directory -Path $qwenDir -Force | Out-Null

# --- Piper voices ---
$voices = @(
    "en_US-lessac-medium",
    "en_US-ryan-medium",
    "en_GB-alba-medium",
    "en_GB-northern_english_male-medium"
)

Write-Host ""
Write-Host "Checking Piper voice models..." -ForegroundColor Cyan
pip install -q piper-tts 2>$null

$missing = @()
foreach ($v in $voices) {
    $onnx = Join-Path $piperDir "$v.onnx"
    $json = Join-Path $piperDir "$v.onnx.json"
    if ((Test-Path $onnx) -and (Test-Path $json)) {
        Write-Host "[OK] $v" -ForegroundColor Green
    } else {
        $missing += $v
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Downloading Piper voices: $($missing -join ', ')" -ForegroundColor Cyan
    Push-Location $piperDir
    foreach ($v in $missing) {
        python -m piper.download_voices $v
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[FAIL] download $v" -ForegroundColor Red
            Pop-Location
            exit 1
        }
        Write-Host "[OK] downloaded $v" -ForegroundColor Green
    }
    Pop-Location
}

# --- Qwen3 venv + optional model ---
$qwenVenv = Join-Path $Root "data\tts\.venv"
$qwenPython = Join-Path $qwenVenv "Scripts\python.exe"
$qwenModel = Join-Path $qwenDir "Qwen3-TTS-12Hz-0.6B-CustomVoice"

if ($DownloadQwen) {
    Write-Host ""
    Write-Host "Setting up Qwen3-TTS Python env..." -ForegroundColor Cyan
    if (-not (Test-Path $qwenPython)) {
        python -m venv $qwenVenv
        & $qwenPython -m pip install -U pip
    }
    & $qwenPython -m pip install -U qwen-tts soundfile torch httpx fastapi uvicorn

    if (-not (Test-Path (Join-Path $qwenModel "config.json"))) {
        Write-Host "Downloading Qwen3-TTS 0.6B CustomVoice (~2.5GB, may take a while)..." -ForegroundColor Cyan
        & $qwenPython -m pip install -U modelscope
        & $qwenPython -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice', local_dir=r'$qwenModel')"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[WARN] ModelScope failed, trying huggingface-cli..." -ForegroundColor Yellow
            & $qwenPython -m pip install -U "huggingface_hub[cli]"
            & $qwenPython -m huggingface_hub.cli download Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice --local-dir $qwenModel
        }
    } else {
        Write-Host "[OK] Qwen3 model already at $qwenModel" -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "[SKIP] Qwen3 model download (use -DownloadQwen to fetch ~2.5GB)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Piper: ready (works in Docker backend after rebuild)" -ForegroundColor Green
Write-Host "Qwen3: set QWEN3_TTS_ENABLED=true in .env, then:" -ForegroundColor DarkGray
Write-Host "  1. .\scripts\setup-tts.ps1 -DownloadQwen" -ForegroundColor DarkGray
Write-Host "  2. .\scripts\start-tts-host.ps1" -ForegroundColor DarkGray
Write-Host "  3. docker compose up -d --build backend" -ForegroundColor DarkGray
