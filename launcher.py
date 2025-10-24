#!/usr/bin/env python3
"""
Standalone Launcher for Audio Recording System with Hotkeys
Launches both Flask app and hotkey listener automatically
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("🎬 AUDIO RECORDING SYSTEM LAUNCHER")
    print("=" * 60)
    print("🌐 Flask Web App: http://localhost:5000")
    print("🎹 Global Hotkeys:")
    print("   📹 Start Recording: Ctrl+Shift+F9")
    print("   ⏹️ Stop Recording:  Ctrl+Shift+F10")
    print("=" * 60)

def launch_application():
    """Launch both Flask app and hotkey listener"""
    script_dir = Path(__file__).parent.absolute()
    
    # Check if required files exist
    app_script = script_dir / "app.py"
    hotkey_script = script_dir / "hotkey_listener.py"
    
    if not app_script.exists():
        print("❌ app.py not found!")
        return False
    
    if not hotkey_script.exists():
        print("⚠️ hotkey_listener.py not found - hotkeys will be disabled")
    
    processes = []
    
    try:
        print("🚀 Starting Flask application...")
        
        # Start Flask app
        app_process = subprocess.Popen(
            [sys.executable, str(app_script)],
            cwd=str(script_dir)
        )
        processes.append(("Flask App", app_process))
        
        # Wait a bit for Flask to start
        time.sleep(3)
        
        print("✅ Flask application started")
        print(f"🌐 Web interface available at: http://localhost:5000")
        print("\n🎹 Hotkeys are automatically managed by the Flask app")
        print("\n📋 Application is ready!")
        print("   • Visit http://localhost:5000 to use the web interface")
        print("   • Use Ctrl+Shift+F9 to start recording")
        print("   • Use Ctrl+Shift+F10 to stop recording")
        print("   • Press Ctrl+C here to stop everything")
        
        # Wait for processes
        try:
            for name, process in processes:
                process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        return False
    
    finally:
        # Clean up processes
        print("🧹 Cleaning up...")
        for name, process in processes:
            if process.poll() is None:
                try:
                    print(f"🛑 Stopping {name}...")
                    if os.name == 'nt':  # Windows
                        process.terminate()
                    else:  # Linux/Mac
                        process.send_signal(signal.SIGTERM)
                    
                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=5)
                        print(f"✅ {name} stopped")
                    except subprocess.TimeoutExpired:
                        print(f"🔨 Force stopping {name}...")
                        process.kill()
                        process.wait()
                        print(f"✅ {name} force stopped")
                        
                except Exception as e:
                    print(f"❌ Error stopping {name}: {e}")
    
    return True

def main():
    """Main launcher function"""
    print_banner()
    
    try:
        success = launch_application()
        if not success:
            print("\n❌ Failed to launch application")
            input("Press Enter to exit...")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Launcher stopped by user")
    except Exception as e:
        print(f"\n❌ Launcher error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()