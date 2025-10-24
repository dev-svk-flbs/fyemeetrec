@echo off
title Audio Recording System
cd /d "%~dp0"

REM Set UTF-8 encoding for Python
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=0

echo.
echo ====================================================
echo    AUDIO RECORDING SYSTEM - AUTO LAUNCHER
echo ====================================================
echo.
echo Starting Flask app and hotkey listener...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Start Flask app in background
echo Starting Flask app...
start /B python app.py

REM Wait for Flask to start up
echo Waiting for Flask to initialize...
timeout /t 5 /nobreak >nul

REM Start hotkey listener in foreground
echo Starting hotkey listener...
echo.
echo ====================================================
echo Flask app running in background
echo Hotkey listener running in foreground
echo.
echo Global Hotkeys:
echo   Start Recording: Ctrl+Shift+F9
echo   Stop Recording:  Ctrl+Shift+F10
echo.
echo Press Ctrl+C to stop both services
echo ====================================================
echo.

python hotkey_listener.py

echo.
echo Hotkey listener stopped.
echo Flask app may still be running in background.
pause