#!/usr/bin/env python3
"""
Test script to debug user info detection
"""

import requests
import json
import time

def test_current_user_api():
    """Test the current user API endpoint"""
    
    print("🧪 Testing Current User API")
    print("="*40)
    
    try:
        url = "http://localhost:5000/api/current_user"
        
        print(f"📤 Testing: {url}")
        response = requests.get(url, timeout=5)
        
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API Response:")
            print(f"   Logged in: {data.get('logged_in')}")
            
            if data.get('logged_in'):
                print(f"   Username: {data.get('username')}")
                print(f"   Email: {data.get('email')}")
                print(f"   User ID: {data.get('user_id')}")
            else:
                print("   No user logged in")
        else:
            print(f"❌ API Error: {response.text}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

def test_app_health_api():
    """Test the app health API endpoint"""
    
    print(f"\n🧪 Testing App Health API")
    print("="*30)
    
    try:
        url = "http://localhost:5000/api/health"
        
        print(f"📤 Testing: {url}")
        response = requests.get(url, timeout=5)
        
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health Response:")
            print(f"   Alive: {data.get('alive')}")
            print(f"   Recording Active: {data.get('recording_active')}")
            print(f"   Recording Type: {data.get('recording_type')}")
            print(f"   Timestamp: {data.get('timestamp')}")
            
            if data.get('meeting'):
                print(f"   Meeting: {data.get('meeting')}")
        else:
            print(f"❌ Health API Error: {response.text}")
    
    except Exception as e:
        print(f"❌ Error: {e}")

def continuous_user_check():
    """Continuously check user status to see if it changes"""
    
    print(f"\n🧪 Continuous User Status Monitor")
    print("="*40)
    print("Press Ctrl+C to stop")
    
    previous_status = None
    
    try:
        while True:
            try:
                response = requests.get("http://localhost:5000/api/current_user", timeout=2)
                
                if response.status_code == 200:
                    data = response.json()
                    current_status = {
                        'logged_in': data.get('logged_in'),
                        'email': data.get('email'),
                        'username': data.get('username')
                    }
                    
                    if current_status != previous_status:
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"[{timestamp}] 🔄 Status changed:")
                        
                        if current_status['logged_in']:
                            print(f"   ✅ User logged in: {current_status['username']} ({current_status['email']})")
                        else:
                            print(f"   ❌ No user logged in")
                        
                        previous_status = current_status
                    else:
                        # Just show a heartbeat every 10 seconds
                        if int(time.time()) % 10 == 0:
                            timestamp = time.strftime("%H:%M:%S")
                            if current_status['logged_in']:
                                print(f"[{timestamp}] 💓 User online: {current_status['email']}")
                            else:
                                print(f"[{timestamp}] 💓 No user")
                
                time.sleep(1)
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(1)
    
    except KeyboardInterrupt:
        print(f"\n👋 Stopping monitor")

if __name__ == "__main__":
    print("🧪 User Info Debug Suite")
    print("="*50)
    
    # Test current user API
    test_current_user_api()
    
    # Test health API
    test_app_health_api()
    
    # Continuous monitoring
    continuous_user_check()