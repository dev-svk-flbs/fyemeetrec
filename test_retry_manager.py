#!/usr/bin/env python3
"""
Test the retry manager functionality
"""

from retry_manager import get_retry_manager
from background_uploader import get_uploader
import time

def test_retry_manager():
    """Test retry manager basic functionality"""
    
    print("🧪 Testing Retry Manager")
    print("=" * 40)
    
    # Get retry manager instance
    manager = get_retry_manager()
    uploader = get_uploader()
    
    # Get current stats
    stats = manager.get_retry_stats()
    print(f"📊 Current retry stats: {stats}")
    
    # Get failed recordings
    failed_recordings = manager._get_failed_recordings()
    print(f"🔄 Failed recordings eligible for retry: {len(failed_recordings)}")
    
    for recording in failed_recordings:
        print(f"   ID {recording['id']}: {recording['title']} (retry count: {recording.get('retry_count', 0)})")
    
    # Test manual retry
    if failed_recordings:
        print(f"\n🚀 Testing manual retry for all failed uploads...")
        success_count = manager.manual_retry_all_failed()
        print(f"✅ Manual retry triggered: {success_count} uploads started")
        
        # Wait a bit for uploads to start
        print(f"⏳ Waiting 10 seconds for uploads to progress...")
        time.sleep(10)
        
        # Check upload status
        for recording in failed_recordings:
            recording_id = recording['id']
            status = uploader.get_upload_status(recording_id)
            print(f"📊 Recording {recording_id} status: {status.get('status', 'unknown')}")
            
        print(f"\n💡 Note: Background uploads may continue after this test completes")
        
    else:
        print(f"\n✅ No failed uploads to retry")
    
    print(f"\n🔄 Retry manager running: {manager.running}")
    print("🧪 Test completed")

if __name__ == "__main__":
    test_retry_manager()