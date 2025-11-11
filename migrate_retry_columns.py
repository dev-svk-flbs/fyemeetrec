#!/usr/bin/env python3
"""
Database migration to add retry tracking columns
"""

import sqlite3
from pathlib import Path
from logging_config import app_logger as logger

def migrate_add_retry_columns():
    """Add retry tracking columns to the recording table"""
    
    # Get database path
    current_dir = Path(__file__).parent.absolute()
    db_path = current_dir / 'instance' / 'recordings.db'
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(recording)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations_needed = []
        
        if 'retry_count' not in columns:
            migrations_needed.append("ALTER TABLE recording ADD COLUMN retry_count INTEGER DEFAULT 0")
        
        if 'last_retry_at' not in columns:
            migrations_needed.append("ALTER TABLE recording ADD COLUMN last_retry_at TEXT")
        
        if not migrations_needed:
            logger.info(" Database already has retry tracking columns")
            conn.close()
            return True
        
        # Execute migrations
        for migration in migrations_needed:
            logger.info(f" Executing: {migration}")
            cursor.execute(migration)
        
        conn.commit()
        conn.close()
        
        logger.info(f" Database migration completed: {len(migrations_needed)} columns added")
        return True
        
    except Exception as e:
        logger.error(f" Database migration failed: {e}")
        return False

if __name__ == "__main__":
    migrate_add_retry_columns()