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
        self.user_info = None
        self.weekly_meetings = []
        self.weekly_meetings_last_updated = None
    
    def get_current_user(self):
        """Get current logged-in user information"""
        try:
            url = f"{self.app_base_url}/api/current_user"
            response = requests.get(url, timeout=2)
            
            if response.status_code == 200:
                return response.json()
            return {'logged_in': False}
        except Exception as e:
            print(f"❌ Error getting user info: {e}")
            return {'logged_in': False}
        
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
    
    def find_meeting_by_details(self, subject, organizer, start_time):
        """Find meeting in local database by subject, organizer, and start_time via Flask API"""
        try:
            print(f"🔍 Searching for meeting:")
            print(f"   Subject: {subject}")
            print(f"   Organizer: {organizer}")
            print(f"   Start Time: {start_time}")
            
            # Use Flask API to find meeting by matching fields
            url = f"{self.app_base_url}/api/find_meeting_by_details"
            payload = {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time
            }
            
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
                    print(f"❌ No meeting found matching:")
                    print(f"   Subject: {subject}")
                    print(f"   Organizer: {organizer}")
                    print(f"   Start Time: {start_time}")
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
                    'recording_type': data.get('recording_type', 'none'),
                    'meeting': data.get('meeting'),
                    'timestamp': data.get('timestamp')
                }
            else:
                return {'alive': False, 'error': f'Status {response.status_code}'}
        except requests.exceptions.RequestException as e:
            return {'alive': False, 'error': str(e)}
    
    async def health_monitor(self):
        """Monitor Flask app health and report to server"""
        print("\n💓 Starting health monitor...")
        
        user_info_refresh_count = 0
        sync_check_count = 0
        previous_app_alive = None
        
        while True:
            try:
                # Refresh user info every 5 seconds (5 iterations) instead of 30
                if user_info_refresh_count % 5 == 0:
                    old_user_info = self.user_info
                    self.user_info = self.get_current_user()
                    
                    # Check if user login status changed
                    old_logged_in = old_user_info.get('logged_in', False) if old_user_info else False
                    new_logged_in = self.user_info.get('logged_in', False)
                    
                    if not old_logged_in and new_logged_in:
                        print(f"🔑 User just logged in: {self.user_info.get('username')} ({self.user_info.get('email')})")
                    elif old_logged_in and not new_logged_in:
                        print("� User just logged out")
                    elif new_logged_in:
                        print(f"�👤 User: {self.user_info.get('username')} ({self.user_info.get('email')})")
                    else:
                        print("👤 No user logged in")
                
                user_info_refresh_count += 1
                
                # Check for sync requests every 5 seconds (5 iterations)
                if sync_check_count % 5 == 0:
                    await self.check_for_sync_requests()
                
                sync_check_count += 1
                
                # Check app health
                health = self.check_app_health()
                is_alive = health.get('alive', False)
                
                # If app just came alive, refresh user info immediately
                if is_alive and previous_app_alive is False:
                    print("🔄 App just came online - refreshing user info immediately")
                    self.user_info = self.get_current_user()
                    if self.user_info.get('logged_in'):
                        print(f"👤 Detected user after app startup: {self.user_info.get('username')} ({self.user_info.get('email')})")
                
                # Update status
                if is_alive != self.app_is_alive:
                    self.app_is_alive = is_alive
                    if is_alive:
                        print("✅ Flask app is alive")
                    else:
                        print("❌ Flask app is NOT responding")
                
                previous_app_alive = is_alive
                
                # Build health report
                health_report = {
                    "alive": is_alive,
                    "recording_active": health.get('recording_active', False),
                    "recording_type": health.get('recording_type', 'none'),
                    "error": health.get('error'),
                    "hostname": os.environ.get('COMPUTERNAME', 'unknown')
                }
                
                # Add user info to health report
                if self.user_info and self.user_info.get('logged_in'):
                    health_report['user'] = {
                        'username': self.user_info.get('username'),
                        'email': self.user_info.get('email'),
                        'user_id': self.user_info.get('user_id')
                    }
                    # Debug: Show what user info we're sending (only every 10th time to avoid spam)
                    if user_info_refresh_count % 10 == 0:
                        print(f"📤 Sending health with user: {self.user_info.get('email')}")
                else:
                    health_report['user'] = None
                    # Debug: Show why no user info (only every 10th time to avoid spam)
                    if user_info_refresh_count % 10 == 0:
                        if not self.user_info:
                            print("📤 Sending health: No user info available")
                        elif not self.user_info.get('logged_in'):
                            print("📤 Sending health: User not logged in")
                        else:
                            print("📤 Sending health: Unknown user state")
                
                # Add meeting info if recording a meeting
                if health.get('meeting'):
                    health_report['meeting'] = health.get('meeting')
                
                # Report to server
                await self.send_message("app_health", health_report)
                
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
            print(f"📤 Sent: {message_type}")
        except Exception as e:
            print(f"❌ Error sending message: {e}")
    
    async def handle_start_command(self, data):
        """Handle start recording command from server"""
        # Extract matching fields from command
        subject = data.get('subject')
        organizer = data.get('organizer')
        start_time = data.get('start_time')
        duration_minutes = data.get('duration', 60)
        
        print(f"\n{'='*60}")
        print(f"📋 START COMMAND RECEIVED")
        print(f"   Subject: {subject}")
        print(f"   Organizer: {organizer}")
        print(f"   Start Time: {start_time}")
        print(f"   Duration: {duration_minutes} minutes")
        print(f"{'='*60}\n")
        
        # Step 1: Find meeting in database using matching fields
        meeting = self.find_meeting_by_details(subject, organizer, start_time)
        
        if not meeting:
            await self.send_message("start_failed", {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time,
                "reason": "Meeting not found in local database"
            })
            return
        
        # Step 2: Start recording
        success = self.start_recording(meeting.get('id'))
        
        if success:
            self.current_recording = {
                "meeting_id": meeting.get('id'),
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time
            }
            self.recording_start_time = time.time()
            self.recording_duration = duration_minutes * 60  # Convert to seconds
            
            await self.send_message("start_confirmed", {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time,
                "duration": duration_minutes
            })
            
            # Start monitoring task
            asyncio.create_task(self.monitor_recording())
        else:
            await self.send_message("start_failed", {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time,
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
        
        check_interval = 5  # Check every 5 seconds to detect premature stops faster
        
        while self.current_recording:
            # Check elapsed time
            elapsed = time.time() - self.recording_start_time
            remaining = self.recording_duration - elapsed
            
            print(f"\n⏱️  Elapsed: {int(elapsed)}s / {self.recording_duration}s (Remaining: {int(remaining)}s)")
            
            # Check Flask app health to detect if recording stopped
            health = self.check_app_health()
            recording_active = health.get('recording_active', False)
            
            # If recording is no longer active in Flask but we think it should be
            if not recording_active and elapsed < self.recording_duration:
                print("⚠️  Recording stopped prematurely on Flask side!")
                await self.send_message("recording_stopped_premature", {
                    "subject": self.current_recording["subject"],
                    "organizer": self.current_recording["organizer"],
                    "start_time": self.current_recording["start_time"],
                    "duration_actual": int(elapsed),
                    "duration_expected": self.recording_duration,
                    "reason": "User stopped recording manually or error occurred"
                })
                
                # Clear tracking state
                self.current_recording = None
                self.recording_start_time = None
                self.recording_duration = None
                break
            
            # Check if FFmpeg is running
            ffmpeg_ok = self.check_ffmpeg_running()
            
            if not ffmpeg_ok and recording_active:
                print("⚠️  FFmpeg not detected but Flask reports recording active")
                await self.send_message("recording_warning", {
                    "subject": self.current_recording["subject"],
                    "organizer": self.current_recording["organizer"],
                    "start_time": self.current_recording["start_time"],
                    "warning": "FFmpeg process not detected"
                })
            elif recording_active:
                # Send positive confirmation that recording is ongoing
                await self.send_message("recording_status", {
                    "subject": self.current_recording["subject"],
                    "organizer": self.current_recording["organizer"],
                    "start_time": self.current_recording["start_time"],
                    "status": "recording",
                    "elapsed": int(elapsed),
                    "remaining": int(remaining)
                })
            
            # Check if duration elapsed
            if elapsed >= self.recording_duration:
                print("\n⏰ Duration elapsed - stopping recording")
                await self.stop_recording_and_confirm(reason="completed")
                break
            
            # Wait before next check
            await asyncio.sleep(check_interval)
    
    async def stop_recording_and_confirm(self, reason="completed"):
        """Stop recording and send confirmation
        
        Args:
            reason: Why recording stopped - "completed", "manual", "premature", "error"
        """
        if not self.current_recording:
            return
        
        subject = self.current_recording["subject"]
        organizer = self.current_recording["organizer"]
        start_time = self.current_recording["start_time"]
        
        # Calculate actual duration
        actual_duration = int(time.time() - self.recording_start_time) if self.recording_start_time else 0
        expected_duration = self.recording_duration if self.recording_duration else 0
        
        # Stop the recording
        success = self.stop_recording()
        
        if success:
            await self.send_message("stop_confirmed", {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time,
                "duration_actual": actual_duration,
                "duration_expected": expected_duration,
                "reason": reason,
                "status": "success"
            })
        else:
            await self.send_message("stop_failed", {
                "subject": subject,
                "organizer": organizer,
                "start_time": start_time,
                "reason": f"Failed to stop recording: {reason}",
                "duration_actual": actual_duration
            })
        
        # Clear current recording
        self.current_recording = None
        self.recording_start_time = None
        self.recording_duration = None
    
    async def handle_stop_command(self, data):
        """Handle manual stop command from server"""
        print("\n🛑 STOP COMMAND RECEIVED")
        print(f"   Subject: {data.get('subject', 'N/A')}")
        print(f"   Organizer: {data.get('organizer', 'N/A')}")
        print(f"   Start Time: {data.get('start_time', 'N/A')}")
        await self.stop_recording_and_confirm(reason="manual")
    
    async def handle_weekly_meetings(self, data):
        """Handle weekly meetings data from server"""
        user_email = data.get('user_email')
        meetings = data.get('meetings', [])
        total_count = data.get('total_count', 0)
        date_range = data.get('date_range', {})
        is_requested = data.get('requested', False)
        
        if is_requested:
            print(f"\n📅 Weekly meetings received (requested): {total_count} meetings for {user_email}")
        else:
            print(f"\n📅 Weekly meetings received (scheduled): {total_count} meetings for {user_email}")
        
        print(f"   Date range: {date_range.get('start')} to {date_range.get('end')}")
        
        # Process each meeting
        for meeting in meetings:
            start_time = meeting.get('start_time')
            subject = meeting.get('subject')
            status = meeting.get('recording_status')
            auto_record = meeting.get('auto_record')
            
            # Show the UTC time being received
            print(f"   📋 {start_time} UTC - {subject} (Status: {status}, Auto: {auto_record})")
        
        print(f"   💡 Times will be converted from UTC to Eastern before saving to database")
        
        # Store meetings for application use
        self.weekly_meetings = meetings
        self.weekly_meetings_last_updated = datetime.now()
        
        # Save meetings to local database via Flask API
        await self.save_meetings_to_database(user_email, meetings)
    
    async def save_meetings_to_database(self, user_email, meetings):
        """Save meetings to local database via Flask API"""
        try:
            print(f"\n💾 Saving {len(meetings)} meetings to local database...")
            
            url = f"{self.app_base_url}/api/save_weekly_meetings"
            payload = {
                "user_email": user_email,
                "meetings": meetings
            }
            
            # Use asyncio to run the synchronous request in a thread pool
            import asyncio
            loop = asyncio.get_event_loop()
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, timeout=10)
            )
            
            if response.status_code == 200:
                data = response.json()
                added = data.get('added', 0)
                updated = data.get('updated', 0)
                skipped = data.get('skipped', 0)
                
                print(f"✅ Meetings saved successfully:")
                print(f"   Added: {added}")
                print(f"   Updated: {updated}")
                print(f"   Skipped: {skipped}")
            else:
                print(f"❌ Failed to save meetings: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"❌ Error saving meetings to database: {e}")
            import traceback
            traceback.print_exc()
    
    async def request_weekly_meetings(self):
        """Request weekly meetings from server immediately"""
        print("\n📅 Requesting weekly meetings from server...")
        await self.send_message("request_weekly_meetings", {})
    
    async def check_for_sync_requests(self):
        """Check for sync request flag files from Flask admin interface"""
        try:
            sync_request_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_request.flag')
            
            if os.path.exists(sync_request_file):
                try:
                    # Read the sync request
                    with open(sync_request_file, 'r') as f:
                        request_data = json.loads(f.read())
                    
                    print(f"\n🔄 Sync request detected from {request_data.get('requested_by', 'unknown')}")
                    print(f"   Timestamp: {request_data.get('timestamp')}")
                    print(f"   User: {request_data.get('user_email', 'system')}")
                    
                    # Request weekly meetings from server
                    await self.request_weekly_meetings()
                    
                    # Remove the flag file
                    os.remove(sync_request_file)
                    print("✅ Sync request processed and flag file removed")
                    
                except Exception as e:
                    print(f"❌ Error processing sync request: {e}")
                    # Remove the corrupted flag file
                    try:
                        os.remove(sync_request_file)
                    except:
                        pass
        
        except Exception as e:
            # Silently continue - file monitoring errors shouldn't crash the health monitor
            pass
    
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
                    elif msg_type == 'weekly_meetings':
                        await self.handle_weekly_meetings(msg_data)
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
                # Get user information
                self.user_info = self.get_current_user()
                
                # Build connection message
                connection_data = {
                    "hostname": os.environ.get('COMPUTERNAME', 'unknown'),
                    "status": "ready"
                }
                
                # Add user info if available
                if self.user_info.get('logged_in'):
                    connection_data['user'] = {
                        'username': self.user_info.get('username'),
                        'email': self.user_info.get('email'),
                        'user_id': self.user_info.get('user_id')
                    }
                
                await self.send_message("client_connected", connection_data)
                
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