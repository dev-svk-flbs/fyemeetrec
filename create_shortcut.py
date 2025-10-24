#!/usr/bin/env python3
"""
Desktop Shortcut Creator for Audio Recording System
Creates desktop shortcuts for easy launching
"""

import os
import sys
from pathlib import Path

def create_windows_shortcut():
    """Create Windows desktop shortcut"""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        script_dir = Path(__file__).parent.absolute()
        batch_file = script_dir / "start_recording_system.bat"
        
        shortcut_path = Path(desktop) / "Audio Recording System.lnk"
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(batch_file)
        shortcut.WorkingDirectory = str(script_dir)
        shortcut.Description = "Audio Recording System with Global Hotkeys"
        shortcut.IconLocation = str(batch_file) + ",0"
        shortcut.save()
        
        print(f"✅ Desktop shortcut created: {shortcut_path}")
        return True
        
    except ImportError:
        print("⚠️ winshell or pywin32 not installed. Install with:")
        print("   pip install winshell pywin32")
        return False
    except Exception as e:
        print(f"❌ Failed to create shortcut: {e}")
        return False

def create_batch_shortcut():
    """Create a simple batch file on desktop"""
    try:
        script_dir = Path(__file__).parent.absolute()
        desktop = Path.home() / "Desktop"
        
        if not desktop.exists():
            desktop = Path.home() / "OneDrive" / "Desktop"
        
        if not desktop.exists():
            print("❌ Could not find Desktop folder")
            return False
        
        # Create shortcut that launches the dual system
        shortcut_content = f'''@echo off
cd /d "{script_dir}"
start "" "{script_dir}\\start_recording_system.bat"
'''
        
        shortcut_path = desktop / "Audio Recording System.bat"
        
        with open(shortcut_path, 'w') as f:
            f.write(shortcut_content)
        
        print(f"✅ Desktop shortcut created: {shortcut_path}")
        print("   This will start Flask + Hotkey Listener automatically")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create batch shortcut: {e}")
        return False

def main():
    """Main shortcut creation function"""
    print("🔗 Desktop Shortcut Creator")
    print("=" * 40)
    
    if os.name == 'nt':  # Windows
        print("Creating Windows desktop shortcut...")
        
        # Try advanced shortcut first
        if not create_windows_shortcut():
            print("Falling back to simple batch shortcut...")
            create_batch_shortcut()
    else:
        print("❌ Desktop shortcut creation only supported on Windows")
        print("💡 On Linux/Mac, create a launcher script manually")
    
    print("\n🎬 You can now launch the Audio Recording System from your desktop!")
    print("   • Double-click the desktop shortcut")
    print("   • Or run: python app.py")
    print("   • Or run: start_recording_system.bat")

if __name__ == "__main__":
    main()