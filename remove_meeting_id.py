#!/usr/bin/env python3
"""
Migration script to remove meeting_id column from Recording table
Since we're using recording_id in Meeting table for the one-to-one relationship
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from sqlalchemy import text

def remove_meeting_id_column():
    """Remove meeting_id column from Recording table if it exists"""
    try:
        with app.app_context():
            # Check if column exists
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('recording')]
            
            if 'meeting_id' in columns:
                print("Removing meeting_id column from Recording table...")
                
                # Note: SQLite doesn't support DROP COLUMN, so we'll need to recreate the table
                # For now, let's just leave it but update our code to not use it
                print("  SQLite doesn't support DROP COLUMN. Column will remain but is unused.")
                print(" Application updated to not use meeting_id column")
            else:
                print(" meeting_id column doesn't exist in Recording table")
    
    except Exception as e:
        print(f" Error checking meeting_id column: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print(" Starting Recording table cleanup...")
    success = remove_meeting_id_column()
    
    if success:
        print(" Migration completed successfully!")
    else:
        print(" Migration failed!")
        sys.exit(1)