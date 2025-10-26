#!/usr/bin/env python3
"""
Bare minimum script to check calendar events for souvik@fyelabs.com
"""

import requests
import json
from datetime import datetime, timedelta

# Your calendar ID
CALENDAR_ID = "AQMkADBjYWZhZWI5LTE2ZmItNDUyNy1iNDA4LTY0M2NmOTE0YmU3NwAARgAAA0x0AMwFqHZHtaHN6whvT4UHAGZu2hZpbwRNmdBVsXEd-pIAAAIBBgAAAGZu2hZpbwRNmdBVsXEd-pIAAAJdWQAAAA=="

# Power Automate workflow URL for calendar availability
WORKFLOW_URL = "https://default27828ac15d864f46abfd89560403e7.89.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/eaf1261797f54ecd875b16b92047518f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=u4zF0dj8ImUdRzDQayjczqITduEt2lDrCx1KzEJInFg"

def check_calendar():
    """Check calendar events for today"""
    
    # Today's date range
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)
    
    # Prepare request data
    data = {
        'cal_id': CALENDAR_ID,
        'start_date': start_date.isoformat() + 'Z',
        'end_date': end_date.isoformat() + 'Z',
        'email': 'souvik@fyelabs.com'
    }
    
    print(f"Checking calendar for: {data['email']}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("-" * 50)
    
    try:
        # Send request to Power Automate
        response = requests.post(
            WORKFLOW_URL,
            headers={'Content-Type': 'application/json'},
            json=data,
            timeout=30
        )
        
        if response.status_code in [200, 201, 202]:
            events = response.json()
            
            if isinstance(events, list):
                print(f"✅ Found {len(events)} events:")
                
                for i, event in enumerate(events, 1):
                    subject = event.get('subject', 'No Subject')
                    start = event.get('start', 'Unknown start')
                    end = event.get('end', 'Unknown end')
                    
                    print(f"{i}. {subject}")
                    print(f"   Time: {start} to {end}")
                    print()
                    
                if not events:
                    print("🆓 No events found - calendar is free!")
            else:
                print("✅ Response received:")
                print(json.dumps(events, indent=2))
                
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    check_calendar()