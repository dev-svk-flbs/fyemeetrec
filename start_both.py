#!/usr/bin/env python3
"""
Simple launcher for Flask app + Independent Hotkey Listener
Starts Flask in background, then hotkey listener in foreground
"""

import os
import sys
import time
import subprocess
import signal
import requests
from pathlib import Path

def check_flask_ready(port=5000, timeout=30):
    """Check if Flask is ready to accept requests"""
    print(f" Waiting for Flask to be ready on port {port}...")
    
    for i in range(timeout):
        try:
            response = requests.get(f"http://localhost:{port}", timeout=2)
            if response.status_code == 200:
                print(" Flask is ready!")
                return True
        except:
            pass
        
        if i < timeout - 1:  # Don't sleep on last iteration
            time.sleep(1)
    
    print(" Flask may not be ready, but continuing anyway...")
    return False

def main():
    """Launch Flask app and hotkey listener"""
    print("=" * 60)
    print(" AUDIO RECORDING SYSTEM - SIMPLE LAUNCHER")
    print("=" * 60)
    print(" Flask: Background")
    print(" Hotkeys: Foreground") 
    print(" Press Ctrl+C to stop both")
    print("=" * 60)
    
    script_dir = Path(__file__).parent.absolute()
    
    # Check required files
    app_script = script_dir / "app.py"
    hotkey_script = script_dir / "hotkey_listener.py"
    
    if not app_script.exists():
        print(" app.py not found!")
        input("Press Enter to exit...")
        return
    
    if not hotkey_script.exists():
        print(" hotkey_listener.py not found!")
        input("Press Enter to exit...")
        return
    
    flask_process = None
    
    try:
        # Start Flask in background
        print(" Starting Flask app in background...")
        flask_process = subprocess.Popen(
            [sys.executable, str(app_script)],
            cwd=str(script_dir),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Wait for Flask to be ready
        check_flask_ready()
        
        print(f" Flask running (PID: {flask_process.pid})")
        print(" Starting hotkey listener...")
        print()
        print("Global Hotkeys Active:")
        print("   Start Recording: Ctrl+Shift+F9")
        print("   Stop Recording:  Ctrl+Shift+F10")
        print()
        
        # Start hotkey listener in foreground
        subprocess.call([sys.executable, str(hotkey_script)], cwd=str(script_dir))
        
    except KeyboardInterrupt:
        print("\n Stopping services...")
    except Exception as e:
        print(f" Error: {e}")
    finally:
        # Clean up Flask process
        if flask_process and flask_process.poll() is None:
            print(" Stopping Flask app...")
            try:
                if os.name == 'nt':  # Windows
                    flask_process.terminate()
                else:  # Linux/Mac
                    flask_process.send_signal(signal.SIGTERM)
                
                flask_process.wait(timeout=5)
                print(" Flask app stopped")
            except:
                print(" Flask app may still be running")
        
        print(" Launcher stopped")

if __name__ == "__main__":
    main()