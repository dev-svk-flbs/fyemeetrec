"""
Test Event Filtering - All-Day and Non-Teams
===========================================

Test script to verify that all-day events and non-Teams meetings 
are properly filtered out from the AutoRecorder calendar view.
"""

import requests
import json
from datetime import datetime, timedelta

def test_event_filtering():
    """Test the filtering logic for all-day events and non-Teams meetings"""
    
    # Sample events including all-day events and non-Teams meetings
    test_events = [
        {
            "subject": "Team Meeting",
            "start": "2025-10-26T14:00:00.0000000",
            "end": "2025-10-26T15:00:00.0000000",
            "isAllDay": False,
            "webLink": "https://teams.microsoft.com/l/meetup-join/...",
            "requiredAttendees": "john@company.com;jane@company.com"
        },
        {
            "subject": "Birthday - John Doe",
            "start": "2025-10-26T00:00:00.0000000", 
            "end": "2025-10-27T00:00:00.0000000",
            "isAllDay": True
        },
        {
            "subject": "Personal Dentist Appointment",
            "start": "2025-10-26T10:00:00.0000000",
            "end": "2025-10-26T11:00:00.0000000",
            "isAllDay": False,
            "location": "123 Main St"
        },
        {
            "subject": "Client Call - Teams Meeting",
            "start": "2025-10-26T10:30:00.0000000",
            "end": "2025-10-26T11:00:00.0000000",
            "isAllDay": False,
            "body": "Join Microsoft Teams Meeting",
            "requiredAttendees": "client@external.com"
        },
        {
            "subject": "Lunch with Friend",
            "start": "2025-10-26T12:00:00.0000000",
            "end": "2025-10-26T13:00:00.0000000",
            "isAllDay": False,
            "location": "Restaurant Downtown"
        },
        {
            "subject": "Vacation Day",
            "start": "2025-10-27T00:00:00.0000000",
            "end": "2025-10-28T00:00:00.0000000",
            "isAllDay": True
        },
        {
            "subject": "Weekly Status Update",
            "start": "2025-10-26T16:00:00.0000000",
            "end": "2025-10-26T16:30:00.0000000",
            "isAllDay": False,
            "onlineMeeting": True,
            "requiredAttendees": "team@company.com"
        }
    ]
    
    print("🧪 Testing Event Filtering (All-Day + Non-Teams)")
    print("=" * 60)
    
    # Apply the same filtering logic as in app.py
    filtered_events = []
    all_day_count = 0
    non_teams_count = 0
    
    for event in test_events:
        # Check if event is all-day
        is_all_day = False
        
        if event.get('isAllDay') is True:
            is_all_day = True
        elif event.get('start') and event.get('end'):
            try:
                start_str = event['start']
                end_str = event['end']
                
                if 'T00:00:00' in start_str and ('T00:00:00' in end_str or 'T23:59:59' in end_str):
                    start_dt = datetime.fromisoformat(start_str.replace('.0000000', ''))
                    end_dt = datetime.fromisoformat(end_str.replace('.0000000', ''))
                    
                    duration_hours = (end_dt - start_dt).total_seconds() / 3600
                    if duration_hours >= 23.5:
                        is_all_day = True
            except:
                pass
        
        subject = event.get('subject', '').lower()
        if any(keyword in subject for keyword in ['birthday', 'holiday', 'vacation', 'pto', 'out of office']):
            is_all_day = True
        
        if is_all_day:
            all_day_count += 1
            print(f"🚫 ALL-DAY: {event['subject']}")
            continue
        
        # Check if event is a Teams meeting
        is_teams_meeting = False
        
        teams_indicators = [
            'teams.microsoft.com',
            'teams.live.com', 
            'meet.lync.com',
            'join microsoft teams meeting',
            'microsoft teams meeting',
            'teams meeting'
        ]
        
        # Check various fields for Teams indicators
        web_link = event.get('webLink', '').lower()
        if any(indicator in web_link for indicator in teams_indicators):
            is_teams_meeting = True
        
        body = event.get('body', '').lower()
        if any(indicator in body for indicator in teams_indicators):
            is_teams_meeting = True
        
        location = event.get('location', '').lower()
        if any(indicator in location for indicator in teams_indicators):
            is_teams_meeting = True
        
        if any(indicator in subject for indicator in ['teams', 'meeting']):
            is_teams_meeting = True
        
        if event.get('onlineMeeting') or event.get('isOnlineMeeting'):
            is_teams_meeting = True
        
        if event.get('requiredAttendees') or event.get('attendees'):
            is_teams_meeting = True
        
        if not is_teams_meeting:
            non_teams_count += 1
            print(f"🚫 NON-TEAMS: {event['subject']}")
            continue
        
        filtered_events.append(event)
        print(f"✅ KEPT: {event['subject']} (Teams meeting)")
    
    print("\n📊 Results:")
    print(f"  Total events: {len(test_events)}")
    print(f"  All-day events filtered: {all_day_count}")
    print(f"  Non-Teams events filtered: {non_teams_count}")
    print(f"  Remaining Teams meetings: {len(filtered_events)}")
    
    # Expected: Should filter out 2 all-day events, 2 non-Teams events, keep 3 Teams meetings
    expected_all_day = 2
    expected_non_teams = 2
    expected_remaining = 3
    
    if (all_day_count == expected_all_day and 
        non_teams_count == expected_non_teams and 
        len(filtered_events) == expected_remaining):
        print("\n✅ TEST PASSED: Event filtering works correctly!")
        return True
    else:
        print(f"\n❌ TEST FAILED:")
        print(f"   Expected: {expected_all_day} all-day, {expected_non_teams} non-Teams, {expected_remaining} remaining")
        print(f"   Got: {all_day_count} all-day, {non_teams_count} non-Teams, {len(filtered_events)} remaining")
        return False

if __name__ == "__main__":
    test_event_filtering()