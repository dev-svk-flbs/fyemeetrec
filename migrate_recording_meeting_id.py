#!/usr/bin/env python3
"""
Migration script to add meeting_id column to Recording table
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from sqlalchemy import text

def add_meeting_id_column():
    """Add meeting_id column to Recording table if it doesn't exist"""
    try:
        with app.app_context():
            # Check if column already exists
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('recording')]
            
            if 'meeting_id' not in columns:
                print("Adding meeting_id column to Recording table...")
                
                # Use raw SQL to add the column with proper SQLAlchemy 2.x syntax
                with db.engine.connect() as connection:
                    connection.execute(text('ALTER TABLE recording ADD COLUMN meeting_id INTEGER REFERENCES meeting(id)'))
                    connection.commit()
                
                print(" Successfully added meeting_id column to Recording table")
            else:
                print(" meeting_id column already exists in Recording table")
    
    except Exception as e:
        print(f" Error adding meeting_id column: {e}")
        return False
    
    return True

if __name__ == '__main__':
    print(" Starting Recording table migration...")
    success = add_meeting_id_column()
    
    if success:
        print(" Migration completed successfully!")
    else:
        print(" Migration failed!")
        sys.exit(1)