#!/usr/bin/env python3
"""
🎯 CLEAN TRANSCRIPTION VIEWER
============================
Simple, clean viewer for live transcriptions without all the server clutter.

Usage:
  python viewer.py               # Default server
  python viewer.py 192.168.1.100 8000  # Custom server
"""

import requests
import time
import json
import sys
from datetime import datetime
import os


class CleanTranscriptionViewer:
    def __init__(self, server_ip="172.105.109.189", server_port=8000):
        self.server_ip = server_ip
        self.server_port = server_port
        self.last_count = 0
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def get_transcriptions(self):
        """Fetch transcriptions from server"""
        try:
            response = requests.get(
                f"http://{self.server_ip}:{self.server_port}/api/transcriptions",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return []
                
        except requests.exceptions.RequestException:
            return None
    
    def display_transcriptions(self, transcriptions):
        """Display transcriptions in a clean format"""
        self.clear_screen()
        
        print("🎯 LIVE TRANSCRIPTION FEED")
        print("=" * 60)
        print(f"📡 Server: {self.server_ip}:{self.server_port}")
        print(f"⏰ Updated: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 Total: {len(transcriptions)} transcriptions")
        print("-" * 60)
        
        if not transcriptions:
            print("⏳ Waiting for transcriptions...")
            return
        
        # Show last 20 transcriptions
        recent = transcriptions[-20:]
        
        for i, t in enumerate(recent, 1):
            timestamp = datetime.fromtimestamp(t.get('timestamp', time.time()))
            time_str = timestamp.strftime("%H:%M:%S")
            text = t.get('text', '').strip()
            
            print(f"[{time_str}] {text}")
        
        print("-" * 60)
        print("💡 Press Ctrl+C to exit")
    
    def start_viewer(self):
        """Start the clean viewer"""
        print(f"🔄 Connecting to {self.server_ip}:{self.server_port}...")
        
        try:
            while True:
                transcriptions = self.get_transcriptions()
                
                if transcriptions is None:
                    print(f"❌ Cannot connect to server {self.server_ip}:{self.server_port}")
                    time.sleep(5)
                    continue
                
                # Only update screen if new transcriptions arrived
                if len(transcriptions) != self.last_count:
                    self.display_transcriptions(transcriptions)
                    self.last_count = len(transcriptions)
                
                time.sleep(2)  # Check every 2 seconds
                
        except KeyboardInterrupt:
            print("\n👋 Viewer stopped")
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    # Parse command line arguments
    server_ip = sys.argv[1] if len(sys.argv) > 1 else "172.105.109.189"
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    
    viewer = CleanTranscriptionViewer(server_ip, server_port)
    viewer.start_viewer()


if __name__ == "__main__":
    main()