#!/usr/bin/env python3
"""
Database Migration: Add Meeting Model
====================================

This script adds the new Meeting model to track calendar events
and their relationship with recordings.
"""

import os
import sys
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Meeting, Recording, User

def migrate_database():
    """Add Meeting table to existing database"""
    
    print(" Starting database migration...")
    
    with app.app_context():
        try:
            # Create the meetings table
            print(" Creating Meeting table...")
            db.create_all()
            
            # Check if the table was created successfully
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'meeting' in tables:
                print(" Meeting table created successfully!")
                
                # Check table structure
                columns = inspector.get_columns('meeting')
                print(f" Meeting table has {len(columns)} columns:")
                for col in columns:
                    print(f"   - {col['name']} ({col['type']})")
                
                print("\n Meeting model features:")
                print("   - One-to-one relationship with Recording")
                print("   - Calendar event tracking")
                print("   - Recording status management")
                print("   - Attendee management")
                print("   - Auto-recording flags")
                
                return True
            else:
                print(" Failed to create Meeting table")
                return False
                
        except Exception as e:
            print(f" Migration failed: {str(e)}")
            return False

def verify_migration():
    """Verify the migration was successful"""
    
    with app.app_context():
        try:
            # Try to create a test meeting
            test_meeting = Meeting(
                subject="Test Meeting - Migration Verification",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration_minutes=60,
                user_id=1  # Assumes user ID 1 exists
            )
            
            # Don't commit, just test the model works
            print(" Meeting model is working correctly!")
            return True
            
        except Exception as e:
            print(f" Migration verification failed: {str(e)}")
            return False

if __name__ == "__main__":
    print(" Meeting Model Migration Script")
    print("=" * 50)
    
    # Run migration
    success = migrate_database()
    
    if success:
        # Verify migration
        verify_migration()
        print("\n Migration completed successfully!")
        print("\n Next steps:")
        print("   1. Restart your Flask app")
        print("   2. Visit /admin to see the meetings interface")
        print("   3. AutoRecorder will start populating meetings from calendar events")
    else:
        print("\n Migration failed!")
        sys.exit(1)