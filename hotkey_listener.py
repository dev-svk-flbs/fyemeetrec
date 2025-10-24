#!/usr/bin/env python3
"""
Global Hotkey Listener for Recording Control
Left Ctrl + Alt + Shift + R = Start Recording
Left Ctrl + Alt + Shift + S = Stop Recording
"""

import keyboard
import requests
import time
import json
from datetime import datetime
import sys

# Flask app configuration
FLASK_URL = "http://localhost:5000"
HOTKEYS = {
    'record': 'ctrl+shift+f9',
    'stop': 'ctrl+shift+f10'
}

# Debounce mechanism
last_hotkey_time = {'start': 0, 'stop': 0}
DEBOUNCE_SECONDS = 2

def print_status(message, emoji="🎹"):
    """Print status with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"{timestamp} | {emoji} {message}")

def check_flask_connection():
    """Check if Flask app is running"""
    try:
        response = requests.get(f"{FLASK_URL}/", timeout=2)
        return response.status_code == 200
    except Exception as e:
        print_status(f"🔍 Flask check failed: {e}")
        return False

def trigger_start_recording():
    """Trigger recording start via hotkey"""
    try:
        # Debounce check
        current_time = time.time()
        if current_time - last_hotkey_time['start'] < DEBOUNCE_SECONDS:
            return
        last_hotkey_time['start'] = current_time
        
        print_status("🎬 Hotkey pressed: Starting recording...")
        
        # Check if Flask app is running
        if not check_flask_connection():
            print_status("❌ Flask app not accessible", "⚠️")
            return
        
        # Generate recording title with timestamp
        title = f"Hotkey Recording {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Send start request
        print_status(f"📤 Sending POST request to {FLASK_URL}/start")
        response = requests.post(
            f"{FLASK_URL}/start",
            json={'title': title},
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        print_status(f"📥 Response: Status {response.status_code}, Headers: {dict(response.headers)}")
        print_status(f"📝 Response text: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code == 200:
            try:
                data = response.json()
                print_status(f"✅ Recording started: {data.get('monitor', 'Unknown monitor')}")
                print_status(f"📁 Recording ID: {data.get('recording_id', 'Unknown')}")
            except json.JSONDecodeError:
                print_status("✅ Recording started (no JSON response)")
        elif response.status_code == 401 or response.status_code == 302:
            print_status("❌ Authentication required - Flask endpoint needs login", "🔐")
            print_status("💡 Try accessing via web interface first to authenticate", "💡")
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f'HTTP {response.status_code}')
            except json.JSONDecodeError:
                error_msg = f'HTTP {response.status_code} (no JSON response)'
            print_status(f"❌ Failed to start recording: {error_msg}", "⚠️")
            
    except requests.exceptions.Timeout:
        print_status("❌ Request timeout - Flask app may be busy", "⏰")
    except requests.exceptions.ConnectionError:
        print_status("❌ Connection failed - Is Flask app running?", "🔌")
    except Exception as e:
        print_status(f"❌ Unexpected error: {e}", "💥")

def trigger_stop_recording():
    """Trigger recording stop via hotkey"""
    try:
        # Debounce check
        current_time = time.time()
        if current_time - last_hotkey_time['stop'] < DEBOUNCE_SECONDS:
            return
        last_hotkey_time['stop'] = current_time
        
        print_status("⏹️ Hotkey pressed: Stopping recording...")
        
        # Check if Flask app is running
        if not check_flask_connection():
            print_status("❌ Flask app not accessible", "⚠️")
            return
        
        # Send stop request
        print_status(f"📤 Sending POST request to {FLASK_URL}/stop")
        response = requests.post(
            f"{FLASK_URL}/stop",
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        
        print_status(f"📥 Response: Status {response.status_code}, Headers: {dict(response.headers)}")
        print_status(f"📝 Response text: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code == 200:
            try:
                data = response.json()
                print_status(f"✅ Recording stopped: {data.get('status', 'Unknown status')}")
            except json.JSONDecodeError:
                print_status("✅ Recording stopped (no JSON response)")
        elif response.status_code == 401 or response.status_code == 302:
            print_status("❌ Authentication required - Flask endpoint needs login", "🔐")
            print_status("💡 Try accessing via web interface first to authenticate", "💡")
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f'HTTP {response.status_code}')
            except json.JSONDecodeError:
                error_msg = f'HTTP {response.status_code} (no JSON response)'
            print_status(f"❌ Failed to stop recording: {error_msg}", "⚠️")
            
    except requests.exceptions.Timeout:
        print_status("❌ Request timeout - Flask app may be busy", "⏰")
    except requests.exceptions.ConnectionError:
        print_status("❌ Connection failed - Is Flask app running?", "🔌")
    except Exception as e:
        print_status(f"❌ Unexpected error: {e}", "💥")

def main():
    """Main hotkey listener"""
    print("🎹 Global Recording Hotkeys")
    print("=" * 50)
    print(f"📹 Start Recording: {HOTKEYS['record'].title()}")
    print(f"⏹️ Stop Recording:  {HOTKEYS['stop'].title()}")
    print("=" * 50)
    
    # Check initial Flask connection
    if check_flask_connection():
        print_status("✅ Flask app detected on localhost:5000")
    else:
        print_status("⚠️ Flask app not detected - start your Flask app first", "⚠️")
    
    print_status("🎧 Listening for hotkeys... (Press Ctrl+C to exit)")
    
    try:
        # Register hotkeys - removed suppress=True to avoid interfering with other apps
        keyboard.add_hotkey(HOTKEYS['record'], trigger_start_recording, suppress=False)
        keyboard.add_hotkey(HOTKEYS['stop'], trigger_stop_recording, suppress=False)
        
        print_status("🔥 Hotkeys registered successfully")
        
        # Keep the script running
        keyboard.wait()
        
    except KeyboardInterrupt:
        print_status("👋 Hotkey listener stopped by user")
        # Clean up hotkeys
        keyboard.unhook_all_hotkeys()
        print_status("🧹 Hotkeys cleaned up")
    except Exception as e:
        print_status(f"❌ Fatal error: {e}", "💥")
        # Clean up hotkeys on error
        keyboard.unhook_all_hotkeys()
        print_status("🧹 Hotkeys cleaned up after error")
        sys.exit(1)

if __name__ == "__main__":
    main()