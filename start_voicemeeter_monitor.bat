@echo off
echo Starting VoiceMeeter Bluetooth Auto-Restart Monitor...
echo.
echo This monitor will:
echo - Detect Bluetooth headset connections/disconnections
echo - Automatically restart VoiceMeeter audio engine (Ctrl+R)
echo - Keep VoiceMeeter audio routing fresh and responsive
echo.
echo Press Ctrl+C to stop the monitor
echo.
pause
echo Starting monitor...
python voicemeeter_bluetooth_monitor.py
pause