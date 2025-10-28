#!/usr/bin/env python3
"""
Initialize database for WebSocket client
This ensures the database tables exist before the client tries to query them
"""

import os
from flask import Flask
from models import db, init_db

# Create a minimal Flask app just to initialize the database
app = Flask(__name__)

# Database configuration
instance_path = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(instance_path, exist_ok=True)

db_path = os.path.join(instance_path, 'meetings.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

print("="*60)
print("🗄️  Initializing Database for WebSocket Client")
print("="*60)
print(f"📂 Database path: {db_path}")

# Initialize database
init_db(app)

print("✅ Database initialized successfully!")
print(f"📊 Database file created at: {db_path}")

# Check tables
with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"\n📋 Tables created:")
    for table in tables:
        print(f"   ✓ {table}")

print("\n✅ Ready for WebSocket client!")
