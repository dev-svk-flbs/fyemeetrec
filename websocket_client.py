#!/usr/bin/env python3
"""
WebSocket Client for Remote Meeting Recording Control
Connects to ops.fyelabs.com to receive recording commands
"""

import asyncio
import websockets
import json
import requests
import subprocess
import time
from datetime import datetime
import os

class MeetingRecorderClient:
    def __init__(self, server_url="ws://ops.fyelabs.com:8769", app_base_url="http://localhost:5000"):
        self.server_url = server_url
        self.app_base_url = app_base_url
        self.websocket = None
        self.current_recording = None
        self.recording_start_time = None
        self.recording_duration = None
        self.health_check_task = None
        self.app_is_alive = False
        
    async def connect(self):
        """Connect to WebSocket server"""
        try:
            print(f"🔌 Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(self.server_url)
            print("✅ Connected to remote control server")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def find_meeting_by_event_id(self, calendar_event_id):
        """Find meeting in local database by calendar_event_id via Flask API"""
        try:
            print(f"🔍 Searching for meeting with event ID: {calendar_event_id[:50]}...")
            
            # Use Flask API to find meeting
            url = f"{self.app_base_url}/api/find_meeting"
            payload = {"calendar_event_id": calendar_event_id}
            
            response = requests.post(url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('found'):
                    meeting = data.get('meeting')
                    print(f"✅ Found meeting: {meeting.get('subject')}")
                    print(f"   Start: {meeting.get('start_time')}")
                    print(f"   Meeting DB ID: {meeting.get('id')}")
                    return meeting
                else:
                    print(f"❌ No meeting found with event ID: {calendar_event_id[:50]}...")
                    return None
            else:
                print(f"❌ API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error finding meeting: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def start_recording(self, meeting_id):
        """Send start recording request to Flask app"""
        try:
            url = f"{self.app_base_url}/api/start_recording"
            payload = {"meeting_id": meeting_id}
            
            print(f"🎥 Starting recording for meeting ID: {meeting_id}")
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Recording started: {data.get('message', 'Success')}")
                return True
            else:
                print(f"❌ Failed to start recording: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            return False
    
    def stop_recording(self):
        """Send stop recording request to Flask app"""
        try:
            url = f"{self.app_base_url}/api/stop_recording"
            
            print("🛑 Stopping recording...")
            response = requests.post(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Recording stopped: {data.get('message', 'Success')}")
                return True
            else:
                print(f"❌ Failed to stop recording: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
            return False
    
    def check_ffmpeg_running(self):
        """Check if ffmpeg process is actually running"""
        try:
            # Windows: tasklist
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq ffmpeg.exe'],
                capture_output=True,
                text=True,
                shell=True
            )
            
            is_running = 'ffmpeg.exe' in result.stdout
            
            if is_running:
                print("✅ FFmpeg is running")
            else:
                print("⚠️  FFmpeg is NOT running")
            
            return is_running
        except Exception as e:
            print(f"❌ Error checking FFmpeg: {e}")
            return False
    
    def check_app_health(self):
        """Check if Flask app is alive"""
        try:
            url = f"{self.app_base_url}/api/health"
            response = requests.get(url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'alive': data.get('alive', False),
                    'recording_active': data.get('recording_active', False),
                    'timestamp': data.get('timestamp')
                }
            else:
                return {'alive': False, 'error': f'Status {response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'alive': False, 'error': str(e)}
    
    async def health_monitor(self):
        """Monitor Flask app health and report to server"""
        print("\n💓 Starting health monitor...")
        
        while True:
            try:
                # Check app health
                health = self.check_app_health()
                is_alive = health.get('alive', False)
                
                # Update status
                if is_alive != self.app_is_alive:
                    self.app_is_alive = is_alive
                    if is_alive:
                        print("✅ Flask app is alive")
                    else:
                        print("❌ Flask app is NOT responding")
                
                # Report to server
                await self.send_message("app_health", {
                    "alive": is_alive,
                    "recording_active": health.get('recording_active', False),
                    "error": health.get('error')
                })
                
                # If app is dead, send alert
                if not is_alive:
                    await self.send_message("app_alert", {
                        "alert": "Flask application is not responding",
                        "error": health.get('error', 'Unknown error')
                    })
                
            except Exception as e:
                print(f"❌ Error in health monitor: {e}")
            
            # Wait 1 second before next check
            await asyncio.sleep(1)
    
    async def send_message(self, message_type, data):
        """Send message to server"""
        try:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            await self.websocket.send(json.dumps(message))
            print(f"📤 Sent: {message_type} - {data}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    async def handle_start_command(self, data):
        """Handle start recording command from server"""
        calendar_event_id = data.get('meeting_id')
        duration_minutes = data.get('duration', 60)
        
        print(f"\n{'='*60}")
        print(f"📋 START COMMAND RECEIVED")
        print(f"   Meeting ID: {calendar_event_id}")
        print(f"   Duration: {duration_minutes} minutes")
        print(f"{'='*60}\n")
        
        # Step 1: Find meeting in database
        meeting = self.find_meeting_by_event_id(calendar_event_id)
        
        if not meeting:
            await self.send_message("start_failed", {
                "meeting_id": calendar_event_id,
                "reason": "Meeting not found in local database"
            })
            return
        
        # Step 2: Start recording
        success = self.start_recording(meeting.get('id'))
        
        if success:
            self.current_recording = {
                "meeting_id": meeting.get('id'),
                "calendar_event_id": calendar_event_id,
                "subject": meeting.get('subject')
            }
            self.recording_start_time = time.time()
            self.recording_duration = duration_minutes * 60  # Convert to seconds
            
            await self.send_message("start_confirmed", {
                "meeting_id": calendar_event_id,
                "subject": meeting.get('subject'),
                "duration": duration_minutes
            })
            
            # Start monitoring task
            asyncio.create_task(self.monitor_recording())
        else:
            await self.send_message("start_failed", {
                "meeting_id": calendar_event_id,
                "reason": "Failed to start recording"
            })
    
    async def monitor_recording(self):
        """Monitor recording progress and FFmpeg status"""
        if not self.current_recording:
            return
        
        print("\n🔍 Starting recording monitor...")
        
        # Wait for FFmpeg to start (give it 10 seconds before first check)
        print("⏳ Waiting 10 seconds for FFmpeg to initialize...")
        await asyncio.sleep(10)
        
        check_interval = 30  # Check every 30 seconds after first check
        
        while self.current_recording:
            # Check elapsed time
            elapsed = time.time() - self.recording_start_time
            remaining = self.recording_duration - elapsed
            
            print(f"\n⏱️  Elapsed: {int(elapsed)}s / {self.recording_duration}s (Remaining: {int(remaining)}s)")
            
            # Check if FFmpeg is running
            ffmpeg_ok = self.check_ffmpeg_running()
            
            if not ffmpeg_ok:
                print("⚠️  FFmpeg not detected - recording may have stopped unexpectedly")
                await self.send_message("recording_warning", {
                    "meeting_id": self.current_recording["calendar_event_id"],
                    "warning": "FFmpeg process not detected"
                })
            else:
                # Send positive confirmation that recording is ongoing
                await self.send_message("recording_status", {
                    "meeting_id": self.current_recording["calendar_event_id"],
                    "status": "recording",
                    "elapsed": int(elapsed),
                    "remaining": int(remaining)
                })
            
            # Check if duration elapsed
            if elapsed >= self.recording_duration:
                print("\n⏰ Duration elapsed - stopping recording")
                await self.stop_recording_and_confirm()
                break
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def stop_recording_and_confirm(self):
        """Stop recording and send confirmation"""
        if not self.current_recording:
            return
        
        calendar_event_id = self.current_recording["calendar_event_id"]
        
        # Stop the recording
        success = self.stop_recording()
        
        if success:
            await self.send_message("stop_confirmed", {
                "meeting_id": calendar_event_id,
                "duration_actual": int(time.time() - self.recording_start_time)
            })
        else:
            await self.send_message("stop_failed", {
                "meeting_id": calendar_event_id,
                "reason": "Failed to stop recording"
            })
        
        # Clear current recording
        self.current_recording = None
        self.recording_start_time = None
        self.recording_duration = None
    
    async def handle_stop_command(self, data):
        """Handle manual stop command from server"""
        print("\n🛑 STOP COMMAND RECEIVED")
        await self.stop_recording_and_confirm()
    
    async def listen(self):
        """Listen for messages from server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')
                    msg_data = data.get('data', {})
                    
                    print(f"\n📥 Received: {msg_type}")
                    
                    if msg_type == 'start_recording':
                        await self.handle_start_command(msg_data)
                    elif msg_type == 'stop_recording':
                        await self.handle_stop_command(msg_data)
                    elif msg_type == 'ping':
                        await self.send_message('pong', {'status': 'ok'})
                    else:
                        print(f"⚠️  Unknown message type: {msg_type}")
                
                except json.JSONDecodeError as e:
                    print(f"❌ Invalid JSON: {e}")
                except Exception as e:
                    print(f"❌ Error handling message: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            print("\n❌ Connection closed by server")
        except Exception as e:
            print(f"\n❌ Error in listen loop: {e}")
    
    async def run(self):
        """Main run loop"""
        while True:
            if await self.connect():
                await self.send_message("client_connected", {
                    "hostname": os.environ.get('COMPUTERNAME', 'unknown'),
                    "status": "ready"
                })
                
                # Start health monitor
                if not self.health_check_task or self.health_check_task.done():
                    self.health_check_task = asyncio.create_task(self.health_monitor())
                    print("💓 Health monitor started")
                
                await self.listen()
                
                # Cancel health monitor if connection lost
                if self.health_check_task and not self.health_check_task.done():
                    self.health_check_task.cancel()
            
            # Reconnect after delay
            print("\n⏳ Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
    
    def close(self):
        """Clean up resources"""
        pass  # No database session to close anymore

async def main():
    """Main entry point"""
    print("="*60)
    print("🎥 Meeting Recorder WebSocket Client")
    print("="*60)
    
    client = MeetingRecorderClient()
    
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main())
