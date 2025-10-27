#!/usr/bin/env python3
"""
Fix meeting statuses for uploaded recordings
This script updates meeting statuses from 'recorded_local' to 'recorded_synced' 
when the associated recording has been successfully uploaded
"""

from app import app, db
from models import Meeting, Recording
from datetime import datetime

def fix_meeting_statuses():
    """Update meeting statuses for uploaded recordings"""
    with app.app_context():
        # Find meetings with 'recorded_local' status that have uploaded recordings
        outdated_meetings = Meeting.query.join(Recording, Meeting.recording_id == Recording.id)\
            .filter(
                Meeting.recording_status == 'recorded_local',
                Recording.uploaded == True,
                Recording.upload_status == 'completed'
            ).all()
        
        if not outdated_meetings:
            print("✅ No meetings need status updates")
            return
        
        print(f"🔍 Found {len(outdated_meetings)} meetings with outdated status")
        
        for meeting in outdated_meetings:
            old_status = meeting.recording_status
            meeting.recording_status = 'recorded_synced'
            meeting.last_updated = datetime.utcnow()
            print(f"📝 Updated meeting '{meeting.subject}' from '{old_status}' to 'recorded_synced'")
        
        db.session.commit()
        print(f"✅ Successfully updated {len(outdated_meetings)} meeting statuses")

if __name__ == "__main__":
    fix_meeting_statuses()