#!/usr/bin/env python3
import sqlite3
from datetime import datetime

def fix_stuck_recording():
    conn = sqlite3.connect('instance/recordings.db')
    cursor = conn.cursor()
    
    # Find the stuck recording (ID 6)
    cursor.execute('SELECT id, title, status FROM recording WHERE id = 6')
    stuck_record = cursor.fetchone()
    
    if stuck_record:
        print(f"Found stuck recording: ID={stuck_record[0]}, Title={stuck_record[1]}, Status={stuck_record[2]}")
        
        # Update it to failed status
        cursor.execute('''
            UPDATE recording 
            SET status = 'failed', 
                ended_at = ?, 
                duration = 0 
            WHERE id = 6
        ''', (datetime.utcnow().isoformat(),))
        
        conn.commit()
        print(" Fixed stuck recording - marked as failed")
        
        # Verify the fix
        cursor.execute('SELECT id, title, status, ended_at FROM recording WHERE id = 6')
        fixed_record = cursor.fetchone()
        print(f"After fix: ID={fixed_record[0]}, Status={fixed_record[2]}, Ended={fixed_record[3]}")
    else:
        print("No stuck recording found with ID 6")
    
    conn.close()

if __name__ == "__main__":
    fix_stuck_recording()