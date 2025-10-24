#!/usr/bin/env python3
"""
Check recording database records
"""

from app import app
from models import Recording, db

def check_recordings():
    with app.app_context():
        rec4 = Recording.query.get(4)
        rec5 = Recording.query.get(5)
        
        print("Recording Status Check:")
        print("=" * 40)
        
        if rec4:
            print(f"Recording 4:")
            print(f"  Title: {rec4.title}")
            print(f"  Status: {rec4.status}")
            print(f"  Duration: {rec4.duration or 'N/A'}")
            print(f"  File Path: {rec4.file_path or 'No file'}")
            print(f"  File Size: {rec4.file_size or 0}")
            print(f"  Upload Status: {rec4.upload_status or 'N/A'}")
            print(f"  Uploaded: {rec4.uploaded}")
        else:
            print("Recording 4: Not found")
        
        print()
        
        if rec5:
            print(f"Recording 5:")
            print(f"  Title: {rec5.title}")
            print(f"  Status: {rec5.status}")
            print(f"  Duration: {rec5.duration or 'N/A'}")
            print(f"  File Path: {rec5.file_path or 'No file'}")
            print(f"  File Size: {rec5.file_size or 0}")
            print(f"  Upload Status: {rec5.upload_status or 'N/A'}")
            print(f"  Uploaded: {rec5.uploaded}")
        else:
            print("Recording 5: Not found")

if __name__ == "__main__":
    check_recordings()