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
from logging_config import setup_logging

# Setup logging
logger = setup_logging("websocket_client")

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
            logger.error(f" Error getting user info: {e}")
            return {'logged_in': False}
    
    def is_remote_recording_enabled(self):
        """Check if remote recording is enabled by calling Flask API to check localStorage"""
        try:
            # Since we can't directly access localStorage from Python, we'll create a simple API check
            # The API will return instructions on how to check localStorage
            url = f"{self.app_base_url}/api/remote_recording_status"
            response = requests.get(url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('enabled', False)
            return False
        except Exception as e:
            logger.error(f" Error checking remote recording status: {e}")
            return False
    
    def check_remote_status_file(self):
        """Check remote recording status from JSON file"""
        try:
            json_file = 'remote_recording_status.json'
            if os.path.exists(json_file):
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    return data.get('enabled', False)
            return False
        except Exception as e:
            logger.error(f" Error reading remote recording status file: {e}")
            return False
    
    def save_weekly_meetings_to_file(self):
        """Save received weekly meetings to a JSON file for persistence"""
        try:
            meetings_file = 'weekly_meetings.json'
            meetings_data = {
                'last_updated': datetime.now().isoformat(),
                'timestamp': self.weekly_meetings_last_updated,
                'count': len(self.weekly_meetings),
                'meetings': self.weekly_meetings
            }
            
            with open(meetings_file, 'w') as f:
                json.dump(meetings_data, f, indent=2, default=str)
            
            logger.info(f" Saved {len(self.weekly_meetings)} meetings to {meetings_file}")
            
        except Exception as e:
            logger.error(f" Error saving meetings to file: {e}")
    
    def load_weekly_meetings_from_file(self):
        """Load previously saved weekly meetings from file"""
        try:
            meetings_file = 'weekly_meetings.json'
            if os.path.exists(meetings_file):
                with open(meetings_file, 'r') as f:
                    data = json.load(f)
                    
                self.weekly_meetings = data.get('meetings', [])
                self.weekly_meetings_last_updated = data.get('timestamp', time.time())
                
                logger.info(f" Loaded {len(self.weekly_meetings)} meetings from {meetings_file}")
                return True
            return False
        except Exception as e:
            logger.error(f" Error loading meetings from file: {e}")
            return False
    
    def _is_today(self, date_str):
        """Check if a date string is today"""
        try:
            from datetime import datetime, date
            # Try to parse the date string (assuming ISO format)
            meeting_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            return meeting_date == date.today()
        except:
            return False
    
    async def connect(self):
        """Connect to the WebSocket server"""
        try:
            logger.info(f" Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(self.server_url)
            logger.info(" Connected to remote control server")
            return True
        except Exception as e:
            logger.error(f" Connection failed: {e}")
            return False
    
    async def search_meeting_by_details(self, subject, organizer, start_time):
        """Search for a meeting in the local database by details"""
        try:
            logger.info(f" Searching for meeting:")
            logger.info(f"   Subject: {subject}")
            logger.info(f"   Organizer: {organizer}")
            logger.info(f"   Start Time: {start_time}")
            
            # Call Flask API to search meetings
            url = f"{self.app_base_url}/api/meetings/search"
            response = requests.post(
                url,
                json={
                    'subject': subject,
                    'organizer_email': organizer,
                    'start_time': start_time
                },
                timeout=5
            )
            
            if response.status_code == 200:
                meetings = response.json().get('meetings', [])
                if meetings:
                    meeting = meetings[0]  # Take first match
                    logger.info(f" Found meeting: {meeting.get('subject')}")
                    logger.info(f"   Start: {meeting.get('start_time')}")
                    logger.info(f"   Meeting DB ID: {meeting.get('id')}")
                    return meeting.get('id')
                else:
                    logger.warning(f" No meeting found matching:")
                    logger.warning(f"   Subject: {subject}")
                    logger.warning(f"   Organizer: {organizer}")
                    logger.warning(f"   Start: {start_time}")
                    return None
            else:
                logger.error(f" Meeting search failed: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f" Error searching for meeting: {e}", exc_info=True)
            return None
    
    async def send_message(self, message_type, data=None):
        """Send a message to the WebSocket server"""
        if not self.websocket:
            logger.warning(" Cannot send message - not connected")
            return
        
        try:
            message = {
                "type": message_type,
                "timestamp": datetime.now().isoformat(),
                "data": data or {}
            }
            await self.websocket.send(json.dumps(message))
            logger.debug(f" Sent: {message_type}")
        except Exception as e:
            logger.error(f" Error sending message: {e}")
    
    async def handle_start_recording(self, data):
        """Handle remote start recording command"""
        try:
            logger.info(" Remote START command received")
            logger.info(f"   Data: {json.dumps(data, indent=2)}")
            
            # Extract meeting details
            meeting_id = data.get('meeting_id')
            subject = data.get('subject', 'Remote Recording')
            organizer = data.get('organizer', '')
            start_time = data.get('start_time', '')
            
            # Check if remote recording is enabled
            if not self.check_remote_status_file():
                logger.warning(" Remote recording is DISABLED - ignoring command")
                await self.send_message("recording_rejected", {
                    "reason": "Remote recording disabled on this client",
                    "meeting_id": meeting_id
                })
                return
            
            logger.info(" Remote recording is ENABLED - processing command")
            
            # Search for meeting in local database
            local_meeting_id = await self.search_meeting_by_details(subject, organizer, start_time)
            
            if not local_meeting_id:
                logger.warning(f" Meeting not found in local database - creating manual recording")
            
            # Start recording via Flask API
            logger.info(f" Starting recording via Flask API...")
            url = f"{self.app_base_url}/start"
            
            payload = {
                'title': subject,
                'meeting_id': local_meeting_id,
                'remote_trigger': True,
                'remote_meeting_id': meeting_id  # Original meeting ID from server
            }
            
            logger.info(f"   Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f" Recording started successfully")
                logger.info(f"   Status: {result.get('status')}")
                logger.info(f"   Monitor: {result.get('monitor')}")
                logger.info(f"   Recording ID: {result.get('recording_id')}")
                
                # Store recording info
                self.current_recording = {
                    'recording_id': result.get('recording_id'),
                    'meeting_id': meeting_id,
                    'local_meeting_id': local_meeting_id,
                    'subject': subject
                }
                self.recording_start_time = time.time()
                
                # Notify server of success
                await self.send_message("recording_started", {
                    "recording_id": result.get('recording_id'),
                    "meeting_id": meeting_id,
                    "local_meeting_id": local_meeting_id,
                    "monitor": result.get('monitor'),
                    "status": "started"
                })
            else:
                error_msg = response.json().get('error', 'Unknown error') if response.headers.get('content-type') == 'application/json' else response.text
                logger.error(f" Failed to start recording: {error_msg}")
                
                # Notify server of failure
                await self.send_message("recording_failed", {
                    "meeting_id": meeting_id,
                    "error": error_msg,
                    "status_code": response.status_code
                })
                
        except Exception as e:
            logger.error(f" Error handling start command: {e}", exc_info=True)
            await self.send_message("recording_failed", {
                "meeting_id": data.get('meeting_id'),
                "error": str(e)
            })
    
    async def handle_stop_recording(self, data):
        """Handle remote stop recording command"""
        try:
            logger.info(" Remote STOP command received")
            logger.info(f"   Data: {json.dumps(data, indent=2)}")
            
            meeting_id = data.get('meeting_id')
            
            # Stop recording via Flask API
            logger.info(f" Stopping recording via Flask API...")
            url = f"{self.app_base_url}/stop"
            
            response = requests.post(url, json={'remote_trigger': True}, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f" Recording stopped successfully")
                logger.info(f"   Status: {result.get('status')}")
                
                # Calculate duration if we have start time
                duration = None
                if self.recording_start_time:
                    duration = int(time.time() - self.recording_start_time)
                    logger.info(f"   Duration: {duration}s")
                
                # Notify server of success
                await self.send_message("recording_stopped", {
                    "meeting_id": meeting_id,
                    "recording_id": self.current_recording.get('recording_id') if self.current_recording else None,
                    "duration": duration,
                    "status": "stopped"
                })
                
                # Clear recording state
                self.current_recording = None
                self.recording_start_time = None
            else:
                error_msg = response.json().get('error', 'Unknown error') if response.headers.get('content-type') == 'application/json' else response.text
                logger.error(f" Failed to stop recording: {error_msg}")
                
                # Notify server of failure
                await self.send_message("stop_failed", {
                    "meeting_id": meeting_id,
                    "error": error_msg,
                    "status_code": response.status_code
                })
                
        except Exception as e:
            logger.error(f" Error handling stop command: {e}", exc_info=True)
            await self.send_message("stop_failed", {
                "meeting_id": data.get('meeting_id'),
                "error": str(e)
            })
    
    async def handle_message(self, message):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            msg_data = data.get('data', {})
            
            logger.debug(f" Received message: {msg_type}")
            
            if msg_type == 'start_recording':
                await self.handle_start_recording(msg_data)
            elif msg_type == 'stop_recording':
                await self.handle_stop_recording(msg_data)
            elif msg_type == 'ping':
                await self.send_message('pong')
            elif msg_type == 'weekly_meetings':
                self.weekly_meetings = msg_data.get('meetings', [])
                self.weekly_meetings_last_updated = time.time()
                
                if self.weekly_meetings:
                    # Log summary only
                    today_meetings = [m for m in self.weekly_meetings if self._is_today(m.get('start_time', ''))]
                    excluded_meetings = [m for m in self.weekly_meetings if m.get('user_excluded') or m.get('exclude_all_series')]
                    recurring_meetings = [m for m in self.weekly_meetings if m.get('is_recurring')]
                    
                    logger.info(f" Received {len(self.weekly_meetings)} weekly meetings - Today: {len(today_meetings)}, Recurring: {len(recurring_meetings)}, Excluded: {len(excluded_meetings)}")
                    
                    # Save meetings to local file for persistence
                    self.save_weekly_meetings_to_file()
                    
                    # Sync to database if Flask app is available
                    if self.app_is_alive:
                        await self.sync_meetings_to_database()
                else:
                    logger.info(" No meetings in the current week")
            else:
                logger.debug(f"ℹ Unknown message type: {msg_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f" Invalid JSON received: {e}")
        except Exception as e:
            logger.error(f" Error handling message: {e}", exc_info=True)
    
    async def health_monitor(self):
        """Monitor Flask app health and send periodic updates"""
        while True:
            try:
                # Check Flask app health
                response = requests.get(f"{self.app_base_url}/api/status", timeout=2)
                self.app_is_alive = response.status_code == 200
                
                if self.app_is_alive:
                    status_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                    
                    # Send health update to server (using app_health so server updates heartbeat)
                    await self.send_message("app_health", {
                        "alive": True,
                        "recording_active": status_data.get('recording', False),
                        "recording_type": "meeting" if status_data.get('recording') else "none",
                        "remote_enabled": self.check_remote_status_file(),
                        "user": self.user_info if self.user_info and self.user_info.get('logged_in') else None,
                        "error": None
                    })
                else:
                    await self.send_message("app_health", {
                        "alive": False,
                        "recording_active": False,
                        "recording_type": "none",
                        "remote_enabled": self.check_remote_status_file(),
                        "user": self.user_info if self.user_info and self.user_info.get('logged_in') else None,
                        "error": "Flask app not responding"
                    })
                
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
                self.app_is_alive = False
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def sync_meetings_to_database(self):
        """Sync received meetings to local Flask database"""
        try:
            if not self.weekly_meetings:
                logger.info(" No meetings to sync to database")
                return
                
            # Get user email for the API call
            user_email = None
            if self.user_info and self.user_info.get('logged_in'):
                user_email = self.user_info.get('email')
            
            if not user_email:
                logger.warning(" Cannot sync meetings - no user email available")
                return
                
            logger.info(f" Syncing {len(self.weekly_meetings)} meetings to database for {user_email}...")
            
            url = f"{self.app_base_url}/api/save_weekly_meetings"
            payload = {
                'user_email': user_email,
                'meetings': self.weekly_meetings
            }
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f" Meeting sync completed:")
                logger.info(f"    Total processed: {result.get('total_processed', 0)}")
                logger.info(f"    New meetings: {result.get('added', 0)}")
                logger.info(f"    Updated meetings: {result.get('updated', 0)}")
                logger.info(f"     Skipped meetings: {result.get('skipped', 0)}")
            else:
                logger.error(f" Meeting sync failed: HTTP {response.status_code}")
                if response.headers.get('content-type') == 'application/json':
                    error_data = response.json()
                    logger.error(f"   Error: {error_data.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f" Error syncing meetings to database: {e}", exc_info=True)
    
    async def listen(self):
        """Listen for incoming messages"""
        try:
            async for message in self.websocket:
                await self.handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning(" Connection closed by server")
        except Exception as e:
            logger.error(f" Error in listen loop: {e}", exc_info=True)
    
    async def run(self):
        """Main run loop with auto-reconnect"""
        # Load existing meetings on startup
        self.load_weekly_meetings_from_file()
        
        while True:
            try:
                # Get user info before connecting
                self.user_info = self.get_current_user()
                
                if await self.connect():
                    # Send connection info
                    connection_data = {
                        "client_type": "meeting_recorder",
                        "remote_enabled": self.check_remote_status_file()
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
                        logger.info(" Health monitor started")
                    
                    await self.listen()
                    
                    # Cancel health monitor if connection lost
                    if self.health_check_task and not self.health_check_task.done():
                        self.health_check_task.cancel()
                
                # Reconnect after delay
                logger.info("\n Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            
            except KeyboardInterrupt:
                logger.info("\n Shutting down...")
                break
            except Exception as e:
                logger.error(f" Error in run loop: {e}", exc_info=True)
                await asyncio.sleep(5)
    
    def close(self):
        """Clean up resources"""
        if self.health_check_task and not self.health_check_task.done():
            self.health_check_task.cancel()
        logger.info(" Client closed")

async def main():
    """Main entry point"""
    logger.info("="*60)
    logger.info(" Meeting Recorder WebSocket Client")
    logger.info("="*60)
    
    client = MeetingRecorderClient()
    
    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("\n\n Shutting down...")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(main())
