#!/usr/bin/env python3
"""
Database models for Meeting Recorder
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationship to recordings
    recordings = db.relationship('Recording', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Recording(db.Model):
    """Recording model to track meeting recordings"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.BigInteger, default=0)  # in bytes
    duration = db.Column(db.Integer, default=0)  # in seconds
    
    # Recording metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    
    # Monitor and quality info
    monitor_name = db.Column(db.String(200))
    resolution = db.Column(db.String(50))  # e.g., "1920x1080"
    
    # Upload status
    uploaded = db.Column(db.Boolean, default=False)
    upload_url = db.Column(db.String(500))
    
    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Status
    status = db.Column(db.String(50), default='completed')  # recording, processing, completed, failed
    
    @property
    def duration_formatted(self):
        """Format duration as HH:MM:SS"""
        if not self.duration:
            return "00:00:00"
        
        hours = self.duration // 3600
        minutes = (self.duration % 3600) // 60
        seconds = self.duration % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @property
    def file_size_formatted(self):
        """Format file size in human readable format"""
        if not self.file_size:
            return "0 B"
        
        size = self.file_size  # Work with a copy to avoid modifying the actual value
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
    
    @property
    def thumbnail_path(self):
        """Generate thumbnail path (placeholder for now)"""
        return "/static/img/video-placeholder.jpg"
    
    def __repr__(self):
        return f'<Recording {self.title}>'

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Create default admin user if none exists
        if not User.query.first():
            admin = User(
                username='admin',
                email='admin@fyemeetings.com'
            )
            admin.set_password('admin123')  # Change this in production!
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin user created (admin/admin123)")