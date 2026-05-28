@echo off
:: Check if the server is already running on port 5000
netstat -ano | findstr ":5000" >nul 2>&1
if errorlevel 1 (
    echo Dashboard server is not running.
    echo Start the bot first using "Start PolyBot".
    timeout /t 3 /nobreak >nul
) else (
    start "" http://localhost:5000
)
