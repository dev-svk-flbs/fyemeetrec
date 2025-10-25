#!/usr/bin/env python3
"""
Test script for Django webhook integration
"""

import requests
import json
from datetime import datetime

def test_webhook():
    """Test sending webhook to Django server"""
    
    webhook_url = "https://ops.fyelabs.com/recordings/webhook/"
    
    # Sample metadata matching your spec
    test_data = {
        "recording_id": 999,  # Test ID
        "title": "Test Recording - Webhook Integration",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration_seconds": 120,
        "duration_database": 120,
        "user_info": {
            "username": "souvik",
            "email": "souvik@fyelabs.com"
        },
        "file_info": {
            "total_size_mb": 1.5,
            "individual_sizes_mb": {
                "video.mkv": 1.2,
                "thumbnail.jpg": 0.02,
                "transcript.txt": 0.01
            }
        },
        "uploaded_files": {
            "video": "https://s3.us-west-1.idrivee2.com/fyemeet/999/video.mkv",
            "thumbnail": "https://s3.us-west-1.idrivee2.com/fyemeet/999/thumbnail.jpg",
            "transcript": "https://s3.us-west-1.idrivee2.com/fyemeet/999/transcript.txt",
            "metadata": "https://s3.us-west-1.idrivee2.com/fyemeet/999/metadata.json"
        },
        "upload_timestamp": datetime.now().isoformat(),
        "upload_source": "test_script",
        "bucket_name": "fyemeet",
        "region": "us-west-1"
    }
    
    print("=" * 60)
    print("TESTING WEBHOOK INTEGRATION")
    print("=" * 60)
    print(f"\nWebhook URL: {webhook_url}")
    print(f"\nPayload:")
    print(json.dumps(test_data, indent=2))
    print("\n" + "=" * 60)
    print("Sending request...")
    print("=" * 60)
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"\n✅ Response Status: {response.status_code}")
        print(f"\nResponse Headers:")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")
        
        print(f"\nResponse Body:")
        try:
            response_json = response.json()
            print(json.dumps(response_json, indent=2))
        except:
            print(response.text)
        
        if response.status_code in [200, 201]:
            print("\n" + "=" * 60)
            print("✅ WEBHOOK TEST SUCCESSFUL!")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ WEBHOOK TEST FAILED")
            print("=" * 60)
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Request timeout after 30 seconds")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_webhook()
