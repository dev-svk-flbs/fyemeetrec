#!/usr/bin/env python3
"""
Reset Settings for Testing
Removes the settings.config file to test the new first-time setup flow
"""

import os
from pathlib import Path

def reset_settings():
    """Remove settings file to test first-time setup"""
    
    settings_file = Path(__file__).parent / "settings.config"
    
    if settings_file.exists():
        try:
            os.remove(settings_file)
            print("✅ Settings file removed successfully")
            print(f"📁 Removed: {settings_file}")
            print("\n💡 Now you can test the new monitor detection flow:")
            print("   1. Start the Flask app: python app.py")
            print("   2. Go to Settings page")
            print("   3. Click 'Detect Monitors' button")
            print("   4. Arrange monitors by dragging")
            print("   5. Click 'Save Arrangement'")
        except Exception as e:
            print(f"❌ Error removing settings file: {e}")
    else:
        print("ℹ️ No settings file found - already in first-time setup state")
        print(f"📁 Expected location: {settings_file}")

if __name__ == "__main__":
    reset_settings()