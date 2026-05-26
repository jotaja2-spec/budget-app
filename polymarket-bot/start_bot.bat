@echo off
title PolyBot — Starting...
cd /d "%~dp0"

:: Check if .env exists
if not exist ".env" (
    echo ERROR: .env file not found.
    echo Copy .env.template to .env and fill in your values first.
    pause
    exit /b 1
)

:: Start the dashboard server silently in the background
echo Starting dashboard server...
start "" /min pythonw server.py

:: Small delay so server is ready
timeout /t 2 /nobreak >nul

:: Open browser to dashboard
start "" http://localhost:5000

:: Start the bot in this window
title PolyBot — Running
python main.py

pause
