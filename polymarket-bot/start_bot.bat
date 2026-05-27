@echo off
title Polymarket Trading — Starting...
cd /d "%~dp0"
set PYTHON=C:\Users\joshj\AppData\Local\Programs\Python\Python312\python.exe

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Copy .env.template to .env and fill in your values first.
    pause
    exit /b 1
)

echo Starting Polymarket Trading in background...

:: Dashboard server (background, minimized)
start "" /min "%PYTHON%" server.py

:: Wait for server to be ready
timeout /t 2 /nobreak >nul

:: System tray icon (background)
start "" /min "%PYTHON%" tray.py

:: Wait a moment then start bot fully hidden
timeout /t 1 /nobreak >nul

:: Trading bot (background, minimized — right-click tray icon to open dashboard)
start "" /min "%PYTHON%" main.py

echo.
echo Polymarket Trading is running in the background.
echo Check your system tray (bottom-right) for the hexagon icon.
echo Right-click the icon to open the dashboard.
timeout /t 4 /nobreak >nul
