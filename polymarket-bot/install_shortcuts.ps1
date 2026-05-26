# install_shortcuts.ps1
# Run this ONCE from PowerShell to create desktop shortcuts.
# Right-click the file → "Run with PowerShell"

$botDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$wsh     = New-Object -ComObject WScript.Shell

# --- Find Python icon ---
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $pythonExe) {
    $pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
}
$pythonIcon = if (Test-Path $pythonExe) { "$pythonExe,0" } else { "shell32.dll,1" }

# --- Shortcut 1: Start Polymarket Trading ---
$s1 = $wsh.CreateShortcut("$desktop\Start Polymarket Trading.lnk")
$s1.TargetPath       = "$botDir\start_bot.bat"
$s1.WorkingDirectory = $botDir
$s1.WindowStyle      = 1
$s1.IconLocation     = $pythonIcon
$s1.Description      = "Start Polymarket Trading bot, dashboard, and tray icon"
$s1.Save()
Write-Host "Created: Start Polymarket Trading" -ForegroundColor Green

# --- Shortcut 2: Polymarket Trading App (desktop window) ---
$s2 = $wsh.CreateShortcut("$desktop\Polymarket Trading App.lnk")
$s2.TargetPath       = "$botDir\open_app.bat"
$s2.WorkingDirectory = $botDir
$s2.WindowStyle      = 7
$s2.IconLocation     = "shell32.dll,14"
$s2.Description      = "Open Polymarket Trading in a desktop app window"
$s2.Save()
Write-Host "Created: Polymarket Trading App" -ForegroundColor Green

# --- Shortcut 3: Polymarket Trading Dashboard (browser) ---
$s3 = $wsh.CreateShortcut("$desktop\Polymarket Dashboard.lnk")
$s3.TargetPath       = "$botDir\open_dashboard.bat"
$s3.WorkingDirectory = $botDir
$s3.WindowStyle      = 7
$s3.IconLocation     = "shell32.dll,14"
$s3.Description      = "Open Polymarket Trading dashboard in browser"
$s3.Save()
Write-Host "Created: Polymarket Dashboard" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Three shortcuts added to your desktop:" -ForegroundColor Cyan
Write-Host "  Start Polymarket Trading    — launches bot + tray icon + browser dashboard"
Write-Host "  Polymarket Trading App      — opens desktop app window (bot must be running)"
Write-Host "  Polymarket Dashboard        — opens browser dashboard (bot must be running)"
