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
import os
from logging_config import setup_logging

# Setup logging
logger = setup_logging("hotkey_listener")

# Windows Toast Notifications
try:
    from plyer import notification
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    logger.warning("Install 'plyer' for toast notifications: pip install plyer")

# Flask app configuration
FLASK_URL = "http://localhost:5000"
HOTKEYS = {
    'record': 'ctrl+shift+f9',
    'stop': 'ctrl+shift+f10'
}

# Debounce mechanism
last_hotkey_time = {'start': 0, 'stop': 0}
DEBOUNCE_SECONDS = 2

def show_notification(title, message, timeout=3):
    """Show discrete Windows toast notification"""
    if NOTIFICATIONS_AVAILABLE:
        try:
            notification.notify(
                title=title,
                message=message,
                timeout=timeout,
                app_name="Recording System"
            )
        except Exception as e:
            logger.debug(f"Notification failed: {e}")

def check_flask_connection():
    """Check if Flask app is running"""
    try:
        response = requests.get(f"{FLASK_URL}/", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def trigger_start_recording():
    """Trigger recording start via hotkey"""
    try:
        # Debounce check
        current_time = time.time()
        if current_time - last_hotkey_time['start'] < DEBOUNCE_SECONDS:
            return
        last_hotkey_time['start'] = current_time
        
        logger.info(" Hotkey pressed: Starting recording...")
        
        # Check if Flask app is running
        if not check_flask_connection():
            logger.info(" Flask app not accessible")
            return
        
        # Generate recording title with timestamp
        title = f"Hotkey Recording {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # Send start request with longer timeout for slow startup
        logger.info(f" Sending POST request to {FLASK_URL}/start")
        response = requests.post(
            f"{FLASK_URL}/start",
            json={'title': title},
            headers={'Content-Type': 'application/json'},
            timeout=10  # Increased from 5 to 10 seconds
        )
        
        logger.info(f" Response: Status {response.status_code}, Headers: {dict(response.headers)}")
        logger.info(f" Response text: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code == 200:
            try:
                data = response.json()
                monitor = data.get('monitor', 'Unknown monitor')
                recording_id = data.get('recording_id', 'Unknown')
                
                # Discrete notification
                show_notification(
                    "Recording Started", 
                    f"Monitor: {monitor}\nID: {recording_id}",
                    timeout=4
                )
                
                logger.info(f" Recording started: {monitor}")
                logger.info(f" Recording ID: {recording_id}")
            except json.JSONDecodeError:
                show_notification("Recording Started", "Successfully initiated")
                logger.info(" Recording started (no JSON response)")
        elif response.status_code == 401 or response.status_code == 302:
            show_notification("Recording Failed", "Authentication required", timeout=5)
            logger.info(" Authentication required - Flask endpoint needs login")
            logger.info(" Try accessing via web interface first to authenticate")
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f'HTTP {response.status_code}')
            except json.JSONDecodeError:
                error_msg = f'HTTP {response.status_code} (no JSON response)'
            
            show_notification("Recording Failed", error_msg, timeout=5)
            logger.info(f" Failed to start recording: {error_msg}")
            
    except requests.exceptions.Timeout:
        show_notification("Recording Failed", "Request timeout", timeout=5)
        logger.info(" Request timeout - Flask app may be busy")
    except requests.exceptions.ConnectionError:
        show_notification("Recording Failed", "Connection failed", timeout=5)
        logger.info(" Connection failed - Is Flask app running?")
    except Exception as e:
        show_notification("Recording Failed", f"Error: {str(e)[:50]}", timeout=5)
        logger.info(f" Unexpected error: {e}")

def trigger_stop_recording():
    """Trigger recording stop via hotkey"""
    try:
        # Debounce check
        current_time = time.time()
        if current_time - last_hotkey_time['stop'] < DEBOUNCE_SECONDS:
            return
        last_hotkey_time['stop'] = current_time
        
        logger.info(" Hotkey pressed: Stopping recording...")
        
        # Check if Flask app is running
        if not check_flask_connection():
            logger.info(" Flask app not accessible")
            return
        
        # Send stop request with longer timeout
        logger.info(f" Sending POST request to {FLASK_URL}/stop")
        response = requests.post(
            f"{FLASK_URL}/stop",
            headers={'Content-Type': 'application/json'},
            timeout=10  # Increased from 5 to 10 seconds
        )
        
        logger.info(f" Response: Status {response.status_code}, Headers: {dict(response.headers)}")
        logger.info(f" Response text: {response.text[:200]}...")  # First 200 chars
        
        if response.status_code == 200:
            try:
                data = response.json()
                status = data.get('status', 'Unknown status')
                
                # Discrete notification
                show_notification(
                    "Recording Stopped", 
                    f"Status: {status}",
                    timeout=4
                )
                
                logger.info(f" Recording stopped: {status}")
            except json.JSONDecodeError:
                show_notification("Recording Stopped", "Successfully stopped")
                logger.info(" Recording stopped (no JSON response)")
        elif response.status_code == 401 or response.status_code == 302:
            show_notification("Stop Failed", "Authentication required", timeout=5)
            logger.info(" Authentication required - Flask endpoint needs login")
            logger.info(" Try accessing via web interface first to authenticate")
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('error', f'HTTP {response.status_code}')
            except json.JSONDecodeError:
                error_msg = f'HTTP {response.status_code} (no JSON response)'
            
            show_notification("Stop Failed", error_msg, timeout=5)
            logger.info(f" Failed to stop recording: {error_msg}")
            
    except requests.exceptions.Timeout:
        show_notification("Stop Failed", "Request timeout", timeout=5)
        logger.info(" Request timeout - Flask app may be busy")
    except requests.exceptions.ConnectionError:
        show_notification("Stop Failed", "Connection failed", timeout=5)
        logger.info(" Connection failed - Is Flask app running?")
    except Exception as e:
        show_notification("Stop Failed", f"Error: {str(e)[:50]}", timeout=5)
        logger.info(f" Unexpected error: {e}")

def main():
    """Main hotkey listener"""
    logger.info("=" * 60)
    logger.info("HOTKEY LISTENER STARTING")
    logger.info("=" * 60)
    logger.info(f"Flask URL: {FLASK_URL}")
    logger.info(f"Start Recording: {HOTKEYS['record']}")
    logger.info(f"Stop Recording:  {HOTKEYS['stop']}")
    logger.info("=" * 60)
    
    # Check initial Flask connection
    if check_flask_connection():
        logger.info("Flask app detected on localhost:5000")
    else:
        logger.warning("Flask app not detected - start your Flask app first")
    
    logger.info("Listening for hotkeys... (Press Ctrl+C to exit)")
    
    try:
        # Register hotkeys - suppress=False to avoid interfering with other apps
        keyboard.add_hotkey(HOTKEYS['record'], trigger_start_recording, suppress=False)
        keyboard.add_hotkey(HOTKEYS['stop'], trigger_stop_recording, suppress=False)
        
        logger.info("Hotkeys registered successfully")
        
        # Keep the script running
        keyboard.wait()
        
    except KeyboardInterrupt:
        logger.info("Hotkey listener stopped by user")
        # Clean up hotkeys
        keyboard.unhook_all_hotkeys()
        logger.info("Hotkeys cleaned up")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        # Clean up hotkeys on error
        keyboard.unhook_all_hotkeys()
        logger.info("Hotkeys cleaned up after error")
        sys.exit(1)

if __name__ == "__main__":
    main()
