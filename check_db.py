#!/usr/bin/env python3
import sqlite3
import os

def check_all_databases():
    db_files = [
        'instance/meetings.db',
        'instance/recordings.db', 
        'instance/recordings-souvikfyenuc.db'
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            print(f"\n{'='*60}")
            print(f"DATABASE: {db_file}")
            print(f"{'='*60}")
            
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print("Tables:")
            for table in tables:
                print(f"  - {table[0]}")
            
            # Check recording table if it exists
            table_names = [table[0] for table in tables]
            if 'recording' in table_names:
                print(f"\nRecent recordings from {db_file}:")
                cursor.execute('''
                    SELECT id, title, status, started_at, ended_at, file_size, created_at
                    FROM recording 
                    ORDER BY id DESC 
                    LIMIT 15
                ''')
                
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        print(f"ID: {row[0]:<3} | {row[1][:40]:<40} | {row[2]:<12} | {row[5] or 0:<8} bytes")
                        print(f"       Started: {row[3]} | Ended: {row[4]}")
                        print(f"       Created: {row[6]}")
                        print("-" * 60)
                        
                    # Check for duplicates from today
                    cursor.execute('''
                        SELECT id, title, started_at, file_size
                        FROM recording 
                        WHERE started_at LIKE '%2025-10-27 00:13%'
                        ORDER BY id
                    ''')
                    
                    duplicates = cursor.fetchall()
                    if duplicates:
                        print(f"\n DUPLICATES from 00:13 timeframe in {db_file}:")
                        for dup in duplicates:
                            print(f"   ID: {dup[0]} | {dup[1]} | {dup[2]} | {dup[3] or 0} bytes")
                else:
                    print("   No recordings found")
            
            conn.close()
        else:
            print(f" Database not found: {db_file}")

if __name__ == "__main__":
    check_all_databases()