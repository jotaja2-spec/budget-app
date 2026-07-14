@echo off
title Polymarket Trading — Stopping...
cd /d "%~dp0"
set PYTHON=C:\Users\joshj\AppData\Local\Programs\Python\Python312\python.exe

echo Stopping all Polymarket Trading processes...

:: Kill bot (main.py)
if exist "bot.pid" (
    set /p BOT_PID=<bot.pid
    taskkill /PID %BOT_PID% /F >nul 2>&1
    del bot.pid >nul 2>&1
    echo   Bot stopped.
)

:: Kill tray (tray.py)
if exist "tray.pid" (
    set /p TRAY_PID=<tray.pid
    taskkill /PID %TRAY_PID% /F >nul 2>&1
    del tray.pid >nul 2>&1
    echo   Tray stopped.
)

:: Kill server, app, and any remaining python processes for this bot
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5000"') do (
    taskkill /PID %%p /F >nul 2>&1
)
echo   Dashboard stopped.

:: Kill any app.py (pywebview) windows
taskkill /FI "WINDOWTITLE eq Polymarket Trading*" /F >nul 2>&1

echo.
echo All Polymarket Trading processes stopped.
timeout /t 3 /nobreak >nul
