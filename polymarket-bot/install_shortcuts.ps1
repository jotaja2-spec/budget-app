# install_shortcuts.ps1
# Run this ONCE from PowerShell to create desktop shortcuts.
# Right-click the file → "Run with PowerShell"

$botDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath("Desktop")
$wsh     = New-Object -ComObject WScript.Shell

# --- Find Python icon ---
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $pythonExe) {
    $pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
}
$pythonIcon = if (Test-Path $pythonExe) { "$pythonExe,0" } else { "shell32.dll,1" }

# --- Shortcut 1: Start PolyBot ---
$s1 = $wsh.CreateShortcut("$desktop\Start PolyBot.lnk")
$s1.TargetPath      = "$botDir\start_bot.bat"
$s1.WorkingDirectory = $botDir
$s1.WindowStyle     = 1   # normal window
$s1.IconLocation    = $pythonIcon
$s1.Description     = "Start Polymarket Weather Bot and Dashboard"
$s1.Save()
Write-Host "Created: $desktop\Start PolyBot.lnk" -ForegroundColor Green

# --- Shortcut 2: PolyBot Dashboard ---
$s2 = $wsh.CreateShortcut("$desktop\PolyBot Dashboard.lnk")
$s2.TargetPath      = "$botDir\open_dashboard.bat"
$s2.WorkingDirectory = $botDir
$s2.WindowStyle     = 7   # minimized (flashes briefly then disappears)
$s2.IconLocation    = "shell32.dll,14"  # globe/browser icon
$s2.Description     = "Open PolyBot Dashboard in browser"
$s2.Save()
Write-Host "Created: $desktop\PolyBot Dashboard.lnk" -ForegroundColor Green

Write-Host ""
Write-Host "Done! Two shortcuts added to your desktop:" -ForegroundColor Cyan
Write-Host "  Start PolyBot       — launches the bot + opens dashboard"
Write-Host "  PolyBot Dashboard   — opens dashboard (bot must already be running)"
