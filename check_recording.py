#!/usr/bin/env python3
"""
Check recording data after upload
"""
import sqlite3
import json

def check_recording_data():
    conn = sqlite3.connect('instance/recordings.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, uploaded, upload_status, video_url, transcript_url, 
               thumbnail_url, upload_metadata 
        FROM recording 
        WHERE id = 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        print("📊 Recording Data:")
        print(f"  ID: {result[0]}")
        print(f"  Title: {result[1]}")
        print(f"  Uploaded: {result[2]}")
        print(f"  Upload Status: {result[3]}")
        print(f"  Video URL: {result[4]}")
        print(f"  Transcript URL: {result[5]}")
        print(f"  Thumbnail URL: {result[6]}")
        
        if result[7]:
            print("\n📋 Upload Metadata:")
            try:
                metadata = json.loads(result[7])
                print(json.dumps(metadata, indent=2))
            except:
                print("  (Invalid JSON)")
        else:
            print("\n📋 No upload metadata")
    else:
        print("❌ Recording not found")

if __name__ == "__main__":
    check_recording_data()