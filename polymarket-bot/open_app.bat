@echo off
title Polymarket Trading — Desktop App
cd /d "%~dp0"

:: Check if server is running (port 5000 in use)
netstat -an 2>nul | find "0.0.0.0:5000" >nul
if errorlevel 1 (
    echo Bot server is not running.
    echo Please start the bot first using "Start Polymarket Trading" on your desktop.
    timeout /t 4
    exit /b 1
)

pythonw app.py
