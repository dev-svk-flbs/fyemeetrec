#!/usr/bin/env python3
"""
Factory Reset Script for Audio Recording System
Run this script to completely wipe all data and start fresh
"""

import os
import shutil
import sqlite3
from pathlib import Path
import sys

def print_banner():
    """Print factory reset banner"""
    print("=" * 60)
    print(" FACTORY RESET - AUDIO RECORDING SYSTEM")
    print("=" * 60)
    print("  WARNING: This will permanently delete ALL data!")
    print("   • All recordings and transcripts")
    print("   • All users and authentication data")
    print("   • All settings and configurations")
    print("   • All logs and cache files")
    print("   • Complete database wipe")
    print("=" * 60)

def confirm_reset():
    """Get user confirmation for factory reset"""
    print("\n CONFIRMATION REQUIRED ")
    response = input("Type 'FACTORY RESET' (exactly) to proceed: ")
    
    if response != "FACTORY RESET":
        print(" Factory reset cancelled.")
        return False
    
    print("\n  FINAL WARNING: This action cannot be undone!")
    final = input("Type 'YES DELETE EVERYTHING' to confirm: ")
    
    if final != "YES DELETE EVERYTHING":
        print(" Factory reset cancelled.")
        return False
    
    return True

def factory_reset():
    """Perform complete factory reset"""
    script_dir = Path(__file__).parent.absolute()
    
    print("\n Starting factory reset...")
    
    # 1. Remove recordings directory
    recordings_path = script_dir / "recordings"
    if recordings_path.exists():
        try:
            shutil.rmtree(recordings_path)
            print(" Deleted recordings directory")
        except Exception as e:
            print(f" Failed to delete recordings: {e}")
    
    # Recreate empty recordings directory
    recordings_path.mkdir(exist_ok=True)
    print(" Recreated empty recordings directory")
    
    # 2. Remove logs directory
    logs_path = script_dir / "logs"
    if logs_path.exists():
        try:
            shutil.rmtree(logs_path)
            print(" Deleted logs directory")
        except Exception as e:
            print(f" Failed to delete logs: {e}")
    
    # Recreate empty logs directory
    logs_path.mkdir(exist_ok=True)
    print(" Recreated empty logs directory")
    
    # 3. Remove database
    db_path = script_dir / "recordings.db"
    if db_path.exists():
        try:
            os.remove(db_path)
            print(" Deleted database file")
        except Exception as e:
            print(f" Failed to delete database: {e}")
    
    # 4. Remove instance directory (Flask instance folder)
    instance_path = script_dir / "instance"
    if instance_path.exists():
        try:
            shutil.rmtree(instance_path)
            print(" Deleted instance directory")
        except Exception as e:
            print(f" Failed to delete instance directory: {e}")
    
    # 5. Remove settings file
    settings_path = script_dir / "settings.config"
    if settings_path.exists():
        try:
            os.remove(settings_path)
            print(" Deleted settings configuration")
        except Exception as e:
            print(f" Failed to delete settings: {e}")
    
    # 6. Remove Python cache
    pycache_path = script_dir / "__pycache__"
    if pycache_path.exists():
        try:
            shutil.rmtree(pycache_path)
            print(" Cleared Python cache")
        except Exception as e:
            print(f" Failed to clear cache: {e}")
    
    # 7. Remove any .pyc files
    for pyc_file in script_dir.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            print(f" Deleted {pyc_file.name}")
        except Exception as e:
            print(f" Failed to delete {pyc_file.name}: {e}")
    
    print("\n FACTORY RESET COMPLETED!")
    print("=" * 60)
    print(" All data has been permanently deleted")
    print(" System has been reset to initial state")
    print(" You can now restart the application")
    print("=" * 60)
    print("\n To restart the application:")
    print("   1. Run: python app.py")
    print("   2. Visit: http://localhost:5000")
    print("   3. Complete the setup process")
    print("\n The application will create a fresh setup page")

def main():
    """Main factory reset function"""
    print_banner()
    
    if not confirm_reset():
        sys.exit(0)
    
    try:
        factory_reset()
    except Exception as e:
        print(f"\n Factory reset failed: {e}")
        print(" You may need to manually delete files and restart")
        sys.exit(1)

if __name__ == "__main__":
    main()