#!/usr/bin/env python3
import sqlite3
from datetime import datetime

def check_duplicates():
    conn = sqlite3.connect('instance/meetings.db')
    cursor = conn.cursor()
    
    # Get recent recordings
    cursor.execute('''
        SELECT id, title, recording_status, start_time, end_time, file_size, created_at
        FROM recording 
        ORDER BY id DESC 
        LIMIT 10
    ''')
    
    rows = cursor.fetchall()
    print("Recent recordings:")
    print("=" * 80)
    
    for row in rows:
        print(f"ID: {row[0]:<3} | Title: {row[1]:<30} | Status: {row[2]:<10} | Size: {row[5] or 0:<8} bytes")
        print(f"      Start: {row[3]} | End: {row[4]}")
        print(f"      Created: {row[6]}")
        print("-" * 80)
    
    # Check for potential duplicates around the same time
    cursor.execute('''
        SELECT id, title, start_time, file_size
        FROM recording 
        WHERE start_time LIKE '%2025-10-27 00:13%'
        ORDER BY id
    ''')
    
    duplicates = cursor.fetchall()
    if duplicates:
        print("\nPotential duplicates from 00:13 timeframe:")
        print("=" * 50)
        for dup in duplicates:
            print(f"ID: {dup[0]} | Title: {dup[1]} | Start: {dup[2]} | Size: {dup[3] or 0} bytes")
    
    conn.close()

if __name__ == "__main__":
    check_duplicates()