#!/usr/bin/env python3
"""
Database Migration Script for IDrive E2 Upload Support
"""

import sqlite3
import os
from pathlib import Path

def migrate_database():
    """Add new columns for IDrive E2 upload support"""
    
    # Get database path
    current_dir = Path(__file__).parent.absolute()
    db_path = current_dir / 'instance' / 'recordings.db'
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print(f"🔍 Checking database schema at: {db_path}")
        
        # Check current schema
        cursor.execute("PRAGMA table_info(recording)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"📋 Current columns: {columns}")
        
        migrations_needed = []
        
        # Check for new columns that need to be added
        new_columns = {
            'video_url': 'VARCHAR(500)',
            'transcript_url': 'VARCHAR(500)', 
            'thumbnail_url': 'VARCHAR(500)',
            'upload_status': "VARCHAR(50) DEFAULT 'pending'",
            'upload_metadata': 'TEXT'
        }
        
        for column_name, column_type in new_columns.items():
            if column_name not in columns:
                migrations_needed.append((column_name, column_type))
        
        if not migrations_needed:
            print("✅ Database schema is already up to date!")
            return True
        
        print(f"🔄 Need to add {len(migrations_needed)} columns:")
        for column_name, column_type in migrations_needed:
            print(f"   - {column_name} ({column_type})")
        
        # Apply migrations
        for column_name, column_type in migrations_needed:
            try:
                alter_query = f"ALTER TABLE recording ADD COLUMN {column_name} {column_type}"
                print(f"🔧 Adding column: {alter_query}")
                cursor.execute(alter_query)
                print(f"✅ Added column: {column_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    print(f"⚠️ Column {column_name} already exists, skipping")
                else:
                    print(f"❌ Failed to add column {column_name}: {e}")
                    raise
        
        conn.commit()
        
        # Verify migrations
        cursor.execute("PRAGMA table_info(recording)")
        new_columns_list = [column[1] for column in cursor.fetchall()]
        print(f"📋 Updated columns: {new_columns_list}")
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM recording")
        record_count = cursor.fetchone()[0]
        print(f"📊 Database contains {record_count} recording(s)")
        
        conn.close()
        
        print("✅ Database migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting database migration for IDrive E2 support...")
    success = migrate_database()
    if success:
        print("🎉 Migration completed successfully!")
    else:
        print("💥 Migration failed!")
    input("Press Enter to continue...")