#!/usr/bin/env python3
"""
Fix orphaned recording - update recording 5 status
"""

from app import app
from models import Recording, db
from datetime import datetime

def fix_orphaned_recording():
    with app.app_context():
        # Get the orphaned recording
        rec5 = Recording.query.get(5)
        
        if rec5 and rec5.status == 'recording':
            print(f"Found orphaned recording: {rec5.title}")
            print(f"Current status: {rec5.status}")
            
            # Update to failed status since it has no file
            rec5.status = 'failed'
            rec5.ended_at = datetime.utcnow()
            rec5.upload_status = 'failed'
            
            # Save changes
            db.session.commit()
            
            print("✅ Updated orphaned recording to 'failed' status")
            print(f"   Status: {rec5.status}")
            print(f"   Upload Status: {rec5.upload_status}")
            print(f"   Ended At: {rec5.ended_at}")
            
        else:
            print("No orphaned recording found or already fixed")

if __name__ == "__main__":
    fix_orphaned_recording()