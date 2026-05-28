@echo off
title Polymarket Trading — Starting...
cd /d "%~dp0"
set PYTHON=C:\Users\joshj\AppData\Local\Programs\Python\Python312\python.exe
set PYTHONW=C:\Users\joshj\AppData\Local\Programs\Python\Python312\pythonw.exe

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Copy .env.template to .env and fill in your values first.
    pause
    exit /b 1
)

:: Dashboard server — completely silent, no window
start "" "%PYTHONW%" server.py

:: Wait for server to be ready
timeout /t 2 /nobreak >nul

:: System tray icon — completely silent, no window
start "" "%PYTHONW%" tray.py

:: Wait a moment
timeout /t 1 /nobreak >nul

:: Trading bot — completely silent, no window
start "" "%PYTHONW%" main.py

:: Brief confirmation then this window closes itself
echo Polymarket Trading started. Check your system tray.
timeout /t 3 /nobreak >nul
