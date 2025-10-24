# Audio Recording System PowerShell Launcher
# Automatically starts Flask app and independent hotkey listener

param(
    [int]$Port = 5000,
    [int]$FlaskWaitTime = 5
)

$Host.UI.RawUI.WindowTitle = "Audio Recording System"

# Set UTF-8 encoding for Python
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONLEGACYWINDOWSSTDIO = "0"

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "🎬 AUDIO RECORDING SYSTEM LAUNCHER" -ForegroundColor Yellow
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host

# Check Python installation
try {
    $pythonVersion = python --version 2>$null
    Write-Host "✅ Python detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found! Please install Python 3.7+" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check required files
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appScript = Join-Path $scriptDir "app.py"
$hotkeyScript = Join-Path $scriptDir "hotkey_listener.py"

if (-not (Test-Path $appScript)) {
    Write-Host "❌ app.py not found in $scriptDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path $hotkeyScript)) {
    Write-Host "❌ hotkey_listener.py not found in $scriptDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "🌐 Web Interface: http://localhost:$Port" -ForegroundColor Cyan
Write-Host "🎹 Global Hotkeys:" -ForegroundColor Cyan
Write-Host "   📹 Start Recording: Ctrl+Shift+F9" -ForegroundColor White
Write-Host "   ⏹️ Stop Recording:  Ctrl+Shift+F10" -ForegroundColor White
Write-Host

try {
    # Change to script directory
    Set-Location $scriptDir
    
    # Start Flask application in background
    Write-Host "🚀 Starting Flask app..." -ForegroundColor Green
    $flaskProcess = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru -WindowStyle Hidden
    
    # Wait for Flask to start
    Write-Host "⏳ Waiting $FlaskWaitTime seconds for Flask to initialize..." -ForegroundColor Yellow
    Start-Sleep -Seconds $FlaskWaitTime
    
    # Verify Flask is running
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$Port" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        Write-Host "✅ Flask app is running" -ForegroundColor Green
    } catch {
        Write-Host "⚠️ Flask app may not be ready yet, but continuing..." -ForegroundColor Yellow
    }
    
    Write-Host
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host "✅ Flask app running in background (PID: $($flaskProcess.Id))" -ForegroundColor Green
    Write-Host "🎹 Starting hotkey listener..." -ForegroundColor Yellow
    Write-Host "💡 Press Ctrl+C to stop both services" -ForegroundColor Cyan
    Write-Host "=" * 60 -ForegroundColor Cyan
    Write-Host
    
    # Start hotkey listener in foreground
    python hotkey_listener.py
    
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
} finally {
    # Clean up Flask process
    if ($flaskProcess -and !$flaskProcess.HasExited) {
        Write-Host
        Write-Host "🛑 Stopping Flask app..." -ForegroundColor Yellow
        try {
            $flaskProcess.Kill()
            $flaskProcess.WaitForExit(5000)
            Write-Host "✅ Flask app stopped" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ Flask app may still be running" -ForegroundColor Yellow
        }
    }
    
    Write-Host
    Write-Host "Application stopped." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}