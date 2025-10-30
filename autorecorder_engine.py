#!/usr/bin/env python3
"""
Auto-Recorder Engine
Automatically records today's scheduled meetings
"""
import sys
sys.path.insert(0, '.')

from app import app, Meeting, db
from datetime import datetime, timedelta
import time
import requests
import pytz

class AutoRecorderEngine:
    def __init__(self, app_base_url="http://localhost:5000"):
        self.app_base_url = app_base_url
        self.current_meeting = None
        self.eastern = pytz.timezone('US/Eastern')
    
    def get_todays_meetings(self):
        """Get today's non-excluded meetings"""
        with app.app_context():
            today = datetime.now(self.eastern).date()
            
            meetings = Meeting.query.filter(
                Meeting.user_excluded == False,
                Meeting.exclude_all_series == False
            ).all()
            
            # Filter for today
            today_meetings = [m for m in meetings if m.start_time.date() == today]
            
            # Sort by start time
            today_meetings.sort(key=lambda m: m.start_time)
            
            return today_meetings
    
    def find_next_meeting(self):
        """Find the next meeting that needs recording"""
        meetings = self.get_todays_meetings()
        now = datetime.now(self.eastern).replace(tzinfo=None)
        
        for meeting in meetings:
            # Check if meeting hasn't ended yet
            if meeting.end_time > now:
                # Check if not already recorded
                if not meeting.recording_id:
                    return meeting
        
        return None
    
    def check_recording_status(self):
        """Check if a recording is currently active"""
        try:
            response = requests.get(f"{self.app_base_url}/api/health", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return data.get('recording_active', False), data.get('meeting', {})
            return False, {}
        except Exception as e:
            print(f"❌ Error checking recording status: {e}")
            return False, {}
    
    def start_recording(self, meeting_id):
        """Start recording for a meeting"""
        try:
            url = f"{self.app_base_url}/api/start_recording"
            payload = {"meeting_id": meeting_id}
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                return True
            else:
                print(f"❌ Failed to start recording: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error starting recording: {e}")
            return False
    
    def stop_recording(self):
        """Stop current recording"""
        try:
            url = f"{self.app_base_url}/api/stop_recording"
            response = requests.post(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error stopping recording: {e}")
            return False
    
    def run(self):
        """Main auto-recorder loop"""
        print("="*60)
        print("🤖 AUTO-RECORDER ENGINE STARTED")
        print("="*60)
        
        while True:
            try:
                now = datetime.now(self.eastern).replace(tzinfo=None)
                
                # Find next meeting
                next_meeting = self.find_next_meeting()
                
                if not next_meeting:
                    print(f"\n⏰ {now.strftime('%I:%M:%S %p')} - No upcoming meetings to record")
                    time.sleep(60)  # Check again in 1 minute
                    continue
                
                # Calculate time until meeting starts
                time_until_start = (next_meeting.start_time - now).total_seconds()
                
                if time_until_start > 300:  # More than 5 minutes away
                    print(f"\n⏰ {now.strftime('%I:%M:%S %p')} - Next meeting: {next_meeting.subject}")
                    print(f"   Starts at: {next_meeting.start_time.strftime('%I:%M %p')}")
                    print(f"   Waiting {int(time_until_start/60)} minutes...")
                    time.sleep(60)  # Check again in 1 minute
                    continue
                
                # Meeting is starting soon or should have started
                if time_until_start <= 0:
                    print(f"\n🎬 {now.strftime('%I:%M:%S %p')} - Meeting should be recording: {next_meeting.subject}")
                    
                    # Check if recording is ongoing
                    is_recording, recording_info = self.check_recording_status()
                    
                    if is_recording:
                        current_meeting_id = recording_info.get('id')
                        if current_meeting_id == next_meeting.id:
                            print(f"   ✅ Already recording this meeting")
                        else:
                            print(f"   ⏳ Another recording in progress: {recording_info.get('subject', 'Unknown')}")
                            print(f"   Waiting for it to finish...")
                            time.sleep(30)  # Check again in 30 seconds
                            continue
                    else:
                        # No recording active, start this meeting
                        print(f"   🚀 Starting recording for: {next_meeting.subject}")
                        success = self.start_recording(next_meeting.id)
                        
                        if success:
                            print(f"   ✅ Recording started!")
                            self.current_meeting = next_meeting
                            
                            # Monitor until meeting end time
                            while datetime.now(self.eastern).replace(tzinfo=None) < next_meeting.end_time:
                                remaining = (next_meeting.end_time - datetime.now(self.eastern).replace(tzinfo=None)).total_seconds()
                                print(f"   📹 Recording... {int(remaining/60)} minutes remaining")
                                time.sleep(60)  # Check every minute
                            
                            # Meeting ended, stop recording
                            print(f"\n⏰ {datetime.now(self.eastern).strftime('%I:%M:%S %p')} - Meeting ended, stopping recording")
                            self.stop_recording()
                            print(f"   ✅ Recording stopped")
                            self.current_meeting = None
                        else:
                            print(f"   ❌ Failed to start recording")
                            time.sleep(30)  # Wait before retry
                else:
                    # Meeting starting in less than 5 minutes
                    print(f"\n⏰ {now.strftime('%I:%M:%S %p')} - Meeting starting soon: {next_meeting.subject}")
                    print(f"   Starts in {int(time_until_start)} seconds")
                    time.sleep(10)  # Check more frequently
                
            except KeyboardInterrupt:
                print("\n\n👋 Shutting down auto-recorder...")
                break
            except Exception as e:
                print(f"\n❌ Error in auto-recorder loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(30)

if __name__ == "__main__":
    engine = AutoRecorderEngine()
    engine.run()
