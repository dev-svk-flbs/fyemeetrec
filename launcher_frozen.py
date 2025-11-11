#!/usr/bin/env python3
"""
Master Launcher for Audio Recording System (PyInstaller Compatible)
Runs all services as threads instead of subprocesses when frozen
"""

import os
import sys
import time
import threading
from pathlib import Path
from logging_config import setup_logging

# Setup logging
logger = setup_logging("launcher")

def run_flask_app():
    """Run Flask application"""
    try:
        import app
        app.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Flask app error: {e}", exc_info=True)

def run_hotkey_listener():
    """Run hotkey listener"""
    try:
        import hotkey_listener
        hotkey_listener.main()
    except Exception as e:
        logger.error(f"Hotkey listener error: {e}", exc_info=True)

def run_websocket_client():
    """Run WebSocket client"""
    try:
        import websocket_client
        import asyncio
        client = websocket_client.MeetingRecorderClient()
        asyncio.run(client.run())
    except Exception as e:
        logger.error(f"WebSocket client error: {e}", exc_info=True)

def run_bluetooth_monitor():
    """Run Bluetooth monitor"""
    try:
        import bluetooth_endpoint_monitor
        bluetooth_endpoint_monitor.main()
    except Exception as e:
        logger.error(f"Bluetooth monitor error: {e}", exc_info=True)

def main():
    """Main entry point"""
    logger.info("=" * 70)
    logger.info(" AUDIO RECORDING SYSTEM - MASTER LAUNCHER")
    logger.info("=" * 70)
    logger.info(f" Running as: {'Frozen (PyInstaller)' if getattr(sys, 'frozen', False) else 'Python Script'}")
    logger.info("=" * 70)
    
    # Start all services as threads
    threads = []
    
    services = [
        ("Flask App", run_flask_app),
        ("Hotkey Listener", run_hotkey_listener),
        ("WebSocket Client", run_websocket_client),
        ("Bluetooth Monitor", run_bluetooth_monitor),
    ]
    
    for name, func in services:
        logger.info(f" Starting {name}...")
        thread = threading.Thread(target=func, name=name, daemon=True)
        thread.start()
        threads.append(thread)
        time.sleep(0.5)  # Stagger startup
    
    logger.info("=" * 70)
    logger.info(" All services started!")
    logger.info(" Flask dashboard: http://localhost:5000")
    logger.info(" Press Ctrl+C to stop all services")
    logger.info("=" * 70)
    logger.info("")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
            # Check if threads are still alive
            for thread in threads:
                if not thread.is_alive():
                    logger.warning(f" Thread {thread.name} has died!")
    except KeyboardInterrupt:
        logger.info("\n Shutdown signal received...")
        logger.info(" Stopping all services...")
        sys.exit(0)

if __name__ == "__main__":
    main()
