#!/usr/bin/env python3
"""
Test script for the new WebSocket-based calendar sync
"""

import requests
import json
import time
import os

def test_calendar_sync_request():
    """Test the new calendar sync request API"""
    
    print("🧪 Testing WebSocket-based Calendar Sync")
    print("="*50)
    
    try:
        # Test the new sync request API
        url = "http://localhost:5000/api/request_calendar_sync"
        
        print(f"📤 Sending sync request to: {url}")
        response = requests.post(url, timeout=10)
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Sync request successful!")
            print(f"   Message: {result.get('message')}")
            
            # Check if flag file was created
            flag_file = "sync_request.flag"
            if os.path.exists(flag_file):
                print(f"✅ Flag file created: {flag_file}")
                
                # Read flag file content
                with open(flag_file, 'r') as f:
                    flag_data = json.loads(f.read())
                
                print(f"   Timestamp: {flag_data.get('timestamp')}")
                print(f"   Requested by: {flag_data.get('requested_by')}")
                print(f"   User: {flag_data.get('user_email')}")
                
                print(f"\n💡 WebSocket client should detect this flag and request meetings from server")
                print(f"   Monitor the WebSocket client logs to see the sync process")
                
            else:
                print("⚠️  Flag file not found - may have been processed already")
        else:
            print("❌ Sync request failed!")
            print(f"   Error: {response.text}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

def test_admin_sync_route():
    """Test the admin sync calendar route (requires login)"""
    print(f"\n🧪 Testing Admin Sync Route")
    print("="*30)
    
    try:
        # This would normally require authentication
        url = "http://localhost:5000/admin/sync_calendar"
        
        print(f"📤 Testing admin route: {url}")
        print("   Note: This requires login, will likely return redirect")
        
        response = requests.post(url, timeout=10, allow_redirects=False)
        
        print(f"📥 Response Status: {response.status_code}")
        
        if response.status_code == 302:
            print("✅ Expected redirect (login required)")
            print(f"   Location: {response.headers.get('Location', 'N/A')}")
        elif response.status_code == 200:
            print("✅ Route accessible (user logged in)")
        else:
            print(f"⚠️  Unexpected status: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🧪 WebSocket Calendar Sync Test Suite")
    print("="*60)
    
    # Test the API endpoint
    test_calendar_sync_request()
    
    # Test the admin route
    test_admin_sync_route()
    
    print(f"\n📋 Summary:")
    print(f"   1. The API endpoint creates a flag file for WebSocket client")
    print(f"   2. The WebSocket client monitors for flag files every 5 seconds")
    print(f"   3. When detected, it sends 'request_weekly_meetings' to server")
    print(f"   4. Server responds with weekly meetings data")
    print(f"   5. Client saves meetings to local database via Flask API")
    
    print(f"\n💡 To see the full process:")
    print(f"   1. Start the WebSocket client: python websocket_client.py")
    print(f"   2. Run this test or click 'Sync from Server' in admin interface")
    print(f"   3. Watch WebSocket client logs for sync activity")