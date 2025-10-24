#!/usr/bin/env python3

from app import app, db, get_single_user

def test_single_user():
    with app.app_context():
        print("🧪 Testing single user system...")
        
        # Get or create the single user
        user = get_single_user()
        
        if user:
            print(f"✅ Single user found/created: {user.username} (ID: {user.id})")
            print(f"   Email: {user.email}")
            print(f"   Active: {user.is_active}")
        else:
            print("❌ Failed to get/create single user")

if __name__ == "__main__":
    test_single_user()