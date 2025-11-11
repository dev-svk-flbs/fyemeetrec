#!/usr/bin/env python3
"""
Trigger retry for failed upload
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from background_uploader import get_uploader
    
    print(" Triggering retry for failed upload...")
    
    # Get uploader instance
    uploader = get_uploader()
    
    # Trigger upload for recording ID 1 (the one that failed)
    recording_id = 1
    print(f" Starting background upload for recording {recording_id}...")
    
    success = uploader.upload_recording_async(recording_id)
    
    if success:
        print(f" Upload thread started successfully for recording {recording_id}")
        print(" Check the logs to see upload progress...")
    else:
        print(f" Failed to start upload for recording {recording_id}")
        
except Exception as e:
    print(f" Error: {e}")