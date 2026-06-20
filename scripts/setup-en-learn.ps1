# One-time setup for en-learn / word_dict / tts modules
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== En-Learn Module Setup ===" -ForegroundColor Cyan

# 1. Create data dirs
$dirs = @(
    "data/ecdict",
    "data/tts/piper"
)
foreach ($d in $dirs) {
    $p = Join-Path $Root $d
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Path $p -Force | Out-Null
        Write-Host "[OK] Created $d" -ForegroundColor Green
    }
}

# 2. Init word_lib from ECDICT (stardict.db / ecdict.csv) or core fallback
Write-Host ""
Write-Host "Ensuring word_lib.db ..." -ForegroundColor Cyan
python scripts/ensure_word_lib.py
if ($LASTEXITCODE -ne 0) { exit 1 }

# 4. Check Ollama
Write-Host ""
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "[OK] Ollama :11434" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Ollama not running - correction/translation AI needs it" -ForegroundColor Yellow
}

# 5. Check Translator
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8100/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
    Write-Host "[OK] Translator :8100" -ForegroundColor Green
} catch {
    Write-Host "[WARN] Translator not running - run .\scripts\start-translator.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Setup done. Start platform: .\scripts\start-all.ps1" -ForegroundColor Green
Write-Host "Docs: docs/modules/EN_LEARN_TTS_WORDDICT.md" -ForegroundColor DarkGray
