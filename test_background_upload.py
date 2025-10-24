#!/usr/bin/env python3
"""
Test Background Upload Functionality
"""

import os
import sys
import time
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

def test_background_upload():
    """Test the background upload functionality"""
    
    try:
        from background_uploader import get_uploader, trigger_upload
        print("✅ Successfully imported background uploader")
        
        # Get uploader instance
        uploader = get_uploader()
        print("✅ Got uploader instance")
        
        # Test connection to IDrive E2
        try:
            s3_client = uploader._get_s3_client()
            print("✅ IDrive E2 connection successful")
        except Exception as e:
            print(f"❌ IDrive E2 connection failed: {e}")
            print("⚠️ Make sure AWS credentials are configured for IDrive E2")
            return False
        
        # Check for existing recordings
        try:
            conn = uploader._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, upload_status FROM recording ORDER BY id DESC LIMIT 5")
            recordings = cursor.fetchall()
            conn.close()
            
            if not recordings:
                print("❌ No recordings found in database")
                return False
            
            print(f"📊 Found {len(recordings)} recent recording(s):")
            for rec in recordings:
                print(f"   ID: {rec[0]}, Title: {rec[1]}, Upload Status: {rec[2] or 'None'}")
            
            # Test with the most recent recording
            test_recording_id = recordings[0][0]
            print(f"\n🧪 Testing upload with recording ID: {test_recording_id}")
            
            # Check current status
            status = uploader.get_upload_status(test_recording_id)
            print(f"📋 Current upload status: {status}")
            
            # Trigger upload
            print(f"🚀 Triggering background upload...")
            success = trigger_upload(test_recording_id)
            
            if success:
                print("✅ Upload triggered successfully!")
                print("⏳ Upload is running in background...")
                
                # Monitor progress for a short time
                for i in range(10):
                    time.sleep(2)
                    status = uploader.get_upload_status(test_recording_id)
                    print(f"📊 Status update {i+1}: {status.get('status', 'unknown')}")
                    
                    if status.get('status') in ['completed', 'failed']:
                        break
                
                print("✅ Test completed!")
                return True
            else:
                print("❌ Failed to trigger upload")
                return False
                
        except Exception as e:
            print(f"❌ Database error: {e}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Background Upload System")
    print("=" * 50)
    
    success = test_background_upload()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Background upload test completed!")
    else:
        print("💥 Background upload test failed!")
    
    input("Press Enter to continue...")