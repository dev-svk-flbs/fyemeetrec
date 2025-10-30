#!/usr/bin/env python3
"""List today's non-excluded meetings"""
import requests
from datetime import datetime

# Get meetings from Flask API
response = requests.get('http://localhost:5000/api/find_meeting', json={})

# Or query directly with correct approach
url = 'http://localhost:5000/admin/meetings'

# Actually, let's use direct Flask context
import sys
sys.path.insert(0, '.')
from app import app, Meeting, db

with app.app_context():
    today = datetime.now().date()
    
    # Query meetings
    meetings = Meeting.query.filter(
        Meeting.user_excluded == False,
        Meeting.exclude_all_series == False
    ).all()
    
    # Filter for today
    today_meetings = [m for m in meetings if m.start_time.date() == today]
    
    print(f"📅 Meetings for {today.strftime('%A, %B %d, %Y')}:\n")
    
    if today_meetings:
        for m in today_meetings:
            print(f"• {m.subject}")
            print(f"  Time: {m.start_time.strftime('%I:%M %p')} - {m.end_time.strftime('%I:%M %p')}")
            print(f"  ID: {m.id} | Status: {m.recording_status}")
            print()
    else:
        print("No meetings scheduled for today.")

