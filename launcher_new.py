#!/usr/bin/env python3
"""
MINIMAL Launcher - Testing ONE Service at a Time
"""

import os
import sys
import time
import subprocess
from pathlib import Path

print(" MINIMAL LAUNCHER STARTING...")
print(f" Working directory: {Path(__file__).parent.absolute()}")
print(f" Python: {sys.executable}")
print("=" * 50)

# Test with just ONE service first
script_to_test = Path(__file__).parent / "hotkey_listener.py"

if not script_to_test.exists():
    print(f" Script not found: {script_to_test}")
    sys.exit(1)

print(f" Starting SINGLE SERVICE: {script_to_test.name}")

try:
    # Start just ONE process
    process = subprocess.Popen(
        [sys.executable, str(script_to_test)],
        cwd=str(Path(__file__).parent),
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    
    print(f" Service started with PID: {process.pid}")
    print("=" * 50)
    print(" CHECK PROCESS COUNT NOW!")
    print("Run this in another terminal:")
    print('Get-WmiObject Win32_Process -Filter "name=\'python.exe\'" | Select-Object ProcessId | Measure-Object | Select-Object Count')
    print("=" * 50)
    
    # Wait and monitor
    try:
        while True:
            if process.poll() is not None:
                print(f" Process terminated with exit code: {process.returncode}")
                break
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n Stopping...")
        process.terminate()
        process.wait()
        print(" Stopped")
        
except Exception as e:
    print(f" Error: {e}")

print(" Minimal launcher finished")