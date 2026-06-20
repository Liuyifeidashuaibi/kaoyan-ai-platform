# Configure Docker Desktop: engine in background, no dashboard on startup
# Usage: .\scripts\configure-docker-background.ps1

$ErrorActionPreference = "Stop"

$settingsPath = Join-Path $env:APPDATA "Docker\settings-store.json"
if (-not (Test-Path $settingsPath)) {
    Write-Host "Docker settings not found: $settingsPath" -ForegroundColor Red
    Write-Host "Install and run Docker Desktop once first." -ForegroundColor Yellow
    exit 1
}

$backupPath = "$settingsPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
Copy-Item $settingsPath $backupPath
Write-Host "Backup: $backupPath" -ForegroundColor DarkGray

$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
$settings | Add-Member -NotePropertyName AutoStart -NotePropertyValue $true -Force
$settings | Add-Member -NotePropertyName OpenUIOnStartupDisabled -NotePropertyValue $true -Force
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8

Write-Host ""
Write-Host "Docker Desktop configured:" -ForegroundColor Green
Write-Host "  AutoStart = true              (start engine on Windows login)"
Write-Host "  OpenUIOnStartupDisabled = true (do not open dashboard on start)"
Write-Host ""
Write-Host "How to keep engine running without the client window:" -ForegroundColor Cyan
Write-Host "  - Click X on Docker Desktop window -> hides to tray, engine keeps running"
Write-Host "  - Do NOT choose Quit Docker Desktop in the tray menu (that stops the engine)"
Write-Host "  - Or run: .\scripts\hide-docker-ui.ps1"
Write-Host ""
