#!/usr/bin/env python3
"""
Test script to verify the background uploader fix
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from background_uploader import get_uploader
    
    print("✅ Testing background uploader fix...")
    
    # Get uploader instance
    uploader = get_uploader()
    print("✅ Uploader instance created")
    
    # Test database connection
    try:
        conn = uploader._get_db_connection()
        cursor = conn.cursor()
        
        # Check if recordings exist
        cursor.execute("SELECT COUNT(*) FROM recording")
        recording_count = cursor.fetchone()[0]
        print(f"📊 Found {recording_count} recordings in database")
        
        if recording_count > 0:
            # Test the fixed query
            cursor.execute("SELECT id FROM recording LIMIT 1")
            test_id = cursor.fetchone()[0]
            
            print(f"🧪 Testing _get_recording_info with recording ID {test_id}...")
            
            # Test the actual function
            recording_info = uploader._get_recording_info(test_id)
            
            if recording_info:
                print("✅ SUCCESS! Recording info retrieved successfully")
                print(f"   Recording title: {recording_info.get('title', 'N/A')}")
                print(f"   Meeting linked: {'Yes' if recording_info.get('meeting_id') else 'No'}")
                if recording_info.get('meeting_id'):
                    print(f"   Meeting subject: {recording_info.get('meeting_subject', 'N/A')}")
            else:
                print("❌ FAILED: Could not retrieve recording info")
        else:
            print("ℹ️ No recordings found to test with")
            
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        
except Exception as e:
    print(f"❌ Import or setup error: {e}")
    print("Make sure you're running this from the correct directory")