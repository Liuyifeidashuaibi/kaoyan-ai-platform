# 本地开发脚本公共函数（被 start-*.ps1 / stop-dev.ps1 引用）

function Get-ProjectRoot {
    return Split-Path -Parent $PSScriptRoot
}

function Import-ProjectDotEnv {
    param([string]$Root = (Get-ProjectRoot))
    foreach ($name in @(".env", ".env.local")) {
        $path = Join-Path $Root $name
        if (-not (Test-Path $path)) { continue }
        Get-Content $path | ForEach-Object {
            $line = $_.Trim()
            if (-not $line -or $line.StartsWith("#")) { return }
            $eq = $line.IndexOf("=")
            if ($eq -lt 1) { return }
            $key = $line.Substring(0, $eq).Trim()
            $val = $line.Substring($eq + 1).Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            Set-Item -Path "Env:$key" -Value $val
        }
    }
}

function Test-PortListen {
    param([int]$Port)
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Get-BackendVenvPython {
    $Root = Get-ProjectRoot
    $Backend = Join-Path $Root "backend"
    $VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating backend\.venv and installing deps..." -ForegroundColor Yellow
        Set-Location $Backend
        python -m venv .venv
        & ".\.venv\Scripts\pip.exe" install -r requirements.txt
    }
    return $VenvPython
}

function Get-TranslatorRoot {
    Import-ProjectDotEnv | Out-Null
    if ($env:TRANSLATOR_ROOT -and (Test-Path $env:TRANSLATOR_ROOT)) {
        return $env:TRANSLATOR_ROOT
    }
    return "E:\Tanslator\translatorai"
}

function Stop-PortProcess {
    param([int]$Port, [string]$Label = "port $Port")
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conn) {
        Write-Host "[skip] $Label not listening" -ForegroundColor DarkGray
        return
    }
    $pid = $conn.OwningProcess | Select-Object -First 1
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Write-Host "[stopped] $Label (PID $pid)" -ForegroundColor Green
}

function Start-InNewDevWindow {
    param(
        [string]$Title,
        [string]$ScriptPath,
        [string[]]$ScriptArgs = @()
    )
    $argList = @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", $ScriptPath) + $ScriptArgs
    Start-Process powershell -ArgumentList $argList -WindowStyle Normal
    Write-Host "Opened window: $Title" -ForegroundColor Green
}

function Test-OllamaReady {
    param([int]$TimeoutSec = 3)
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec $TimeoutSec | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Start-OllamaIfNeeded {
    param([int]$WaitSec = 30)
    if (Test-OllamaReady) {
        Write-Host "[OK] Ollama :11434" -ForegroundColor Green
        return $true
    }
    Write-Host "Starting Ollama..." -ForegroundColor Cyan
    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Ollama\Ollama.exe",
        "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe",
        "C:\Program Files\Ollama\ollama.exe"
    )) {
        if (Test-Path $p) {
            Start-Process $p -WindowStyle Minimized
            break
        }
    }
    $deadline = (Get-Date).AddSeconds($WaitSec)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-OllamaReady) {
            Write-Host "[OK] Ollama :11434" -ForegroundColor Green
            return $true
        }
    }
    Write-Host "[WARN] Ollama not ready - translation may fail" -ForegroundColor Yellow
    return $false
}

function Ensure-BackendPiper {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return }
    $running = docker ps --filter "name=kaoyan-backend" --filter "status=running" -q 2>$null
    if (-not $running) { return }
    docker exec kaoyan-backend python -c "import piper" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Host "Installing piper-tts in backend container..." -ForegroundColor Cyan
    docker exec kaoyan-backend pip install -q piper-tts numpy -i https://pypi.tuna.tsinghua.edu.cn/simple 2>$null
}

function Start-TtsHostBackground {
    Import-ProjectDotEnv | Out-Null
    if ($env:QWEN3_TTS_ENABLED -ne "true") {
        return $false
    }
    if (Test-PortListen 8200) {
        Write-Host "[OK] TTS host :8200" -ForegroundColor Green
        return $true
    }
    $script = Join-Path (Get-ProjectRoot) "scripts\start-tts-host.ps1"
    if (-not (Test-Path $script)) { return $false }
    & $script
    return $LASTEXITCODE -eq 0
}

function Start-TranslatorBackground {
    param([int]$WaitSec = 45)
    if (Test-PortListen 8100) {
        Write-Host "[OK] Translator :8100" -ForegroundColor Green
        return $true
    }
    Import-ProjectDotEnv | Out-Null
    $root = Get-TranslatorRoot
    $main = Join-Path $root "src\translator\server\main.py"
    if (-not (Test-Path $main)) {
        Write-Host "[WARN] Translator project not found: $root" -ForegroundColor Yellow
        return $false
    }
    Write-Host "Starting Translator :8100 (background)..." -ForegroundColor Cyan
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $python) {
        Write-Host "[WARN] python not found for Translator" -ForegroundColor Yellow
        return $false
    }
    Start-Process -FilePath $python -ArgumentList "-m", "translator.server.main" -WorkingDirectory $root -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($WaitSec)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-PortListen 8100) {
            Write-Host "[OK] Translator :8100" -ForegroundColor Green
            return $true
        }
    }
    Write-Host "[WARN] Translator :8100 not ready yet (may still be loading models)" -ForegroundColor Yellow
    return $false
}
