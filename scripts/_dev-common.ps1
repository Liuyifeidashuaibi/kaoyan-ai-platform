# 本地开发脚本公共函数（被 start-*.ps1 / stop-dev.ps1 引用）

function Set-DevConsoleUtf8 {
    try {
        chcp 65001 | Out-Null
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    } catch {}
}

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

function Wait-PortListen {
    param(
        [int]$Port,
        [int]$WaitSec = 30,
        [string]$Label = "port $Port"
    )
    $deadline = (Get-Date).AddSeconds($WaitSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListen $Port) {
            Write-Host "[OK] $Label" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "[WARN] $Label not ready after ${WaitSec}s" -ForegroundColor Yellow
    return $false
}

function Start-RedisDev {
    param(
        [int]$WaitSec = 30,
        [switch]$Foreground
    )

    if (Test-PortListen 6379) {
        Write-Host "[OK] Redis :6379" -ForegroundColor Green
        return $true
    }

    $Root = Get-ProjectRoot
    $conf = Join-Path $Root "docker\redis.conf"
    if (-not (Test-Path $conf)) {
        Write-Host "[FAIL] Missing redis config: $conf" -ForegroundColor Red
        return $false
    }

    if (Get-Command docker -ErrorAction SilentlyContinue) {
        docker rm -f kaoyan-redis-dev 2>$null | Out-Null

        if ($Foreground) {
            Write-Host "Starting Redis :6379 (foreground — close window to stop)..." -ForegroundColor Green
            docker run --rm --name kaoyan-redis-dev `
                -p 6379:6379 `
                -v "${conf}:/usr/local/etc/redis/redis.conf:ro" `
                redis:7-alpine redis-server /usr/local/etc/redis/redis.conf
            return $LASTEXITCODE -eq 0
        }

        Write-Host "Starting Redis :6379 (background Docker)..." -ForegroundColor Cyan
        docker run -d --name kaoyan-redis-dev `
            -p 6379:6379 `
            -v "${conf}:/usr/local/etc/redis/redis.conf:ro" `
            redis:7-alpine redis-server /usr/local/etc/redis/redis.conf | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[FAIL] Could not start Redis container" -ForegroundColor Red
            return $false
        }
        return Wait-PortListen -Port 6379 -WaitSec $WaitSec -Label "Redis :6379"
    }

    if ($Foreground -and (Get-Command wsl -ErrorAction SilentlyContinue)) {
        Write-Host "Starting Redis :6379 via WSL..." -ForegroundColor Green
        wsl redis-server --port 6379 --maxmemory 512mb --maxmemory-policy allkeys-lru
        return $LASTEXITCODE -eq 0
    }

    if ($Foreground -and (Get-Command redis-server -ErrorAction SilentlyContinue)) {
        Write-Host "Starting Redis :6379 via local redis-server..." -ForegroundColor Green
        redis-server --port 6379 --maxmemory 512mb --maxmemory-policy allkeys-lru
        return $LASTEXITCODE -eq 0
    }

    Write-Host "[FAIL] Docker not available — install Docker Desktop or run start-redis.ps1" -ForegroundColor Red
    return $false
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
