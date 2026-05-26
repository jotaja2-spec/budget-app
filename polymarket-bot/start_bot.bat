@echo off
title Polymarket Trading — Starting...
cd /d "%~dp0"

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Copy .env.template to .env and fill in your values first.
    pause
    exit /b 1
)

echo Starting Polymarket Trading...

:: Dashboard server (background, minimized)
start "" /min pythonw server.py

:: Wait for server to be ready
timeout /t 2 /nobreak >nul

:: System tray icon (background)
start "" /min pythonw tray.py

:: Open browser dashboard
start "" http://localhost:5000

:: Run the trading bot (this window stays open — close it to stop the bot)
title Polymarket Trading — Running
python main.py

pause
