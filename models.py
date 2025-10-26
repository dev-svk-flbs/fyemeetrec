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
    
    # Settings
    default_monitor = db.Column(db.String(200))  # Default monitor for recordings
    auto_delete_days = db.Column(db.Integer, default=30)  # Auto-delete recordings after N days
    
    # Relationship to recordings and meetings
    recordings = db.relationship('Recording', backref='user', lazy=True)
    meetings = db.relationship('Meeting', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Meeting(db.Model):
    """Meeting model to track calendar events and their recording status"""
    id = db.Column(db.Integer, primary_key=True)
    
    # Calendar event details
    calendar_event_id = db.Column(db.String(255))  # Original calendar event ID
    subject = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(500))
    web_link = db.Column(db.String(1000))  # Teams meeting link
    
    # Meeting times
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer)
    is_all_day = db.Column(db.Boolean, default=False)
    
    # Attendees
    organizer = db.Column(db.String(255))
    required_attendees = db.Column(db.Text)  # JSON list of email addresses
    optional_attendees = db.Column(db.Text)  # JSON list of email addresses
    attendee_count = db.Column(db.Integer, default=0)
    
    # Meeting metadata
    meeting_type = db.Column(db.String(50), default='teams')  # teams, phone, in-person, other
    is_teams_meeting = db.Column(db.Boolean, default=False)
    is_recurring = db.Column(db.Boolean, default=False)
    
    # Recording tracking
    recording_status = db.Column(db.String(50), default='none')  # none, scheduled, recorded_local, recorded_synced, excluded
    recording_id = db.Column(db.Integer, db.ForeignKey('recording.id'), nullable=True)  # One-to-one relationship
    recording = db.relationship('Recording', backref='meeting', uselist=False)  # One meeting can have 0 or 1 recording
    
    # Auto-discovery and management
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Status and flags
    is_excluded = db.Column(db.Boolean, default=False)  # User manually excluded from recording
    auto_record = db.Column(db.Boolean, default=True)  # Should this meeting be auto-recorded
    
    @property
    def duration_formatted(self):
        """Format duration as HH:MM:SS"""
        if not self.duration_minutes:
            return "00:00"
        
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}"
        else:
            return f"{minutes:02d}m"
    
    @property
    def attendee_list(self):
        """Parse required attendees from JSON"""
        try:
            import json
            if self.required_attendees:
                return json.loads(self.required_attendees)
        except:
            pass
        return []
    
    @property
    def optional_attendee_list(self):
        """Parse optional attendees from JSON"""
        try:
            import json
            if self.optional_attendees:
                return json.loads(self.optional_attendees)
        except:
            pass
        return []
    
    @property
    def all_attendees(self):
        """Get all attendees (required + optional)"""
        return self.attendee_list + self.optional_attendee_list
    
    @property
    def status_display(self):
        """Get human-readable status"""
        status_map = {
            'none': 'No Recording',
            'scheduled': 'Scheduled',
            'recorded_local': 'Recorded (Local)',
            'recorded_synced': 'Recorded & Synced',
            'excluded': 'Excluded'
        }
        return status_map.get(self.recording_status, 'Unknown')
    
    @property
    def status_class(self):
        """Get CSS class for status display"""
        class_map = {
            'none': 'status-none',
            'scheduled': 'status-scheduled',
            'recorded_local': 'status-recorded-local',
            'recorded_synced': 'status-recorded-synced',
            'excluded': 'status-excluded'
        }
        return class_map.get(self.recording_status, 'status-none')
    
    @property
    def is_past(self):
        """Check if meeting is in the past"""
        return self.end_time < datetime.utcnow()
    
    @property
    def is_today(self):
        """Check if meeting is today"""
        today = datetime.utcnow().date()
        return self.start_time.date() == today
    
    @property
    def is_upcoming(self):
        """Check if meeting is upcoming (in the future)"""
        return self.start_time > datetime.utcnow()
    
    def set_attendees(self, required_list=None, optional_list=None):
        """Set attendees from lists"""
        import json
        if required_list:
            self.required_attendees = json.dumps(required_list)
        if optional_list:
            self.optional_attendees = json.dumps(optional_list)
        
        # Update count
        total_count = len(required_list or []) + len(optional_list or [])
        self.attendee_count = total_count
    
    def update_recording_status(self):
        """Update recording status based on associated recording"""
        if self.recording:
            if self.recording.has_cloud_backup:
                self.recording_status = 'recorded_synced'
            else:
                self.recording_status = 'recorded_local'
        elif self.is_excluded:
            self.recording_status = 'excluded'
        elif self.auto_record and self.is_upcoming:
            self.recording_status = 'scheduled'
        else:
            self.recording_status = 'none'
    
    def __repr__(self):
        return f'<Meeting {self.subject} on {self.start_time.strftime("%Y-%m-%d %H:%M")}>'

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
    upload_url = db.Column(db.String(500))  # Legacy field - kept for compatibility
    
    # IDrive E2 Upload URLs
    video_url = db.Column(db.String(500))
    transcript_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    
    # Upload tracking
    upload_status = db.Column(db.String(50), default='pending')  # pending, uploading, completed, failed
    upload_metadata = db.Column(db.Text)  # JSON metadata from upload
    
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
    
    @property
    def sync_status(self):
        """Get sync status display text"""
        if self.upload_status == 'completed' and self.uploaded:
            return "Synced"
        elif self.upload_status == 'uploading':
            return "Uploading"
        elif self.upload_status == 'failed':
            return "Upload Failed"
        elif self.status == "failed":
            return "Recording Failed"
        elif self.status == "processing":
            return "Processing"
        else:
            return "Local Only"
    
    @property
    def sync_status_class(self):
        """Get CSS class for sync status"""
        status = self.sync_status
        if status == "Synced":
            return "status-synced"
        elif status == "Uploading":
            return "status-uploading"
        elif "Failed" in status:
            return "status-failed"
        elif status == "Processing":
            return "status-processing"
        else:
            return "status-local"
    
    @property
    def resolved_file_path(self):
        """Get the correct file path for the current machine/user"""
        if not self.file_path:
            return None
            
        # Get the current project directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check if file_path is already just a filename (new format)
        if os.path.isabs(self.file_path):
            # Old format: full path stored - extract filename
            filename = os.path.basename(self.file_path)
        else:
            # New format: just filename stored
            filename = self.file_path
        
        # Build the correct path for this machine
        resolved_path = os.path.join(current_dir, 'recordings', filename)
        
        return resolved_path
    
    @property
    def file_exists(self):
        """Check if the file exists at the resolved path"""
        resolved_path = self.resolved_file_path
        return resolved_path and os.path.exists(resolved_path)
    
    @property
    def transcript_path(self):
        """Get transcript file path"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        recordings_dir = os.path.join(current_dir, 'recordings')
        
        # First try the new naming scheme (based on title)
        safe_title = "".join(c for c in self.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        transcript_filename = f"{safe_title}_transcript.txt"
        transcript_path = os.path.join(recordings_dir, transcript_filename)
        
        if os.path.exists(transcript_path):
            return transcript_path
        
        # Fall back to old naming scheme (based on video file)
        resolved_path = self.resolved_file_path
        if resolved_path:
            old_transcript_path = os.path.splitext(resolved_path)[0] + '_transcript.txt'
            if os.path.exists(old_transcript_path):
                return old_transcript_path
        
        # Return the new path even if it doesn't exist yet (for creation)
        return transcript_path
    
    @property
    def has_transcript(self):
        """Check if transcript file exists"""
        transcript_path = self.transcript_path
        return transcript_path and os.path.exists(transcript_path)
    
    @property
    def has_cloud_backup(self):
        """Check if recording has been uploaded to cloud"""
        return self.uploaded and self.upload_status == 'completed' and self.video_url
    
    @property
    def cloud_video_url(self):
        """Get cloud video URL if available"""
        return self.video_url if self.has_cloud_backup else None
    
    @property
    def cloud_thumbnail_url(self):
        """Get cloud thumbnail URL if available"""
        return self.thumbnail_url if self.has_cloud_backup else None
    
    @property
    def cloud_transcript_url(self):
        """Get cloud transcript URL if available"""
        return self.transcript_url if self.has_cloud_backup else None
    
    def get_upload_progress(self):
        """Get upload progress from metadata if available"""
        try:
            if self.upload_metadata:
                import json
                metadata = json.loads(self.upload_metadata)
                return metadata.get('upload_progress', {})
        except:
            pass
        return {}
    
    def __repr__(self):
        return f'<Recording {self.title}>'

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # No automatic user creation - let the setup page handle first-time user creation