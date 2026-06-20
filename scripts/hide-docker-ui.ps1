# Hide Docker Desktop dashboard window (engine keeps running in tray)
# Usage: .\scripts\hide-docker-ui.ps1

$ErrorActionPreference = "SilentlyContinue"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class DockerUiHelper {
    public const uint WM_CLOSE = 0x0010;
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
}
"@

$closed = 0
Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.MainWindowHandle -ne [IntPtr]::Zero) {
        [void][DockerUiHelper]::PostMessage($_.MainWindowHandle, [DockerUiHelper]::WM_CLOSE, [IntPtr]::Zero, [IntPtr]::Zero)
        $closed++
    }
}

if ($closed -gt 0) {
    Write-Host "Docker Desktop window hidden to tray ($closed window(s))." -ForegroundColor Green
    Write-Host "Engine is still running. Use tray icon to reopen if needed." -ForegroundColor DarkGray
} else {
    Write-Host "No Docker Desktop window found (already hidden or not running)." -ForegroundColor Yellow
}
