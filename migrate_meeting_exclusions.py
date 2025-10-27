#!/usr/bin/env python3
"""
Database migration to add user exclusion fields to Meeting table
"""

import sqlite3
from pathlib import Path

def migrate_add_exclusion_fields():
    """Add user_excluded, exclude_all_series, and series_id fields to Meeting table"""
    try:
        # Get database path
        current_dir = Path(__file__).parent.absolute()
        db_path = current_dir / 'instance' / 'recordings.db'
        
        if not db_path.exists():
            print(f"❌ Database not found at {db_path}")
            return False
        
        print(f"🗄️ Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(meeting)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'user_excluded' not in columns:
            migrations_needed.append(('user_excluded', 'BOOLEAN DEFAULT 0'))
        
        if 'exclude_all_series' not in columns:
            migrations_needed.append(('exclude_all_series', 'BOOLEAN DEFAULT 0'))
        
        if 'series_id' not in columns:
            migrations_needed.append(('series_id', 'VARCHAR(255)'))
        
        if not migrations_needed:
            print("✅ All exclusion columns already exist. No migration needed.")
            conn.close()
            return True
        
        # Add missing columns
        for column_name, column_type in migrations_needed:
            print(f"➕ Adding column: {column_name} ({column_type})")
            cursor.execute(f"ALTER TABLE meeting ADD COLUMN {column_name} {column_type}")
        
        conn.commit()
        
        print(f"✅ Migration completed! Added {len(migrations_needed)} column(s):")
        for column_name, _ in migrations_needed:
            print(f"   - {column_name}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Meeting Exclusion Fields Migration")
    print("=" * 60)
    migrate_add_exclusion_fields()
    print("=" * 60)
