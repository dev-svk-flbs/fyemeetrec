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
    webhook_token = "fye_webhook_secure_token_2025_recordings"
    
    # Sample metadata matching your spec with meeting info
    test_data = {
        "recording_id": 999,  # Test ID
        "title": "Test Recording - Webhook Integration with Meeting",
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
        "region": "us-west-1",
        "meeting_info": {
            "meeting_id": 456,
            "subject": "Test Recording - Webhook Integration with Meeting",
            "start_time": "2025-10-27 10:00:00",
            "end_time": "2025-10-27 11:00:00",
            "duration_minutes": 60,
            "organizer": "souvik@fyelabs.com",
            "location": "Microsoft Teams Meeting",
            "web_link": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_test",
            "meeting_type": "teams",
            "is_teams_meeting": True,
            "is_recurring": False,
            "attendee_count": 3,
            "required_attendees": [
                "souvik@fyelabs.com",
                "test@fyelabs.com"
            ],
            "optional_attendees": [
                "observer@fyelabs.com"
            ],
            "calendar_event_id": "test_calendar_event_id_123",
            "discovered_at": "2025-10-26 15:20:00",
            "is_linked_to_meeting": True
        }
    }
    
    print("=" * 60)
    print("TESTING WEBHOOK INTEGRATION WITH AUTHENTICATION")
    print("=" * 60)
    print(f"\nWebhook URL: {webhook_url}")
    print(f"Auth Token: {webhook_token[:20]}...")
    print(f"\nPayload:")
    print(json.dumps(test_data, indent=2))
    print("\n" + "=" * 60)
    print("Sending authenticated request...")
    print("=" * 60)
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Token': webhook_token
            },
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

def test_webhook_standalone_recording():
    """Test webhook for standalone recording (no meeting linked)"""
    
    webhook_url = "https://ops.fyelabs.com/recordings/webhook/"
    webhook_token = "fye_webhook_secure_token_2025_recordings"
    
    # Sample metadata for standalone recording
    test_data = {
        "recording_id": 997,  # Test ID
        "title": "Manual Screen Recording - No Meeting",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "duration_seconds": 1800,
        "duration_database": 1795,
        "user_info": {
            "username": "souvik",
            "email": "souvik@fyelabs.com"
        },
        "file_info": {
            "total_size_mb": 180.25,
            "individual_sizes_mb": {
                "video.mkv": 175.80,
                "transcript.txt": 0.03,
                "thumbnail.jpg": 4.42
            }
        },
        "uploaded_files": {
            "video": "https://s3.us-west-1.idrivee2.com/fyemeet/997/video.mkv",
            "thumbnail": "https://s3.us-west-1.idrivee2.com/fyemeet/997/thumbnail.jpg",
            "transcript": "https://s3.us-west-1.idrivee2.com/fyemeet/997/transcript.txt",
            "metadata": "https://s3.us-west-1.idrivee2.com/fyemeet/997/metadata.json"
        },
        "upload_timestamp": datetime.now().isoformat(),
        "upload_source": "background_thread",
        "bucket_name": "fyemeet",
        "region": "us-west-1",
        "meeting_info": {
            "is_linked_to_meeting": False
        }
    }
    
    print("\n" + "=" * 60)
    print("TESTING STANDALONE RECORDING WEBHOOK")
    print("=" * 60)
    print(f"\nWebhook URL: {webhook_url}")
    print(f"Recording Type: Standalone (No Meeting Linked)")
    print(f"\nPayload Preview:")
    print(json.dumps(test_data, indent=2)[:500] + "...")
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={
                'Content-Type': 'application/json',
                'X-Webhook-Token': webhook_token
            },
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers:")
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
            print("✅ STANDALONE RECORDING WEBHOOK TEST SUCCESSFUL!")
            print("=" * 60)
            return True
        else:
            print("\n" + "=" * 60)
            print("❌ STANDALONE RECORDING WEBHOOK TEST FAILED")
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

def test_webhook_unauthorized():
    """Test webhook without authentication token (should fail)"""
    
    webhook_url = "https://ops.fyelabs.com/recordings/webhook/"
    
    test_data = {
        "recording_id": 998,
        "title": "Unauthorized Test",
        "user_info": {"email": "souvik@fyelabs.com", "username": "souvik"}
    }
    
    print("\n" + "=" * 60)
    print("TESTING UNAUTHORIZED ACCESS (Should Fail)")
    print("=" * 60)
    print("Sending request WITHOUT authentication token...")
    
    try:
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            # No X-Webhook-Token header
            timeout=30
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 401:
            print("\n✅ SECURITY TEST PASSED - Unauthorized request rejected")
            return True
        else:
            print("\n❌ SECURITY WARNING - Unauthorized request was accepted!")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Test with meeting-linked recording
    meeting_success = test_webhook()
    
    # Test standalone recording
    standalone_success = test_webhook_standalone_recording()
    
    # Test without authentication
    unauth_success = test_webhook_unauthorized()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Meeting-linked recording: {'✅ PASS' if meeting_success else '❌ FAIL'}")
    print(f"Standalone recording:     {'✅ PASS' if standalone_success else '❌ FAIL'}")
    print(f"Unauthorized rejection:   {'✅ PASS' if unauth_success else '❌ FAIL'}")
    print("=" * 60)
