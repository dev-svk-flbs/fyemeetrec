#!/usr/bin/env python3
"""
Flask Web Interface for Dual Stream Recording with Authentication
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, send_file, abort, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import pytz
from dual_stream import DualModeStreamer
from models import db, User, Recording, Meeting, init_db
from settings_config import settings_manager
from logging_config import app_logger as logger
from retry_manager import start_retry_manager, get_retry_manager
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import threading
import time
import atexit
import subprocess
import json
import re
import os
import mimetypes
from pathlib import Path
#test
def get_ffmpeg_path():
    """Get the path to the local FFmpeg executable"""
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    ffmpeg_path = script_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
    
    if ffmpeg_path.exists():
        return str(ffmpeg_path)
    else:
        # Fallback to system FFmpeg if local not found
        return "ffmpeg"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'  # Change this!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recordings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Timezone Configuration
UTC = pytz.UTC
EASTERN = pytz.timezone('US/Eastern')

def convert_utc_to_eastern(utc_dt):
    """Convert UTC datetime to Eastern time"""
    if utc_dt is None:
        return None
    
    # If datetime is naive, assume it's UTC
    if utc_dt.tzinfo is None:
        utc_dt = UTC.localize(utc_dt)
    
    # Convert to Eastern time
    eastern_dt = utc_dt.astimezone(EASTERN)
    return eastern_dt

def parse_calendar_datetime(datetime_str):
    """Parse datetime string from calendar and convert to Eastern time"""
    if not datetime_str:
        return None
    
    try:
        # Parse the datetime string (remove microseconds if present)
        clean_str = datetime_str.replace('.0000000', '')
        if clean_str.endswith('Z'):
            # UTC time
            utc_dt = datetime.fromisoformat(clean_str[:-1])
            utc_dt = UTC.localize(utc_dt)
        else:
            # Assume UTC if no timezone info
            utc_dt = datetime.fromisoformat(clean_str)
            if utc_dt.tzinfo is None:
                utc_dt = UTC.localize(utc_dt)
        
        # Convert to Eastern time
        eastern_dt = utc_dt.astimezone(EASTERN)
        # Return naive datetime in Eastern time for database storage
        return eastern_dt.replace(tzinfo=None)
    
    except Exception as e:
        logger.error(f"Failed to parse datetime {datetime_str}: {e}")
        return None

# Power Automate Configuration
WORKFLOW_URL = "https://default27828ac15d864f46abfd89560403e7.89.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/eaf1261797f54ecd875b16b92047518f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=u4zF0dj8ImUdRzDQayjczqITduEt2lDrCx1KzEJInFg"
CALENDAR_ID = "AQMkADBjYWZhZWI5LTE2ZmItNDUyNy1iNDA4LTY0M2NmOTE0YmU3NwAARgAAA0x0AMwFqHZHtaHN6whvT4UHAGZu2hZpbwRNmdBVsXEd-pIAAAIBBgAAAGZu2hZpbwRNmdBVsXEd-pIAAAJdWQAAAA=="

# Disable Flask request logging spam
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Log Flask app initialization
logger.info("🌐 Flask app initializing...")

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None  # Disable automatic login messages
login_manager.login_message_category = 'info'

# Initialize database
init_db(app)
logger.info("🗄️ Database initialized")

# Jinja2 template filters for timezone handling
@app.template_filter('to_eastern')
def to_eastern_filter(utc_dt):
    """Convert UTC datetime to Eastern time for display"""
    return convert_utc_to_eastern(utc_dt)

@app.template_filter('format_eastern_datetime')
def format_eastern_datetime_filter(utc_dt, format_str='%a, %b %d, %H:%M EST'):
    """Format datetime in Eastern time as 'MON, OCT 27, hh:mm EST'"""
    eastern_dt = convert_utc_to_eastern(utc_dt)
    if eastern_dt:
        # Format as "MON, OCT 27, hh:mm EST"
        formatted = eastern_dt.strftime(format_str).upper()
        return formatted
    return 'N/A'

@app.template_filter('format_eastern_local')
def format_eastern_local_filter(local_dt, format_str='%a, %b %d, %I:%M %p EST'):
    """Format datetime that's already in Eastern time in human-readable format"""
    if local_dt:
        # This datetime is already in Eastern time, just format it
        # %a = Mon, %b = Oct, %d = 27, %I = 12-hour, %M = minutes, %p = AM/PM
        formatted = local_dt.strftime(format_str).upper()
        return formatted
    return 'N/A'

# Run database migration for retry columns
try:
    from migrate_retry_columns import migrate_add_retry_columns
    migrate_add_retry_columns()
except Exception as e:
    logger.warning(f"⚠️ Database migration check failed: {e}")

# Utility functions for both Python code and templates
def format_file_size(size_bytes):
    """Format file size in human readable format"""
    if not size_bytes:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"

def format_duration(seconds):
    """Format duration as HH:MM:SS"""
    if not seconds:
        return "00:00:00"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

# Add utility functions to template context
@app.context_processor
def utility_processor():
    """Add utility functions to all templates"""
    # Check for active recordings
    active_recording = None
    if current_user.is_authenticated:
        # Check for any recording that's currently active (not completed)
        # This includes both meeting-linked and hotkey recordings
        from dual_stream import DualModeStreamer
        global recording_state
        if recording_state.get('active', False):
            # Get the most recent recording that might be active
            recent_recording = Recording.query.filter_by(user_id=current_user.id).order_by(Recording.created_at.desc()).first()
            if recent_recording and recent_recording.status != 'completed':
                active_recording = recent_recording
    
    return dict(
        format_file_size=format_file_size, 
        format_duration=format_duration,
        active_recording=active_recording
    )

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))  # Fix SQLAlchemy deprecation

def get_single_user():
    """Get the single user for this system (don't auto-create)"""
    try:
        # Get the first (and only) user
        user = User.query.first()
        return user
        
    except Exception as e:
        logger.error(f"❌ Error getting single user: {e}")
        return None

# Global state
recording_state = {
    'active': False,
    'streamer': None,
    'thread': None,
    'transcriptions': [],
    'selected_monitor': None,
    'recording_id': None
}

# Threading lock to prevent race conditions in recording start/stop
recording_lock = threading.Lock()

def get_monitor_manufacturers():
    """Get monitor manufacturer info using WMI InstanceNames and full model names"""
    try:
        # Get full monitor information including model names from EDID
        wmi_command = '''Get-WmiObject -Namespace root\\wmi -Class WmiMonitorID | ForEach-Object {
            $mfgCode = ($_.ManufacturerName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join '';
            $modelName = ($_.UserFriendlyName | Where-Object {$_ -ne 0} | ForEach-Object {[char]$_}) -join '';
            [PSCustomObject]@{
                InstanceName = $_.InstanceName;
                ManufacturerCode = $mfgCode;
                ModelName = $modelName
            }
        } | ConvertTo-Json'''
        
        result = subprocess.run([
            'powershell', '-Command', wmi_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            wmi_data = json.loads(result.stdout.strip())
            if isinstance(wmi_data, dict):
                wmi_data = [wmi_data]
            
            # Enhanced manufacturer code to actual brand mapping
            manufacturer_codes = {
                'LEN': 'Lenovo',
                'HKC': 'Koorui',  # HKC codes are often used by Koorui monitors
                'ACR': 'Acer', 
                'SAM': 'Samsung',
                'DEL': 'Dell',
                'AOC': 'AOC',
                'BNQ': 'BenQ',
                'ASU': 'ASUS',
                'MSI': 'MSI',
                'GSM': 'LG',      # GSM is LG's manufacturer code
                'LG': 'LG',
                'HP': 'HP',
                'YCT': 'Unknown'
            }
            
            # Extract manufacturer info from InstanceName (format: DISPLAY\MANUFACTURER####\...)
            manufacturers = []
            for item in wmi_data:
                instance_name = item.get('InstanceName', '')
                if 'DISPLAY\\' in instance_name:
                    # Extract manufacturer code (e.g., "LEN4187" -> "LEN")
                    parts = instance_name.split('\\')
                    if len(parts) > 1:
                        manufacturer_part = parts[1]  # e.g., "LEN4187"
                        # Find manufacturer code (usually first 3 chars, but can vary)
                        manufacturer_code = None
                        for code in manufacturer_codes.keys():
                            if manufacturer_part.startswith(code):
                                manufacturer_code = code
                                break
                        
                        if manufacturer_code:
                            manufacturers.append({
                                'instance': instance_name,
                                'code': manufacturer_code,
                                'name': manufacturer_codes[manufacturer_code],
                                'product_id': manufacturer_part[len(manufacturer_code):]  # e.g., "4187"
                            })
                        else:
                            # Unknown manufacturer, use the part before numbers
                            match = re.match(r'^([A-Z]+)', manufacturer_part)
                            if match:
                                unknown_code = match.group(1)
                                manufacturers.append({
                                    'instance': instance_name,
                                    'code': unknown_code,
                                    'name': unknown_code,
                                    'product_id': manufacturer_part[len(unknown_code):]
                                })
            
            return manufacturers
        
    except Exception as e:
        print(f"WMI lookup failed: {e}")
    
    return []

def get_monitors():
    """Get list of available monitors from settings configuration"""
    logger.debug("🔍 Getting monitors from settings manager...")
    monitors = settings_manager.get_all_monitors()
    logger.info(f"📺 Found {len(monitors)} monitors")
    for i, monitor in enumerate(monitors):
        logger.debug(f"   Monitor {i}: {monitor['name']} at ({monitor['x']}, {monitor['y']}) - {monitor['width']}x{monitor['height']}")
    return monitors

def get_default_monitor():
    """Get the default monitor configuration from settings"""
    logger.debug("🔍 Getting default monitor from settings manager...")
    default_monitor = settings_manager.get_default_monitor()
    if default_monitor:
        logger.info(f"📺 Default monitor: ID={default_monitor['id']}, Name='{default_monitor['name']}'")
        logger.debug(f"   Position: ({default_monitor['x']}, {default_monitor['y']})")
        logger.debug(f"   Size: {default_monitor['width']}x{default_monitor['height']}")
    else:
        logger.warning("⚠️ No default monitor found")
    return default_monitor

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Check if any user exists
    existing_user = User.query.first()
    
    if not existing_user:
        # No user exists, redirect to setup
        return redirect(url_for('setup'))
    
    # User exists, auto-login for single-user system
    if not current_user.is_authenticated:
        login_user(existing_user, remember=True)
    
    return redirect(url_for('dashboard'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    # Check if user already exists
    if User.query.first():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address')
        
        if errors:
            return jsonify({'success': False, 'errors': errors})
        
        # Create the single user (no password needed for single-user system)
        try:
            user = User(username=username, email=email)
            user.set_password('default')  # Set a default password since the field is required
            db.session.add(user)
            db.session.commit()
            
            # Auto-login the new user
            login_user(user, remember=True)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'errors': ['Setup failed. Please try again.']})
    
    return render_template('setup.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # For single-user system, redirect to login which auto-logs in the single user
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))  # This will auto-login and redirect to dashboard

@app.route('/dashboard')
@login_required
def dashboard():
    # Get recent recordings - show all recordings for single-user system
    recent_recordings = Recording.query\
        .order_by(Recording.created_at.desc()).limit(6).all()
    
    # Get recording stats - show all recordings for single-user system
    total_recordings = Recording.query.count()
    total_duration = db.session.query(db.func.sum(Recording.duration)).scalar() or 0
    
    return render_template('dashboard.html', 
                         recent_recordings=recent_recordings,
                         total_recordings=total_recordings,
                         total_duration=total_duration)

@app.route('/recordings')
@login_required
def recordings():
    page = request.args.get('page', 1, type=int)
    sort_by = request.args.get('sort', 'date_desc')
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '').strip()
    
    # Start with base query - show all recordings for single-user system
    query = Recording.query
    
    # Apply search filter
    if search_query:
        query = query.filter(Recording.title.contains(search_query))
    
    # Apply status filter
    if status_filter != 'all':
        if status_filter == 'completed':
            query = query.filter(Recording.file_path.isnot(None))
        elif status_filter == 'processing':
            query = query.filter(Recording.file_path.is_(None))
        elif status_filter == 'failed':
            # Recordings that have been marked as failed or have issues
            query = query.filter(Recording.file_path.is_(None))
    
    # Apply sorting
    if sort_by == 'date_asc':
        query = query.order_by(Recording.created_at.asc())
    elif sort_by == 'title':
        query = query.order_by(Recording.title.asc())
    elif sort_by == 'duration':
        query = query.order_by(Recording.duration.desc().nullslast())
    else:  # default: date_desc
        query = query.order_by(Recording.created_at.desc())
    
    recordings = query.paginate(page=page, per_page=10, error_out=False)
    
    return render_template('recordings.html', recordings=recordings)

@app.route('/record')
@login_required
def record():
    monitors = get_monitors()
    default_monitor = get_default_monitor()
    default_monitor_id = default_monitor['id'] if default_monitor else 0
    return render_template('record.html', 
                         monitors=monitors, 
                         default_monitor=default_monitor_id)

@app.route('/monitors')
@login_required
def list_monitors():
    """API endpoint to get available monitors"""
    monitors = get_monitors()
    return jsonify({'monitors': monitors})

@app.route('/start', methods=['POST'])
def start_recording():
    # Handle both authenticated and hotkey requests
    user_info = current_user.username if current_user.is_authenticated else "hotkey"
    logger.info(f"🎬 Recording start requested by: {user_info}")
    
    # Use lock to prevent race conditions
    with recording_lock:
        if recording_state['active']:
            logger.warning(f"⚠️ Recording already active - rejecting request from {user_info}")
            return jsonify({'error': 'Already recording'}), 400
        
        # Immediately set active flag to prevent duplicate requests
        recording_state['active'] = True
        logger.info(f"🔒 Recording state locked for {user_info}")
    
    try:
        # Get monitor selection and title from request
        data = request.get_json() or {}
        monitor_id = data.get('monitor_id')
        recording_title = data.get('title', f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        meeting_id = data.get('meeting_id')  # New: get meeting ID for association
        
        logger.info(f"📝 Recording request details:")
        logger.info(f"   Title: {recording_title}")
        logger.info(f"   Requested Monitor ID: {monitor_id}")
        logger.info(f"   Meeting ID: {meeting_id}")
        logger.info(f"   Request data: {data}")
        
        # If meeting_id provided, check if meeting already has a recording
        if meeting_id:
            try:
                meeting = Meeting.query.filter_by(id=meeting_id, user_id=current_user.id if current_user.is_authenticated else None).first()
                if meeting and meeting.recording_id:
                    logger.warning(f"⚠️ Meeting {meeting_id} already has a recording linked")
                    recording_state['active'] = False  # Reset flag on error
                    return jsonify({'error': 'This meeting already has a recording'}), 400
                
                # Check if meeting is excluded
                if meeting and (meeting.user_excluded or meeting.exclude_all_series):
                    logger.warning(f"⚠️ Meeting {meeting_id} is excluded from recording")
                    recording_state['active'] = False  # Reset flag on error
                    return jsonify({'error': 'This meeting is excluded from recording'}), 403
                    
            except Exception as e:
                logger.error(f"❌ Error checking meeting: {str(e)}")
                # Continue with recording anyway
        
        # Use default monitor from settings if no monitor specified
        if monitor_id is None:
            logger.info("🔍 No monitor specified, getting default from settings...")
            default_monitor = get_default_monitor()
            monitor_id = default_monitor['id'] if default_monitor else 0
            logger.info(f"📺 Using default monitor ID: {monitor_id}")
    
        # Get monitor info
        logger.info("🔍 Getting all available monitors...")
        monitors = get_monitors()
        selected_monitor = None
        for monitor in monitors:
            if monitor['id'] == monitor_id:
                selected_monitor = monitor
                logger.info(f"✅ Found matching monitor: ID={monitor['id']}, Name='{monitor['name']}'")
                break
        
        if not selected_monitor:
            logger.error(f"❌ Invalid monitor selection: ID={monitor_id}")
            logger.error(f"   Available monitors: {[m['id'] for m in monitors]}")
            recording_state['active'] = False  # Reset flag on error
            return jsonify({'error': 'Invalid monitor selection'}), 400
        
        logger.info(f"📺 Selected monitor configuration:")
        logger.info(f"   ID: {selected_monitor['id']}")
        logger.info(f"   Name: {selected_monitor['name']}")
        logger.info(f"   Position: ({selected_monitor['x']}, {selected_monitor['y']})")
        logger.info(f"   Size: {selected_monitor['width']}x{selected_monitor['height']}")
        logger.info(f"   Primary: {selected_monitor.get('primary', False)}")
        
        # Create database record for this recording
        logger.info("💾 Creating database record...")
        
        # Always use the single user for this system
        single_user = get_single_user()
        if not single_user:
            recording_state['active'] = False  # Reset flag on error
            return jsonify({'error': 'System user not available'}), 500
        
        recording = Recording(
            title=recording_title,
            filename='',  # Will be set when recording completes
            file_path='',  # Will be set when recording completes
            started_at=datetime.utcnow(),
            monitor_name=selected_monitor['name'],
            resolution=f"{selected_monitor['width']}x{selected_monitor['height']}",
            user_id=single_user.id,
            status='recording'
        )
        db.session.add(recording)
        db.session.commit()
        logger.info(f"✅ Database record created with ID: {recording.id}")
        
        # If meeting_id provided, link the recording to the meeting
        if meeting_id:
            try:
                meeting = Meeting.query.filter_by(id=meeting_id, user_id=single_user.id).first()
                if meeting:
                    meeting.recording_id = recording.id
                    meeting.recording_status = 'recording'
                    meeting.last_updated = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"🔗 Linked recording {recording.id} to meeting {meeting_id}")
                else:
                    logger.warning(f"⚠️ Meeting {meeting_id} not found or doesn't belong to user")
            except Exception as e:
                logger.error(f"❌ Error linking recording to meeting: {str(e)}")
                # Continue with recording anyway
        
        # Store selected monitor and recording ID
        recording_state['selected_monitor'] = selected_monitor
        recording_state['recording_id'] = recording.id
        recording_state['meeting_id'] = meeting_id  # Store for later use
        
        # Create streamer instance with monitor config
        logger.info("🚀 Creating DualModeStreamer instance...")
        recording_state['streamer'] = DualModeStreamer(
            monitor_config=selected_monitor
        )
        # Note: active flag already set at the beginning with lock
        recording_state['transcriptions'] = []
        
        logger.info("✅ Recording state updated and streamer created")
        
    except Exception as e:
        # Reset flag on any error during setup
        logger.error(f"❌ Error during recording setup: {str(e)}")
        recording_state['active'] = False
        return jsonify({'error': f'Recording setup failed: {str(e)}'}), 500
    
    # Start recording in background thread
    def record_thread():
        logger.info("🎬 Starting recording thread...")
        success = recording_state['streamer'].dual_mode_record()
        recording_state['active'] = False
        logger.info(f"🔄 Recording thread completed with success: {success}")
        
        # Update database record when recording completes
        if 'recording_id' in recording_state:
            with app.app_context():  # Ensure we have application context
                rec = Recording.query.get(recording_state['recording_id'])
                if rec:
                    logger.info(f"💾 Updating database record {rec.id} after recording completion...")
                    rec.ended_at = datetime.utcnow()
                    rec.status = 'completed' if success else 'failed'
                    
                    # Try to get file info if recording succeeded
                    if success and hasattr(recording_state['streamer'], 'last_output_file'):
                        file_path = recording_state['streamer'].last_output_file
                        if os.path.exists(file_path):
                            # Store only the filename, not the full path to avoid cross-machine issues
                            rec.file_path = os.path.basename(file_path)  # Store just filename
                            rec.filename = os.path.basename(file_path)
                            rec.file_size = os.path.getsize(file_path)
                            
                            logger.info(f"📁 File info updated: {rec.filename} ({rec.file_size} bytes)")
                            
                            # Calculate duration from start/end times
                            if rec.started_at and rec.ended_at:
                                duration = (rec.ended_at - rec.started_at).total_seconds()
                                rec.duration = int(duration)
                                logger.info(f"⏱️ Duration calculated: {rec.duration} seconds")
                            
                            # Try to get actual video duration using ffprobe if available
                            try:
                                import subprocess
                                result = subprocess.run([
                                    'ffprobe', '-v', 'quiet', '-show_entries', 
                                    'format=duration', '-of', 'csv=p=0', file_path
                                ], capture_output=True, text=True, timeout=10)
                                
                                if result.returncode == 0 and result.stdout.strip():
                                    video_duration = float(result.stdout.strip())
                                    rec.duration = int(video_duration)
                                    logger.info(f"⏱️ Duration from ffprobe: {rec.duration} seconds")
                            except Exception as e:
                                logger.debug(f"ffprobe duration check failed: {e}")
                                pass  # Fall back to calculated duration
                    
                    db.session.commit()
                    logger.info(f"✅ Database record {rec.id} updated successfully")
                    
                    # Update associated meeting status if exists
                    if 'meeting_id' in recording_state and recording_state['meeting_id']:
                        try:
                            meeting = Meeting.query.get(recording_state['meeting_id'])
                            if meeting:
                                meeting.recording_status = 'recorded_local' if success else 'failed'
                                meeting.last_updated = datetime.utcnow()
                                db.session.commit()
                                logger.info(f"✅ Updated meeting {meeting.id} status to {meeting.recording_status}")
                        except Exception as e:
                            logger.error(f"❌ Error updating meeting status: {str(e)}")
                    
                    # Trigger background upload to IDrive E2
                    if success:
                        try:
                            from background_uploader import trigger_upload
                            logger.info(f"🚀 Triggering background upload for recording {rec.id}")
                            upload_started = trigger_upload(rec.id)
                            if upload_started:
                                logger.info(f"✅ Background upload started for recording {rec.id}")
                            else:
                                logger.warning(f"⚠️ Failed to start background upload for recording {rec.id}")
                        except Exception as upload_error:
                            logger.error(f"❌ Background upload trigger failed: {upload_error}")
                            # Don't fail the recording if upload fails - it can be retried later
    
    recording_state['thread'] = threading.Thread(target=record_thread, daemon=True)
    recording_state['thread'].start()
    logger.info("🎬 Recording thread started")
    
    response_data = {
        'status': 'started',
        'monitor': selected_monitor['name'],
        'recording_id': recording.id
    }
    logger.info(f"✅ Recording started successfully: {response_data}")
    
    return jsonify(response_data)

@app.route('/stop', methods=['POST'])
def stop_recording():
    with recording_lock:
        if not recording_state['active']:
            return jsonify({'error': 'Not recording'}), 400
        
        # Stop recording
        if recording_state['streamer']:
            # Signal streamer to stop
            recording_state['streamer'].transcription_active = False
            recording_state['streamer'].recording_active = False
            # Terminate ffmpeg processes if running
            try:
                if getattr(recording_state['streamer'], 'audio_process', None):
                    recording_state['streamer'].audio_process.terminate()
            except Exception:
                pass
            try:
                if getattr(recording_state['streamer'], 'video_process', None):
                    recording_state['streamer'].video_process.terminate()
            except Exception:
                pass
            # Don't wait for thread - let it clean up in background
            # This prevents Flask from blocking and timing out
        
        recording_state['active'] = False
        logger.info("🛑 Recording stopped via API request")
        
    return jsonify({'status': 'stopped'})

@app.route('/status')
@login_required
def get_status():
    return jsonify({
        'active': recording_state['active'],
        'transcription_count': len(recording_state['transcriptions'])
    })

@app.route('/transcriptions')
@login_required
def get_transcriptions():
    return jsonify({'transcriptions': recording_state['transcriptions']})

# Monkey patch to capture transcriptions
original_send = DualModeStreamer.send_text_to_server
def patched_send(self, text):
    transcription_entry = {
        'text': text,
        'timestamp': time.strftime('%H:%M:%S'),
        'utc_timestamp': time.time()
    }
    recording_state['transcriptions'].append(transcription_entry)
    
    # Save to transcript file asynchronously (non-blocking)
    if 'recording_id' in recording_state:
        def save_transcript():
            try:
                with app.app_context():  # Ensure Flask application context
                    rec = Recording.query.get(recording_state['recording_id'])
                    if rec:
                        # Create transcript file path - use recording title since file_path isn't set during live recording
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        recordings_dir = os.path.join(current_dir, 'recordings')
                        
                        # Create a transcript filename based on recording title/timestamp
                        safe_title = "".join(c for c in rec.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        transcript_filename = f"{safe_title}_transcript.txt"
                        transcript_path = os.path.join(recordings_dir, transcript_filename)
                        
                        # Ensure recordings directory exists
                        os.makedirs(recordings_dir, exist_ok=True)
                        
                        # Append transcript line to file
                        with open(transcript_path, 'a', encoding='utf-8') as f:
                            f.write(f"[{transcription_entry['timestamp']}] {text}\n")
                        
            except Exception as e:
                logger.error(f"⚠️ Transcript save error: {e}")
        
        # Run in background thread (no latency impact)
        threading.Thread(target=save_transcript, daemon=True).start()
    
    return original_send(self, text)
DualModeStreamer.send_text_to_server = patched_send


# ============================================================================
# WebSocket Client API Endpoints
# ============================================================================

@app.route('/api/find_meeting', methods=['POST'])
def api_find_meeting():
    """Find meeting by calendar_event_id for WebSocket client"""
    try:
        data = request.get_json()
        calendar_event_id = data.get('calendar_event_id')
        
        if not calendar_event_id:
            return jsonify({'found': False, 'error': 'No calendar_event_id provided'}), 400
        
        meeting = Meeting.query.filter_by(calendar_event_id=calendar_event_id).first()
        
        if meeting:
            return jsonify({
                'found': True,
                'meeting': {
                    'id': meeting.id,
                    'subject': meeting.subject,
                    'start_time': meeting.start_time.isoformat() if meeting.start_time else None,
                    'end_time': meeting.end_time.isoformat() if meeting.end_time else None,
                    'calendar_event_id': meeting.calendar_event_id
                }
            })
        else:
            return jsonify({'found': False})
    
    except Exception as e:
        logger.error(f"Error finding meeting: {e}")
        return jsonify({'found': False, 'error': str(e)}), 500


@app.route('/api/start_recording', methods=['POST'])
def api_start_recording():
    """Start recording endpoint for WebSocket client"""
    try:
        data = request.get_json()
        meeting_id = data.get('meeting_id')
        
        if not meeting_id:
            return jsonify({'success': False, 'message': 'No meeting_id provided'}), 400
        
        # Find the meeting
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            return jsonify({'success': False, 'message': f'Meeting {meeting_id} not found'}), 404
        
        # Check if already recording
        with recording_lock:
            if recording_state['active']:
                return jsonify({'success': False, 'message': 'Already recording'}), 400
        
        # Start recording with meeting details
        recording_data = {
            'meeting_id': meeting_id,
            'title': meeting.subject
        }
        
        # Forward to the main start_recording function
        original_json = request.get_json
        request.get_json = lambda: recording_data
        
        response = start_recording()
        request.get_json = original_json
        
        return response
    
    except Exception as e:
        logger.error(f"Error starting recording via API: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/stop_recording', methods=['POST'])
def api_stop_recording():
    """Stop recording endpoint for WebSocket client"""
    try:
        return stop_recording()
    except Exception as e:
        logger.error(f"Error stopping recording via API: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint for WebSocket client"""
    try:
        # Check if recording is active
        is_recording = recording_state.get('active', False)
        
        return jsonify({
            'status': 'ok',
            'alive': True,
            'recording_active': is_recording,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({
            'status': 'error',
            'alive': True,
            'message': str(e)
        }), 500


# ============================================================================
# Video Serving Routes
# ============================================================================

@app.route('/video/<int:recording_id>')
@login_required
def serve_video(recording_id):
    """Serve video file for playback"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Use resolved file path that works across different machines
    resolved_path = recording.resolved_file_path
    
    if not resolved_path or not os.path.exists(resolved_path):
        abort(404)
    
    # Get MIME type for the video file
    mime_type, _ = mimetypes.guess_type(resolved_path)
    if not mime_type:
        mime_type = 'video/mp4'  # Default fallback

    return send_file(resolved_path, mimetype=mime_type)

@app.route('/thumbnail/<int:recording_id>')
@login_required
def serve_thumbnail(recording_id):
    """Serve thumbnail image for video preview"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Use resolved file path that works across different machines
    resolved_path = recording.resolved_file_path
    
    if not resolved_path or not os.path.exists(resolved_path):
        abort(404)
    
    # Generate thumbnail path based on resolved path
    base_name = os.path.splitext(resolved_path)[0]
    thumbnail_path = f"{base_name}_thumb.jpg"
    # Generate thumbnail if it doesn't exist
    if not os.path.exists(thumbnail_path):
        try:
            # Use ffmpeg to generate thumbnail at 5 second mark
            subprocess.run([
                get_ffmpeg_path(), '-i', resolved_path,
                '-ss', '00:00:05',  # Seek to 5 seconds
                '-vframes', '1',    # Extract 1 frame
                '-y',               # Overwrite output
                '-q:v', '2',        # High quality
                '-vf', 'scale=320:240',  # Scale to reasonable size
                thumbnail_path
            ], check=True, capture_output=True)
        except Exception as e:
            # Return a default placeholder or 404
            abort(404)
    return send_file(thumbnail_path, mimetype='image/jpeg')

@app.route('/download/<int:recording_id>')
@login_required
def download_recording(recording_id):
    """Download a recording file"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Use resolved file path that works across different machines
    resolved_path = recording.resolved_file_path
    
    if not resolved_path or not os.path.exists(resolved_path):
        abort(404)
    
    # Get the filename without path for download
    filename = recording.filename or os.path.basename(resolved_path)
    
    return send_file(
        resolved_path, 
        as_attachment=True, 
        download_name=filename,
        mimetype='video/x-matroska'  # MKV mimetype
    )

@app.route('/upload-transcript/<int:recording_id>', methods=['POST'])
@login_required
def manual_upload_transcript(recording_id):
    """Manually upload transcript for a recording"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Since we're no longer sending to transcript servers, this function now just 
    # confirms the transcript exists locally
    transcript_path = recording.transcript_path
    
    if transcript_path and os.path.exists(transcript_path):
        return jsonify({
            'success': True,
            'message': f'Transcript available locally for "{recording.title}"'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Transcript file not found locally'
        }), 404

@app.route('/download-transcript/<int:recording_id>')
@login_required
def download_transcript(recording_id):
    """Download transcript file for a recording"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Get transcript file path using the model property
    transcript_path = recording.transcript_path
    
    if not transcript_path or not os.path.exists(transcript_path):
        abort(404)
    
    # Get filename for download
    transcript_filename = os.path.basename(transcript_path)
    
    return send_file(
        transcript_path,
        as_attachment=True,
        download_name=transcript_filename,
        mimetype='text/plain'
    )

@app.route('/sync-status/<int:recording_id>', methods=['POST'])
@login_required
def update_sync_status(recording_id):
    """Manually update sync status of a recording"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Check if recording is currently being uploaded
    if 'streamer' in recording_state and hasattr(recording_state['streamer'], 'upload_status'):
        upload_status = recording_state['streamer'].upload_status
        if upload_status.get('file') == recording.file_path and upload_status.get('progress') == 100:
            recording.uploaded = True
            db.session.commit()
            return jsonify({'status': 'synced'})
    
    # For now, just return current status
    return jsonify({'status': recording.sync_status.lower()})

@app.route('/delete/<int:recording_id>', methods=['POST', 'DELETE'])
@login_required
def delete_recording(recording_id):
    """Delete a recording from database and optionally from filesystem"""
    logger.info(f"🗑️ DELETE REQUEST: User {current_user.username} attempting to delete recording ID {recording_id}")
    
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    # Get delete options from request
    data = request.get_json() or {}
    delete_file = data.get('delete_file', True)  # Default to deleting file
    
    deleted_items = []
    errors = []
    
    try:
        # Delete physical files if requested
        resolved_path = recording.resolved_file_path
        transcript_path = recording.transcript_path
        print(f"🗑️ RESOLVED PATHS: video={resolved_path}, transcript={transcript_path}")
        
        if delete_file:
            # Delete video file
            if resolved_path and os.path.exists(resolved_path):
                print(f"🗑️ DELETING VIDEO FILE: {resolved_path}")
                try:
                    os.remove(resolved_path)
                    deleted_items.append('video_file')
                    print(f"✅ VIDEO FILE DELETED: {resolved_path}")
                except Exception as e:
                    error_msg = f"Failed to delete video file: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ VIDEO FILE DELETE ERROR: {error_msg}")
            elif resolved_path:
                print(f"⚠️ VIDEO FILE NOT FOUND: {resolved_path}")
            
            # Delete thumbnail file
            if resolved_path:
                base_name = os.path.splitext(resolved_path)[0]
                thumbnail_path = f"{base_name}_thumb.jpg"
                if os.path.exists(thumbnail_path):
                    print(f"🗑️ DELETING THUMBNAIL: {thumbnail_path}")
                    try:
                        os.remove(thumbnail_path)
                        deleted_items.append('thumbnail')
                        print(f"✅ THUMBNAIL DELETED: {thumbnail_path}")
                    except Exception as e:
                        error_msg = f"Failed to delete thumbnail: {str(e)}"
                        errors.append(error_msg)
                        print(f"❌ THUMBNAIL DELETE ERROR: {error_msg}")
            
            # Delete transcript file
            if transcript_path and os.path.exists(transcript_path):
                print(f"🗑️ DELETING TRANSCRIPT: {transcript_path}")
                try:
                    os.remove(transcript_path)
                    deleted_items.append('transcript_file')
                    print(f"✅ TRANSCRIPT DELETED: {transcript_path}")
                except Exception as e:
                    error_msg = f"Failed to delete transcript: {str(e)}"
                    errors.append(error_msg)
                    print(f"❌ TRANSCRIPT DELETE ERROR: {error_msg}")
            elif transcript_path:
                print(f"⚠️ TRANSCRIPT NOT FOUND: {transcript_path}")
        else:
            print(f"🗑️ SKIPPING FILE DELETION: delete_file={delete_file}")
        
        # Delete database record
        title = recording.title
        print(f"🗑️ DELETING DATABASE RECORD: {title}")
        db.session.delete(recording)
        db.session.commit()
        deleted_items.append('database_record')
        print(f"✅ DATABASE RECORD DELETED: {title}")
        
        print(f"🗑️ DELETE COMPLETED: deleted_items={deleted_items}, errors={errors}")
        return jsonify({
            'success': True,
            'message': f'Recording "{title}" deleted successfully',
            'deleted': deleted_items,
            'errors': errors
        })
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Failed to delete recording: {str(e)}'
        print(f"❌ DELETE FAILED: {error_msg}")
        return jsonify({
            'success': False,
            'message': error_msg,
            'deleted': deleted_items,
            'errors': errors + [str(e)]
        }), 500

@app.route('/cleanup-orphaned', methods=['POST'])
@app.route('/cleanup', methods=['POST'])  # Legacy route for cached browsers
@login_required
def cleanup_orphaned_recordings():
    """Delete all recordings that have no corresponding file"""
    all_recordings = Recording.query.all()  # Show all recordings for single-user system
    
    deleted_count = 0
    deleted_titles = []
    
    for recording in all_recordings:
        # Check if recording has no file_path or if the file doesn't exist
        is_orphaned = False
        
        if not recording.file_path or recording.file_path == '':
            is_orphaned = True
        else:
            # Check if the actual file exists
            if not recording.file_exists:
                is_orphaned = True
        
        if is_orphaned:
            deleted_titles.append(recording.title)
            db.session.delete(recording)
            deleted_count += 1
    
    try:
        db.session.commit()
        print(f"🧹 Cleanup completed: {deleted_count} orphaned recordings deleted")
        return jsonify({
            'success': True,
            'cleaned': deleted_count,
            'message': f'Cleaned up {deleted_count} orphaned recording(s)',
            'deleted_titles': deleted_titles
        })
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Cleanup failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to cleanup orphaned recordings: {str(e)}'
        }), 500

def cleanup_old_recordings():
    """Clean up old local recordings based on user settings"""
    from datetime import datetime, timedelta
    
    try:
        # Get all users with auto-delete settings
        users = User.query.filter(User.auto_delete_days.isnot(None)).all()
        
        total_deleted = 0
        total_freed_space = 0
        
        for user in users:
            if not user.auto_delete_days or user.auto_delete_days <= 0:
                continue
                
            # Calculate cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=user.auto_delete_days)
            
            # Find old recordings that are synced (uploaded)
            old_recordings = Recording.query.filter(
                Recording.user_id == user.id,
                Recording.created_at < cutoff_date,
                Recording.uploaded == True,  # Only delete if uploaded
                Recording.file_path.isnot(None)  # Has a file path
            ).all()
            
            user_deleted = 0
            user_freed_space = 0
            
            for recording in old_recordings:
                try:
                    # Delete the actual file using resolved path
                    resolved_path = recording.resolved_file_path
                    if resolved_path and os.path.exists(resolved_path):
                        file_size = os.path.getsize(resolved_path)
                        os.remove(resolved_path)
                        user_freed_space += file_size
                        user_deleted += 1
                        
                        # Update database - clear file path but keep record
                        recording.file_path = None
                        
                        print(f"Auto-deleted: {recording.title} ({recording.file_size_formatted})")
                        
                except Exception as e:
                    print(f"Failed to delete file {recording.file_path}: {e}")
                    continue
            
            if user_deleted > 0:
                total_deleted += user_deleted
                total_freed_space += user_freed_space
                print(f"User {user.username}: Deleted {user_deleted} files, freed {user_freed_space / (1024*1024):.1f} MB")
        
        # Commit all changes
        db.session.commit()
        
        if total_deleted > 0:
            print(f"Auto-cleanup completed: {total_deleted} files deleted, {total_freed_space / (1024*1024):.1f} MB freed")
        
        return {
            'deleted_files': total_deleted,
            'freed_space_mb': total_freed_space / (1024*1024),
            'success': True
        }
        
    except Exception as e:
        db.session.rollback()
        print(f"Auto-cleanup error: {e}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/detect-monitors', methods=['POST'])
@login_required
def detect_monitors():
    """API endpoint to detect and save monitors"""
    logger.info(f"🔍 Monitor detection requested by user: {current_user.username}")
    
    try:
        result = settings_manager.detect_and_save_monitors()
        
        if result['success']:
            logger.info(f"✅ Monitor detection successful: {result['message']}")
            return jsonify({
                'success': True,
                'message': result['message'],
                'monitors': result['monitors']
            })
        else:
            logger.error(f"❌ Monitor detection failed: {result['message']}")
            return jsonify({
                'success': False,
                'message': result['message']
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Monitor detection error: {e}")
        return jsonify({
            'success': False,
            'message': f'Monitor detection failed: {str(e)}'
        }), 500

@app.route('/update-monitor-arrangement', methods=['POST'])
@login_required  
def update_monitor_arrangement():
    """API endpoint to update monitor physical arrangement"""
    logger.info(f"🔄 Monitor arrangement update requested by user: {current_user.username}")
    
    try:
        data = request.get_json()
        monitor_order = data.get('monitor_order', [])
        primary_monitor_id = data.get('primary_monitor_id')
        
        logger.info(f"📺 New monitor order: {monitor_order}")
        logger.info(f"🔝 Primary monitor ID: {primary_monitor_id}")
        
        result = settings_manager.update_monitor_arrangement(monitor_order, primary_monitor_id)
        
        if result['success']:
            logger.info(f"✅ Monitor arrangement updated: {result['message']}")
            return jsonify({
                'success': True,
                'message': result['message']
            })
        else:
            logger.error(f"❌ Monitor arrangement update failed: {result['message']}")
            return jsonify({
                'success': False,
                'message': result['message']
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Monitor arrangement update error: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to update monitor arrangement: {str(e)}'
        }), 500

# @app.route('/autorecorder')
# @login_required
# def autorecorder():
#     """AutoRecorder route removed - function disabled"""
#     return "AutoRecorder functionality has been removed", 404
    """AutoRecorder calendar view - stunning weekly calendar with events"""
    import requests
    from datetime import datetime, timedelta
    # Get 7 days of events starting from today
    start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=7)
    
    # Prepare request data
    data = {
        'cal_id': CALENDAR_ID,
        'start_date': start_date.isoformat() + 'Z',
        'end_date': end_date.isoformat() + 'Z',
        'email': current_user.email  # Use the logged-in user's email
    }
    
    events = []
    error_message = None
    
    try:
        logger.info(f"🗓️ AutoRecorder: Fetching calendar events for {current_user.email}")
        
        # Send request to Power Automate
        response = requests.post(
            WORKFLOW_URL,
            headers={'Content-Type': 'application/json'},
            json=data,
            timeout=30
        )
        
        if response.status_code in [200, 201, 202]:
            events = response.json()
            if isinstance(events, list):
                logger.info(f"✅ AutoRecorder: Found {len(events)} raw events")
                
                # Filter out all-day events and non-Teams meetings
                filtered_events = []
                all_day_count = 0
                non_teams_count = 0
                
                for event in events:
                    # Check if event is all-day
                    is_all_day = False
                    
                    # Method 1: Check if isAllDay field exists and is true
                    if event.get('isAllDay') is True:
                        is_all_day = True
                    
                    # Method 2: Check if start/end times indicate all-day (00:00:00 to 23:59:59 or similar)
                    elif event.get('start') and event.get('end'):
                        try:
                            start_str = event['start']
                            end_str = event['end']
                            
                            # Check for all-day patterns like "2025-10-26T00:00:00" to "2025-10-27T00:00:00"
                            if 'T00:00:00' in start_str and ('T00:00:00' in end_str or 'T23:59:59' in end_str):
                                start_dt = parse_calendar_datetime(start_str)
                                end_dt = parse_calendar_datetime(end_str)
                                
                                if start_dt and end_dt:
                                    # If it's exactly 24 hours or spans midnight to midnight, it's likely all-day
                                    duration_hours = (end_dt - start_dt).total_seconds() / 3600
                                    if duration_hours >= 23.5:  # 23.5+ hours indicates all-day
                                        is_all_day = True
                        except:
                            pass
                    
                    # Method 3: Check if subject contains all-day indicators
                    subject = event.get('subject', '').lower()
                    if any(keyword in subject for keyword in ['birthday', 'holiday', 'vacation', 'pto', 'out of office']):
                        is_all_day = True
                    
                    if is_all_day:
                        all_day_count += 1
                        logger.debug(f"🚫 Filtering out all-day event: {event.get('subject', 'No title')}")
                        continue
                    
                    # Check if event is a Teams meeting
                    is_teams_meeting = False
                    
                    # Method 1: Check for Teams meeting link in various fields
                    teams_indicators = [
                        'teams.microsoft.com',
                        'teams.live.com', 
                        'meet.lync.com',
                        'join microsoft teams meeting',
                        'microsoft teams meeting',
                        'teams meeting'
                    ]
                    
                    # Check in webLink field
                    web_link = event.get('webLink', '').lower()
                    if any(indicator in web_link for indicator in teams_indicators):
                        is_teams_meeting = True
                    
                    # Check in body content
                    body = event.get('body', '').lower()
                    if any(indicator in body for indicator in teams_indicators):
                        is_teams_meeting = True
                    
                    # Check in location field
                    location = event.get('location', '').lower()
                    if any(indicator in location for indicator in teams_indicators):
                        is_teams_meeting = True
                    
                    # Check in subject
                    if any(indicator in subject for indicator in ['teams', 'meeting']):
                        is_teams_meeting = True
                    
                    # Method 2: Check if event has onlineMeeting information
                    if event.get('onlineMeeting') or event.get('isOnlineMeeting'):
                        is_teams_meeting = True
                    
                    # Method 3: Check if it's a meeting with attendees (likely recordable)
                    if event.get('requiredAttendees') or event.get('attendees'):
                        # If it has attendees, consider it a meeting worth recording
                        is_teams_meeting = True
                    
                    if not is_teams_meeting:
                        non_teams_count += 1
                        logger.debug(f"🚫 Filtering out non-Teams event: {event.get('subject', 'No title')}")
                        continue
                    
                    filtered_events.append(event)
                
                events = filtered_events
                logger.info(f"✅ AutoRecorder: After filtering - {len(events)} events remaining ({all_day_count} all-day, {non_teams_count} non-Teams events removed)")
                
                # Process events for better display
                for event in events:
                    # Parse start/end times and convert to Eastern time
                    if event.get('start'):
                        try:
                            start_dt = parse_calendar_datetime(event['start'])
                            if start_dt:
                                event['start_datetime'] = start_dt
                                event['start_time'] = start_dt.strftime('%H:%M')
                                event['start_date'] = start_dt.strftime('%Y-%m-%d')
                                event['day_name'] = start_dt.strftime('%A')
                        except:
                            pass
                    
                    if event.get('end'):
                        try:
                            end_dt = parse_calendar_datetime(event['end'])
                            if end_dt:
                                event['end_datetime'] = end_dt
                                event['end_time'] = end_dt.strftime('%H:%M')
                            
                            # Calculate duration
                            if event.get('start_datetime'):
                                duration = end_dt - event['start_datetime']
                                event['duration_minutes'] = int(duration.total_seconds() / 60)
                        except:
                            pass
                    
                    # Clean up attendees
                    if event.get('requiredAttendees'):
                        attendees = [email.strip() for email in event['requiredAttendees'].split(';') if email.strip()]
                        event['attendee_count'] = len(attendees)
                        event['attendee_list'] = attendees
                    
                    # Determine event type/category
                    subject = event.get('subject', '').lower()
                    if 'meeting' in subject or 'update' in subject:
                        event['category'] = 'meeting'
                        event['category_color'] = '#3b82f6'
                    elif 'appointment' in subject or 'private' in subject:
                        event['category'] = 'appointment'
                        event['category_color'] = '#10b981'
                    elif 'call' in subject or 'huddle' in subject:
                        event['category'] = 'call'
                        event['category_color'] = '#f59e0b'
                    else:
                        event['category'] = 'other'
                        event['category_color'] = '#6b7280'
            else:
                logger.warning(f"⚠️ AutoRecorder: Unexpected response format")
                error_message = "Unexpected response format from calendar service"
        else:
            logger.error(f"❌ AutoRecorder: API error {response.status_code}: {response.text}")
            error_message = f"Calendar service error: {response.status_code}"
            
    except Exception as e:
        logger.error(f"💥 AutoRecorder: Error fetching events: {str(e)}")
        error_message = f"Failed to fetch calendar events: {str(e)}"
    
    # Generate day grid for the week
    week_days = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_events = [e for e in events if e.get('start_date') == day.strftime('%Y-%m-%d')]
        week_days.append({
            'date': day,
            'date_str': day.strftime('%Y-%m-%d'),
            'day_name': day.strftime('%A'),
            'day_short': day.strftime('%a'),
            'day_num': day.strftime('%d'),
            'month_name': day.strftime('%B'),
            'is_today': day.date() == datetime.now().date(),
            'events': sorted(day_events, key=lambda x: x.get('start_time', '00:00'))
        })
    
    return render_template('autorecorder.html', 
                         events=events,
                         week_days=week_days,
                         start_date=start_date,
                         end_date=end_date,
                         error_message=error_message,
                         total_events=len(events))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings page for user preferences"""
    if request.method == 'POST':
        try:
            logger.info(f"🔧 Settings update request from user: {current_user.username}")
            logger.debug(f"📝 Form data: {dict(request.form)}")
            
            # Update monitor settings using settings manager
            default_monitor = request.form.get('default_monitor', '')
            logger.info(f"📺 Monitor selection from form: '{default_monitor}'")
            
            if default_monitor:
                monitor_id = int(default_monitor)
                logger.info(f"📺 Converting to monitor ID: {monitor_id}")
                
                # Log current default before change
                current_default = get_default_monitor()
                if current_default:
                    logger.info(f"📺 Current default monitor: ID={current_default['id']}, Name='{current_default['name']}'")
                else:
                    logger.warning("⚠️ No current default monitor found")
                
                if settings_manager.set_default_monitor(monitor_id):
                    logger.info(f"✅ Default monitor updated to ID: {monitor_id}")
                    
                    # Log new default after change
                    new_default = get_default_monitor()
                    if new_default:
                        logger.info(f"📺 New default monitor: ID={new_default['id']}, Name='{new_default['name']}'")
                        logger.info(f"   Position: ({new_default['x']}, {new_default['y']})")
                        logger.info(f"   Size: {new_default['width']}x{new_default['height']}")
                else:
                    logger.error(f"❌ Failed to set monitor ID: {monitor_id}")
                    flash('Failed to update default monitor.', 'error')
                    return redirect(url_for('settings'))
            
            # Handle auto delete days
            auto_delete_days = request.form.get('auto_delete_days', '30')
            logger.info(f"📅 Auto delete days from form: '{auto_delete_days}'")
            try:
                auto_delete_days = int(auto_delete_days)
                if auto_delete_days < 0 or auto_delete_days > 365:
                    logger.error(f"❌ Invalid auto delete days range: {auto_delete_days}")
                    flash('Auto-delete days must be between 0 and 365.', 'error')
                    return redirect(url_for('settings'))
                
                if not settings_manager.set_auto_delete_days(auto_delete_days):
                    logger.error(f"❌ Failed to set auto delete days: {auto_delete_days}")
                    flash('Failed to update auto-delete setting.', 'error')
                    return redirect(url_for('settings'))
                else:
                    logger.info(f"✅ Auto delete days updated to: {auto_delete_days}")
                    
            except ValueError:
                logger.error(f"❌ Invalid auto delete days value: '{auto_delete_days}'")
                flash('Invalid auto-delete days value.', 'error')
                return redirect(url_for('settings'))
            
            logger.info("✅ Settings update completed successfully")
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('settings'))
            
        except Exception as e:
            logger.error(f"❌ Settings update error: {e}")
            flash(f'Failed to update settings: {str(e)}', 'error')
            return redirect(url_for('settings'))
    
    # GET request - load settings for display
    logger.debug(f"🔍 Loading settings page for user: {current_user.username}")
    
    # Get current settings state
    settings_data = settings_manager.load_settings()
    monitors_detected = settings_data["user_preferences"].get("monitors_detected", False)
    
    # Get available monitors and current settings
    monitors = get_monitors() if monitors_detected else []
    default_monitor = get_default_monitor()
    default_monitor_id = default_monitor['id'] if default_monitor else None
    auto_delete_days = settings_manager.get_auto_delete_days()
    
    logger.debug(f"📺 Monitors detected: {monitors_detected}")
    logger.debug(f"📺 Available monitors: {len(monitors)}")
    logger.debug(f"📺 Default monitor ID: {default_monitor_id}")
    logger.debug(f"📅 Auto delete days: {auto_delete_days}")
    
    # Create a user-like object for template compatibility
    settings_user = {
        'default_monitor': str(default_monitor_id) if default_monitor_id else '',
        'auto_delete_days': auto_delete_days
    }
    
    logger.debug("✅ Settings page data prepared")
    
    # Get statistics for the information cards
    try:
        total_recordings = Recording.query.count()
        last_recording_obj = Recording.query.order_by(Recording.created_at.desc()).first()
        last_recording = last_recording_obj.created_at.strftime('%Y-%m-%d') if last_recording_obj else "Never"
        
        # Calculate storage used (approximate)
        import os
        storage_used = 0
        recordings_path = os.path.join(os.path.dirname(__file__), 'recordings')
        if os.path.exists(recordings_path):
            for root, dirs, files in os.walk(recordings_path):
                storage_used += sum(os.path.getsize(os.path.join(root, name)) for name in files)
        
        # Convert to human readable format
        if storage_used < 1024**3:  # Less than 1GB
            storage_used_str = f"{storage_used / (1024**2):.1f} MB"
        else:
            storage_used_str = f"{storage_used / (1024**3):.1f} GB"
            
    except Exception as e:
        logger.error(f"Error calculating statistics: {e}")
        total_recordings = 0
        last_recording = "Unknown"
        storage_used_str = "Unknown"
    
    return render_template('settings.html', 
                         user=settings_user, 
                         monitors=monitors,
                         monitors_detected=monitors_detected,
                         total_recordings=total_recordings,
                         last_recording=last_recording,
                         storage_used=storage_used_str)

@app.route('/auto-cleanup', methods=['POST'])
@login_required
def trigger_auto_cleanup():
    """Manually trigger auto-cleanup for current user"""
    try:
        result = cleanup_old_recordings()
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Cleanup completed: {result['deleted_files']} files deleted, {result['freed_space_mb']:.1f} MB freed",
                'deleted_files': result['deleted_files'],
                'freed_space_mb': result['freed_space_mb']
            })
        else:
            return jsonify({
                'success': False,
                'message': f"Cleanup failed: {result['error']}"
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error during cleanup: {str(e)}'
        }), 500

@app.route('/clear-local-data', methods=['POST'])
@login_required
def clear_local_data():
    """Clear all local recordings while preserving cloud backups"""
    try:
        import os
        import shutil
        
        logger.info(f"🗑️ Clear local data request from user: {current_user.username}")
        
        # Count files before deletion
        recordings_path = os.path.join(os.path.dirname(__file__), 'recordings')
        files_deleted = 0
        space_freed = 0
        
        if os.path.exists(recordings_path):
            # Calculate size and count before deletion
            for root, dirs, files in os.walk(recordings_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        space_freed += os.path.getsize(file_path)
                        files_deleted += 1
                    except OSError:
                        continue
            
            # Remove all files in recordings directory
            for root, dirs, files in os.walk(recordings_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        logger.info(f"🗑️ Deleted file: {file}")
                    except OSError as e:
                        logger.error(f"❌ Failed to delete {file}: {e}")
            
            # Remove empty subdirectories
            for root, dirs, files in os.walk(recordings_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Only remove if empty
                            os.rmdir(dir_path)
                            logger.info(f"🗑️ Removed empty directory: {dir_name}")
                    except OSError as e:
                        logger.error(f"❌ Failed to remove directory {dir_name}: {e}")
        
        # Update database records to mark files as locally deleted
        # but keep the records for cloud backup reference
        try:
            recordings = Recording.query.all()
            updated_count = 0
            for recording in recordings:
                if recording.file_path and recording.status != 'cloud_only':
                    # Mark as locally deleted but keep cloud reference
                    recording.status = 'cloud_only'  # Custom status for cloud-only files
                    updated_count += 1
            
            db.session.commit()
            logger.info(f"📝 Updated {updated_count} database records to cloud_only status")
            
        except Exception as e:
            logger.error(f"❌ Database update error: {e}")
            db.session.rollback()
        
        # Convert space to human readable format
        if space_freed < 1024**3:  # Less than 1GB
            space_str = f"{space_freed / (1024**2):.1f} MB"
        else:
            space_str = f"{space_freed / (1024**3):.1f} GB"
        
        logger.info(f"✅ Local data cleared: {files_deleted} files, {space_str} freed")
        
        return jsonify({
            'success': True,
            'message': f'Successfully cleared {files_deleted} local files and freed {space_str} of space. Cloud backups remain safe.',
            'files_deleted': files_deleted,
            'space_freed': space_str
        })
        
    except Exception as e:
        logger.error(f"❌ Clear local data error: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to clear local data: {str(e)}'
        }), 500

@app.route('/factory-reset', methods=['POST'])
@login_required
def factory_reset():
    """Complete factory reset - wipe everything and start fresh"""
    try:
        import os
        import shutil
        
        logger.warning(f"🏭 FACTORY RESET initiated by user: {current_user.username}")
        
        # Step 1: Clear all recordings files
        recordings_path = os.path.join(os.path.dirname(__file__), 'recordings')
        files_deleted = 0
        space_freed = 0
        
        if os.path.exists(recordings_path):
            # Calculate total size before deletion
            for root, dirs, files in os.walk(recordings_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        space_freed += os.path.getsize(file_path)
                        files_deleted += 1
                    except OSError:
                        continue
            
            # Remove entire recordings directory
            try:
                shutil.rmtree(recordings_path)
                logger.warning(f"🗑️ Deleted recordings directory: {files_deleted} files")
            except Exception as e:
                logger.error(f"❌ Failed to remove recordings directory: {e}")
            
            # Recreate empty recordings directory
            os.makedirs(recordings_path, exist_ok=True)
            logger.info(f"📁 Recreated empty recordings directory")
        
        # Step 2: Clear logs directory
        logs_path = os.path.join(os.path.dirname(__file__), 'logs')
        logs_deleted = 0
        
        if os.path.exists(logs_path):
            for root, dirs, files in os.walk(logs_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        logs_deleted += 1
                        logger.info(f"🗑️ Deleted log file: {file}")
                    except OSError as e:
                        logger.error(f"❌ Failed to delete log {file}: {e}")
        
        # Step 3: Reset settings to defaults
        try:
            settings_config_path = os.path.join(os.path.dirname(__file__), 'settings.config')
            if os.path.exists(settings_config_path):
                os.remove(settings_config_path)
                logger.warning(f"🔧 Deleted settings configuration")
        except Exception as e:
            logger.error(f"❌ Failed to delete settings: {e}")
        
        # Step 4: Clear database completely
        try:
            # Drop all tables
            db.drop_all()
            logger.warning(f"🗄️ Dropped all database tables")
            
            # Recreate tables
            db.create_all()
            logger.info(f"🗄️ Recreated database schema")
            
            # Remove database file entirely for complete reset
            db_path = os.path.join(os.path.dirname(__file__), 'recordings.db')
            if os.path.exists(db_path):
                # Close any existing connections
                db.session.close()
                db.engine.dispose()
                
                # Remove database file
                try:
                    os.remove(db_path)
                    logger.warning(f"🗄️ Deleted database file completely")
                except Exception as e:
                    logger.error(f"❌ Failed to delete database file: {e}")
            
        except Exception as e:
            logger.error(f"❌ Database reset error: {e}")
        
        # Step 5: Clear Flask session and cache
        try:
            session.clear()
            logger.info(f"🔐 Cleared Flask session")
        except Exception as e:
            logger.error(f"❌ Session clear error: {e}")
        
        # Step 6: Clear Python cache
        try:
            pycache_path = os.path.join(os.path.dirname(__file__), '__pycache__')
            if os.path.exists(pycache_path):
                shutil.rmtree(pycache_path)
                logger.info(f"🐍 Cleared Python cache")
        except Exception as e:
            logger.error(f"❌ Cache clear error: {e}")
        
        # Convert space to human readable format
        if space_freed < 1024**3:  # Less than 1GB
            space_str = f"{space_freed / (1024**2):.1f} MB"
        else:
            space_str = f"{space_freed / (1024**3):.1f} GB"
        
        logger.warning(f"🏭 FACTORY RESET COMPLETED: {files_deleted} files deleted, {logs_deleted} logs cleared, {space_str} freed")
        
        return jsonify({
            'success': True,
            'message': f'Factory reset completed successfully! Deleted {files_deleted} recordings, {logs_deleted} logs, cleared database and settings. Freed {space_str} of space. Please restart the application.',
            'files_deleted': files_deleted,
            'logs_deleted': logs_deleted,
            'space_freed': space_str,
            'restart_required': True
        })
        
    except Exception as e:
        logger.error(f"❌ Factory reset error: {e}")
        return jsonify({
            'success': False,
            'message': f'Factory reset failed: {str(e)}'
        }), 500

@app.route('/upload/<int:recording_id>', methods=['POST'])
@login_required
def trigger_manual_upload(recording_id):
    """Manually trigger upload for a specific recording"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    try:
        from background_uploader import trigger_upload
        logger.info(f"🚀 Manual upload triggered by user {current_user.username} for recording {recording_id}")
        
        upload_started = trigger_upload(recording_id)
        if upload_started:
            return jsonify({
                'success': True,
                'message': f'Upload started for "{recording.title}"'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start upload'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Manual upload trigger failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}'
        }), 500

@app.route('/upload-status/<int:recording_id>')
@login_required
def get_upload_status(recording_id):
    """Get upload status for a recording"""
    recording = Recording.query.filter_by(id=recording_id).first_or_404()
    
    try:
        from background_uploader import get_uploader
        uploader = get_uploader()
        status = uploader.get_upload_status(recording_id)
        
        return jsonify({
            'success': True,
            'recording_id': recording_id,
            'upload_status': recording.upload_status,
            'uploaded': recording.uploaded,
            'sync_status': recording.sync_status,
            'has_cloud_backup': recording.has_cloud_backup,
            'active_upload': status,
            'cloud_urls': {
                'video': recording.cloud_video_url,
                'transcript': recording.cloud_transcript_url,
                'thumbnail': recording.cloud_thumbnail_url
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Upload status check failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

@app.route('/retry-failed-uploads', methods=['POST'])
@login_required
def retry_failed_uploads():
    """Manually retry all failed uploads"""
    try:
        retry_manager = get_retry_manager()
        success_count = retry_manager.manual_retry_all_failed()
        
        return jsonify({
            'success': True,
            'message': f'Retry started for failed uploads',
            'retried_count': success_count
        })
        
    except Exception as e:
        logger.error(f"❌ Manual retry trigger failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Retry failed: {str(e)}'
        }), 500

@app.route('/retry-stats')
@login_required
def get_retry_stats():
    """Get retry statistics"""
    try:
        retry_manager = get_retry_manager()
        stats = retry_manager.get_retry_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"❌ Retry stats failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Stats failed: {str(e)}'
        }), 500

@app.route('/upload-status')
@login_required
def get_all_upload_status():
    """Get status of all active uploads"""
    try:
        from background_uploader import get_uploader
        uploader = get_uploader()
        all_active = uploader.get_all_active_uploads()
        
        # Show all uploads for single-user system
        user_recordings = Recording.query.all()  # Get all recordings instead of filtering by user
        user_recording_ids = {rec.id for rec in user_recordings}
        
        filtered_active = {
            rec_id: status for rec_id, status in all_active.items() 
            if rec_id in user_recording_ids
        }
        
        return jsonify({
            'success': True,
            'active_uploads': filtered_active,
            'total_active': len(filtered_active)
        })
        
    except Exception as e:
        logger.error(f"❌ Upload status check failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

# =============================================
# ADVANCED ROUTES - Database Viewer
# =============================================

@app.route('/admin')
@login_required
def admin_dashboard():
    """Advanced dashboard showing database overview"""
    try:
        # Get recording statistics
        total_recordings = Recording.query.count()
        uploaded_count = Recording.query.filter_by(uploaded=True).count()
        total_size = db.session.query(db.func.sum(Recording.file_size)).scalar() or 0
        total_duration = db.session.query(db.func.sum(Recording.duration)).scalar() or 0
        users_count = User.query.count()
        
        # Get meeting statistics
        total_meetings = Meeting.query.count()
        recorded_meetings = Meeting.query.filter(Meeting.recording_status.in_(['recorded_synced', 'recorded_local'])).count()
        upcoming_meetings = Meeting.query.filter(Meeting.start_time > datetime.utcnow()).count()
        orphaned_recordings = Recording.query.filter(~Recording.id.in_(
            db.session.query(Meeting.recording_id).filter(Meeting.recording_id.isnot(None))
        )).count()
        
        # Get recent recordings with user info
        recent_recordings = db.session.query(Recording, User).join(User)\
            .order_by(Recording.created_at.desc()).limit(5).all()
        
        # Get recent meetings
        recent_meetings = Meeting.query.order_by(Meeting.start_time.desc()).limit(5).all()
        
        # Get upload status counts
        upload_stats = db.session.query(Recording.upload_status, db.func.count(Recording.id))\
            .group_by(Recording.upload_status).all()
        
        upload_counts = {status: count for status, count in upload_stats}
        
        # Today's recordings count
        today = datetime.utcnow().date()
        todays_recordings = Recording.query.filter(
            Recording.created_at >= today,
            Recording.created_at < today + timedelta(days=1)
        ).count()
        
        stats = {
            'total_recordings': total_recordings,
            'uploaded_count': uploaded_count,
            'local_only': total_recordings - uploaded_count,
            'total_size': format_file_size(total_size),
            'total_duration': format_duration(total_duration),
            'users_count': users_count,
            'upload_percentage': int((uploaded_count / total_recordings * 100)) if total_recordings > 0 else 0,
            'upload_counts': upload_counts,
            'total_meetings': total_meetings,
            'recorded_meetings': recorded_meetings,
            'upcoming_meetings': upcoming_meetings,
            'orphaned_recordings': orphaned_recordings,
            'meeting_recording_percentage': int((recorded_meetings / total_meetings * 100)) if total_meetings > 0 else 0,
            'todays_recordings': todays_recordings,
            'uploaded': uploaded_count,
            'total_users': users_count
        }
        
        return render_template('admin/dashboard.html', 
                             stats=stats, 
                             recent_recordings=recent_recordings,
                             recent_meetings=recent_meetings)
        
    except Exception as e:
        logger.error(f"❌ Advanced dashboard error: {e}")
        return f"Database error: {e}", 500

@app.route('/admin/recordings')
@login_required
def admin_recordings():
    """Advanced recordings list with advanced filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'all')
        user_filter = request.args.get('user', 'all')
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        
        # Build query
        query = db.session.query(Recording, User).join(User)
        
        if search:
            query = query.filter(
                db.or_(
                    Recording.title.contains(search),
                    User.username.contains(search),
                    User.email.contains(search)
                )
            )
        
        if status_filter != 'all':
            if status_filter == 'uploaded':
                query = query.filter(Recording.uploaded == True)
            elif status_filter == 'local':
                query = query.filter(Recording.uploaded == False)
            elif status_filter == 'failed':
                query = query.filter(Recording.upload_status == 'failed')
            elif status_filter == 'uploading':
                query = query.filter(Recording.upload_status == 'uploading')
        
        if user_filter != 'all':
            query = query.filter(User.id == int(user_filter))
        
        # Apply sorting
        if sort_by == 'title':
            sort_column = Recording.title
        elif sort_by == 'username':
            sort_column = User.username
        elif sort_by == 'duration':
            sort_column = Recording.duration
        elif sort_by == 'file_size':
            sort_column = Recording.file_size
        elif sort_by == 'upload_status':
            sort_column = Recording.upload_status
        else:
            sort_column = Recording.created_at
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
        
        # Paginate
        recordings = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Get all users for filter dropdown
        users = User.query.all()
        
        return render_template('admin/recordings.html', 
                             recordings=recordings,
                             users=users,
                             search=search,
                             status_filter=status_filter,
                             user_filter=user_filter,
                             sort_by=sort_by,
                             sort_order=sort_order)
        
    except Exception as e:
        logger.error(f"❌ Advanced recordings error: {e}")
        return f"Database error: {e}", 500

@app.route('/admin/recording/<int:recording_id>')
@login_required
def admin_recording_detail(recording_id):
    """Admin detailed view of a recording"""
    try:
        recording = db.session.query(Recording, User).join(User)\
            .filter(Recording.id == recording_id).first_or_404()
        
        # Parse upload metadata if available
        upload_metadata = None
        if recording.Recording.upload_metadata:
            try:
                upload_metadata = json.loads(recording.Recording.upload_metadata)
            except:
                pass
        
        return render_template('admin/recording_detail.html', 
                             recording=recording,
                             upload_metadata=upload_metadata)
        
    except Exception as e:
        logger.error(f"❌ Admin recording detail error: {e}")
        return f"Database error: {e}", 500

@app.route('/admin/recordings/<int:recording_id>/serve')
@login_required
def serve_recording(recording_id):
    """Serve recording video file"""
    try:
        recording = Recording.query.get_or_404(recording_id)
        
        # Check if file exists locally
        if recording.file_exists:
            file_path = recording.resolved_file_path
            return send_file(file_path, as_attachment=False, mimetype='video/mp4')
        else:
            # Redirect to cloud URL if available
            if recording.cloud_video_url:
                return redirect(recording.cloud_video_url)
            else:
                return "Recording file not found", 404
                
    except Exception as e:
        logger.error(f"❌ Error serving recording {recording_id}: {e}")
        return "Error serving recording", 500

@app.route('/admin/recordings/<int:recording_id>/transcript')
@login_required
def serve_transcript(recording_id):
    """Serve recording transcript"""
    try:
        recording = Recording.query.get_or_404(recording_id)
        
        # Check if transcript exists locally
        if recording.has_transcript:
            transcript_path = recording.transcript_path
            with open(transcript_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return Response(content, mimetype='text/plain')
        else:
            # Try cloud transcript URL
            if recording.cloud_transcript_url:
                return redirect(recording.cloud_transcript_url)
            else:
                return "Transcript not found", 404
                
    except Exception as e:
        logger.error(f"❌ Error serving transcript {recording_id}: {e}")
        return "Error serving transcript", 500

@app.route('/admin/users')
@login_required
def admin_users():
    """Admin users list with statistics"""
    try:
        from datetime import datetime, timedelta
        
        # Get all users
        users = User.query.all()
        users_data = []
        
        for user in users:
            # Get user's recordings
            recordings = Recording.query.filter_by(user_id=user.id).all()
            recording_count = len(recordings)
            
            # Calculate totals
            total_size = sum(r.file_size or 0 for r in recordings)
            total_duration = sum(r.duration or 0 for r in recordings)
            uploaded_count = sum(1 for r in recordings if r.uploaded)
            
            users_data.append((user, recording_count, total_size, total_duration, uploaded_count))
        
        # Calculate additional stats
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_users = sum(1 for user, _, _, _, _ in users_data 
                          if user.created_at and user.created_at > thirty_days_ago)
        
        return render_template('admin/users.html', 
                             users_data=users_data,
                             recent_users=recent_users)
        
    except Exception as e:
        logger.error(f"❌ Admin users error: {e}")
        return f"Database error: {e}", 500

@app.route('/admin/api/stats')
@login_required
def admin_api_stats():
    """API endpoint for admin dashboard stats"""
    try:
        total_recordings = Recording.query.count()
        uploaded = Recording.query.filter_by(uploaded=True).count()
        uploading = Recording.query.filter_by(upload_status='uploading').count()
        failed = Recording.query.filter_by(upload_status='failed').count()
        
        return jsonify({
            'total_recordings': total_recordings,
            'uploaded': uploaded,
            'uploading': uploading,
            'failed': failed,
            'local_only': total_recordings - uploaded
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Simple APScheduler for failed upload retry - defined but not started yet
def check_and_retry_failed():
    """Check for failed uploads and retry them"""
    with app.app_context():  # Flask application context
        try:
            failed = Recording.query.filter_by(upload_status='failed').all()
            if failed:
                logger.info(f"🔄 Found {len(failed)} failed uploads, retrying...")
                for recording in failed:
                    from background_uploader import trigger_upload
                    trigger_upload(recording.id)
                    # Removed time.sleep(1) - let background_uploader handle timing
            else:
                logger.debug("✅ No failed uploads found")
        except Exception as e:
            logger.error(f"❌ Retry check failed: {e}")

@app.route('/admin')
@login_required
def admin():
    """Admin dashboard to view meetings and recordings"""
    try:
        # Get meetings and recordings for the current user
        meetings = Meeting.query.filter_by(user_id=current_user.id).order_by(Meeting.start_time.desc()).all()
        recordings = Recording.query.filter_by(user_id=current_user.id).order_by(Recording.created_at.desc()).all()
        
        # Get some statistics
        total_meetings = len(meetings)
        recorded_meetings = len([m for m in meetings if m.recording])
        upcoming_meetings = len([m for m in meetings if m.is_upcoming])
        orphaned_recordings = len([r for r in recordings if not r.meeting])
        
        stats = {
            'total_meetings': total_meetings,
            'recorded_meetings': recorded_meetings,
            'upcoming_meetings': upcoming_meetings,
            'orphaned_recordings': orphaned_recordings,
            'total_recordings': len(recordings)
        }
        
        return render_template('admin/dashboard.html', 
                             meetings=meetings[:20],  # Show last 20 meetings
                             recordings=recordings[:10],  # Show last 10 recordings
                             stats=stats)
    except Exception as e:
        logger.error(f"❌ Admin dashboard error: {str(e)}")
        flash(f"Error loading admin dashboard: {str(e)}", "error")
        return redirect(url_for('dashboard'))

@app.route('/admin/meetings')
@login_required
def admin_meetings():
    """Admin page to view all meetings"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        
        # Get filter parameters
        filter_status = request.args.get('filter', 'all')
        
        # Calculate statistics for all meetings
        total_meetings = Meeting.query.count()
        recorded_meetings = Meeting.query.filter(Meeting.recording_status.in_(['recorded_synced', 'recorded_local'])).count()
        scheduled_meetings = Meeting.query.filter_by(recording_status='scheduled').count()
        upcoming_meetings = Meeting.query.filter(Meeting.start_time > datetime.utcnow()).count()
        no_recording_meetings = Meeting.query.filter(Meeting.recording_id.is_(None)).count()
        
        # Calculate total attendees (sum of attendee_count for all meetings)
        total_attendees = db.session.query(db.func.sum(Meeting.attendee_count)).scalar() or 0
        
        # Build query based on filter
        query = Meeting.query
        
        # Apply filters
        if filter_status == 'recorded':
            query = query.filter(Meeting.recording_status.in_(['recorded_synced', 'recorded_local']))
        elif filter_status == 'scheduled':
            query = query.filter_by(recording_status='scheduled')
        elif filter_status == 'upcoming':
            query = query.filter(Meeting.start_time > datetime.utcnow())
        elif filter_status == 'orphaned':
            query = query.filter(Meeting.recording_id.is_(None))
        
        # Get meetings for display - sorted by newest first (descending)
        meetings_paginated = query.order_by(Meeting.start_time.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Prepare stats dictionary
        stats = {
            'total_meetings': total_meetings,
            'recorded_meetings': recorded_meetings,
            'scheduled_meetings': scheduled_meetings,
            'upcoming_meetings': upcoming_meetings,
            'no_recording_meetings': no_recording_meetings,
            'total_attendees': total_attendees
        }
        
        return render_template('admin/meetings.html', 
                             meetings=meetings_paginated.items,
                             pagination=meetings_paginated,
                             stats=stats,
                             filter_status=filter_status)
    except Exception as e:
        logger.error(f"❌ Admin meetings error: {str(e)}")
        flash(f"Error loading meetings: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/meetings/<int:meeting_id>/exclude', methods=['POST'])
@login_required
def toggle_meeting_exclusion(meeting_id):
    """Toggle exclusion status for a single meeting"""
    try:
        data = request.get_json()
        excluded = data.get('excluded', False)
        
        meeting = Meeting.query.get_or_404(meeting_id)
        meeting.user_excluded = excluded
        
        db.session.commit()
        
        logger.info(f"Meeting {meeting_id} exclusion updated to: {excluded}")
        
        return jsonify({
            'success': True,
            'meeting_id': meeting_id,
            'excluded': excluded
        })
    except Exception as e:
        logger.error(f"❌ Error updating meeting exclusion: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/meetings/exclude-series', methods=['POST'])
@login_required
def toggle_series_exclusion():
    """Toggle exclusion status for an entire recurring series"""
    try:
        data = request.get_json()
        series_id = data.get('series_id')
        excluded = data.get('excluded', False)
        
        if not series_id:
            return jsonify({
                'success': False,
                'error': 'Missing series_id'
            }), 400
        
        # Update all meetings with this series_id
        meetings = Meeting.query.filter_by(series_id=series_id).all()
        
        if not meetings:
            # If no series_id match, try calendar_event_id
            meetings = Meeting.query.filter_by(calendar_event_id=series_id).all()
        
        updated_count = 0
        for meeting in meetings:
            meeting.exclude_all_series = excluded
            meeting.user_excluded = excluded  # Also set individual exclusion
            updated_count += 1
        
        db.session.commit()
        
        logger.info(f"Updated {updated_count} meetings in series {series_id} to excluded={excluded}")
        
        return jsonify({
            'success': True,
            'series_id': series_id,
            'excluded': excluded,
            'updated_count': updated_count
        })
    except Exception as e:
        logger.error(f"❌ Error updating series exclusion: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/admin/meetings/<int:meeting_id>')
@login_required
def admin_meeting_detail(meeting_id):
    """Admin page to view detailed meeting information"""
    try:
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Get available recordings that can be linked to this meeting (not already linked to any meeting)
        available_recordings = Recording.query.filter(~Recording.id.in_(
            db.session.query(Meeting.recording_id).filter(Meeting.recording_id.isnot(None))
        )).all()
        
        return render_template('admin/meeting_detail.html', 
                             meeting=meeting,
                             available_recordings=available_recordings)
    except Exception as e:
        logger.error(f"❌ Admin meeting detail error: {str(e)}")
        flash(f"Error loading meeting details: {str(e)}", "error")
        return redirect(url_for('admin_meetings'))

@app.route('/admin/meetings/<int:meeting_id>/link_recording', methods=['POST'])
@login_required
def admin_link_recording(meeting_id):
    """Link a recording to a meeting"""
    try:
        meeting = Meeting.query.get_or_404(meeting_id)
        recording_id = request.form.get('recording_id')
        
        if recording_id:
            recording = Recording.query.get(recording_id)
            # Check if recording is not already linked to another meeting
            existing_meeting = Meeting.query.filter_by(recording_id=recording_id).first()
            if recording and not existing_meeting:
                meeting.recording_id = recording_id
                meeting.recording_status = 'recorded_local' if not recording.uploaded else 'recorded_synced'
                db.session.commit()
                flash(f"Recording '{recording.title}' linked to meeting successfully!", "success")
            else:
                flash("Recording not found or already linked to another meeting.", "error")
        
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))
    except Exception as e:
        logger.error(f"❌ Admin link recording error: {str(e)}")
        flash(f"Error linking recording: {str(e)}", "error")
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))

@app.route('/admin/meetings/<int:meeting_id>/unlink_recording', methods=['POST'])
@login_required
def admin_unlink_recording(meeting_id):
    """Unlink a recording from a meeting"""
    try:
        meeting = Meeting.query.get_or_404(meeting_id)
        
        if meeting.recording:
            meeting.recording_id = None
            meeting.recording_status = 'scheduled'
            db.session.commit()
            flash("Recording unlinked from meeting successfully!", "success")
        else:
            flash("No recording linked to this meeting.", "warning")
        
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))
    except Exception as e:
        logger.error(f"❌ Admin unlink recording error: {str(e)}")
        flash(f"Error unlinking recording: {str(e)}", "error")
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))

@app.route('/admin/meetings/<int:meeting_id>/sync', methods=['POST'])
@login_required
def admin_sync_single_meeting(meeting_id):
    """Refresh data for a single meeting"""
    try:
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Here you would call your calendar sync logic for this specific meeting
        # For now, just update the timestamp
        meeting.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash("Meeting data refreshed successfully!", "success")
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))
    except Exception as e:
        logger.error(f"❌ Admin sync single meeting error: {str(e)}")
        flash(f"Error syncing meeting: {str(e)}", "error")
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))

@app.route('/admin/meetings/<int:meeting_id>/delete', methods=['POST'])
@login_required
def admin_delete_meeting(meeting_id):
    """Delete a meeting"""
    try:
        meeting = Meeting.query.get_or_404(meeting_id)
        
        # Unlink any associated recording first
        if meeting.recording:
            meeting.recording_id = None
        
        db.session.delete(meeting)
        db.session.commit()
        
        flash("Meeting deleted successfully!", "success")
        return redirect(url_for('admin_meetings'))
    except Exception as e:
        logger.error(f"❌ Admin delete meeting error: {str(e)}")
        flash(f"Error deleting meeting: {str(e)}", "error")
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))

def fetch_and_sync_calendar_events(user):
    """Fetch calendar events and create/update Meeting records"""
    try:
        logger.info(f"🗓️ Syncing calendar events for {user.email}")
        
        # Power Automate data (same format as AutoRecorder)
        # Sync only 1 week: today + 6 days forward for daily sync operations
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)  # 7 days total (today + 6 more)
        
        data = {
            'cal_id': CALENDAR_ID,
            'start_date': start_date.isoformat() + 'Z',
            'end_date': end_date.isoformat() + 'Z',
            'email': user.email
        }
        
        # Send request to Power Automate
        response = requests.post(
            WORKFLOW_URL,
            headers={'Content-Type': 'application/json'},
            json=data,
            timeout=30
        )
        
        if response.status_code not in [200, 201, 202]:
            raise Exception(f"Calendar service error: {response.status_code}")
            
        events = response.json()
        if not isinstance(events, list):
            raise Exception("Unexpected response format from calendar service")
            
        logger.info(f"✅ Found {len(events)} raw events")
        
        # Filter out all-day events and non-Teams meetings
        filtered_events = []
        all_day_count = 0
        non_teams_count = 0
        internal_only_count = 0
        
        for event in events:
            # Check if event is all-day
            is_all_day = False
            
            if event.get('isAllDay') is True:
                is_all_day = True
            elif event.get('start') and event.get('end'):
                try:
                    start_str = event['start']
                    end_str = event['end']
                    
                    if 'T00:00:00' in start_str and ('T00:00:00' in end_str or 'T23:59:59' in end_str):
                        start_dt = datetime.fromisoformat(start_str.replace('.0000000', ''))
                        end_dt = datetime.fromisoformat(end_str.replace('.0000000', ''))
                        duration_hours = (end_dt - start_dt).total_seconds() / 3600
                        if duration_hours >= 23.5:
                            is_all_day = True
                except:
                    pass
            
            subject = event.get('subject', '').lower()
            if any(keyword in subject for keyword in ['birthday', 'holiday', 'vacation', 'pto', 'out of office']):
                is_all_day = True
            
            if is_all_day:
                all_day_count += 1
                continue
            
            # Check if event is a Teams meeting
            is_teams_meeting = False
            teams_indicators = [
                'teams.microsoft.com', 'teams.live.com', 'meet.lync.com',
                'join microsoft teams meeting', 'microsoft teams meeting', 'teams meeting'
            ]
            
            web_link = event.get('webLink', '').lower()
            body = event.get('body', '').lower()
            location = event.get('location', '').lower()
            
            if (any(indicator in web_link for indicator in teams_indicators) or
                any(indicator in body for indicator in teams_indicators) or
                any(indicator in location for indicator in teams_indicators) or
                any(indicator in subject for indicator in ['teams', 'meeting']) or
                event.get('onlineMeeting') or event.get('isOnlineMeeting') or
                event.get('requiredAttendees') or event.get('attendees')):
                is_teams_meeting = True
            
            if not is_teams_meeting:
                non_teams_count += 1
                continue
            
            # Check if meeting is internal-only (all participants @fyelabs.com)
            # Extract all email addresses from the meeting
            all_emails = []
            
            # Get organizer email
            if event.get('organizer'):
                organizer_data = event['organizer']
                if isinstance(organizer_data, dict):
                    organizer_email = organizer_data.get('emailAddress', {}).get('address', '')
                    if organizer_email:
                        all_emails.append(organizer_email.lower())
            
            # Get attendees emails
            if event.get('requiredAttendees'):
                attendees = [email.strip().lower() for email in event['requiredAttendees'].split(';') if email.strip()]
                all_emails.extend(attendees)
            
            if event.get('optionalAttendees'):
                optional = [email.strip().lower() for email in event['optionalAttendees'].split(';') if email.strip()]
                all_emails.extend(optional)
            
            # Remove duplicates
            all_emails = list(set(all_emails))
            
            # Check if ALL participants are @fyelabs.com
            if all_emails:  # Only check if we have participant data
                is_internal_only = all(email.endswith('@fyelabs.com') for email in all_emails)
                
                if is_internal_only:
                    internal_only_count += 1
                    logger.debug(f"🔒 Skipping internal-only meeting: {event.get('subject', 'No Title')} - All {len(all_emails)} participants are @fyelabs.com")
                    continue
                
            filtered_events.append(event)
        
        logger.info(f"✅ After filtering - {len(filtered_events)} events remaining ({all_day_count} all-day, {non_teams_count} non-Teams, {internal_only_count} internal-only removed)")
        
        # Create/update Meeting records
        meetings_created = 0
        meetings_updated = 0
        meetings_skipped = 0
        
        # Track processed meetings to detect duplicates within the current batch
        processed_events = set()
        
        for event in filtered_events:
            try:
                # Parse event data
                event_id = event.get('id') or event.get('iCalUId')
                subject = event.get('subject', 'No Title')
                
                # Parse start/end times and convert to Eastern time
                start_time = None
                end_time = None
                
                if event.get('start'):
                    start_time = parse_calendar_datetime(event['start'])
                if event.get('end'):
                    end_time = parse_calendar_datetime(event['end'])
                
                if not start_time or not end_time:
                    continue
                
                # Create a unique key for duplicate detection
                # Use multiple criteria: time + subject + organizer for robust duplicate detection
                organizer = event.get('organizer', {}).get('emailAddress', {}).get('address', '') if isinstance(event.get('organizer'), dict) else ''
                duplicate_key = f"{start_time.isoformat()}|{end_time.isoformat()}|{subject.lower().strip()}|{organizer.lower()}"
                
                # Skip if we've already processed this exact meeting in this batch
                if duplicate_key in processed_events:
                    logger.debug(f"🔄 Skipping duplicate in batch: {subject} at {start_time}")
                    meetings_skipped += 1
                    continue
                    
                processed_events.add(duplicate_key)
                
                # Process attendees
                attendees_json = None
                attendee_count = 0
                if event.get('requiredAttendees'):
                    attendees = [email.strip() for email in event['requiredAttendees'].split(';') if email.strip()]
                    if attendees:
                        import json
                        attendees_json = json.dumps(attendees)
                        attendee_count = len(attendees)
                
                # Calculate duration
                duration_minutes = None
                if start_time and end_time:
                    duration_minutes = int((end_time - start_time).total_seconds() / 60)
                
                # Detect if this is a recurring meeting
                is_recurring = bool(event.get('seriesMasterId'))
                series_id = event.get('seriesMasterId') if is_recurring else None
                
                # Check for existing meetings using multiple criteria
                existing_meeting = None
                
                # Method 1: Try to find by calendar_event_id (exact match)
                if event_id:
                    existing_meeting = Meeting.query.filter_by(
                        calendar_event_id=event_id,
                        user_id=user.id
                    ).first()
                
                # Method 2: If no event_id match, check for duplicates by time + subject
                if not existing_meeting:
                    # Look for meetings with same start time, subject, and user within a 5-minute window
                    time_tolerance = timedelta(minutes=5)
                    existing_meeting = Meeting.query.filter(
                        Meeting.user_id == user.id,
                        Meeting.subject == subject,
                        Meeting.start_time.between(
                            start_time - time_tolerance,
                            start_time + time_tolerance
                        )
                    ).first()
                
                # Method 3: If still no match, check for same subject + date (different times = different meeting)
                if not existing_meeting and duration_minutes and duration_minutes > 0:
                    # Only check same-day meetings with similar duration (within 15 minutes)
                    same_day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    same_day_end = same_day_start + timedelta(days=1)
                    
                    similar_meetings = Meeting.query.filter(
                        Meeting.user_id == user.id,
                        Meeting.subject == subject,
                        Meeting.start_time.between(same_day_start, same_day_end),
                        Meeting.duration_minutes.between(
                            max(1, duration_minutes - 15),
                            duration_minutes + 15
                        )
                    ).all()
                    
                    # Check if any of these are really close in time (probable duplicates)
                    for similar in similar_meetings:
                        time_diff = abs((similar.start_time - start_time).total_seconds())
                        if time_diff < 300:  # Within 5 minutes
                            existing_meeting = similar
                            logger.debug(f"🔍 Found potential duplicate by subject+time: {subject}")
                            break
                
                if existing_meeting:
                    # Update existing meeting with latest information
                    existing_meeting.subject = subject
                    existing_meeting.start_time = start_time
                    existing_meeting.end_time = end_time
                    existing_meeting.duration_minutes = duration_minutes
                    existing_meeting.required_attendees = attendees_json
                    existing_meeting.attendee_count = attendee_count
                    existing_meeting.location = event.get('location', '')
                    existing_meeting.web_link = event.get('webLink', '')
                    existing_meeting.organizer = organizer
                    existing_meeting.is_teams_meeting = True
                    existing_meeting.is_recurring = is_recurring
                    existing_meeting.series_id = series_id
                    existing_meeting.last_updated = datetime.utcnow()
                    
                    # Update calendar_event_id if it was missing
                    if event_id and not existing_meeting.calendar_event_id:
                        existing_meeting.calendar_event_id = event_id
                    
                    meetings_updated += 1
                else:
                    # Create new meeting
                    new_meeting = Meeting(
                        calendar_event_id=event_id,
                        subject=subject,
                        start_time=start_time,
                        end_time=end_time,
                        duration_minutes=duration_minutes,
                        required_attendees=attendees_json,
                        attendee_count=attendee_count,
                        location=event.get('location', ''),
                        web_link=event.get('webLink', ''),
                        organizer=organizer,
                        is_teams_meeting=True,
                        is_recurring=is_recurring,
                        series_id=series_id,
                        user_id=user.id,
                        auto_record=False  # Default to not auto-record
                    )
                    db.session.add(new_meeting)
                    meetings_created += 1
                    
            except Exception as e:
                logger.error(f"❌ Error processing event {event.get('subject', 'Unknown')}: {str(e)}")
                continue
        
        db.session.commit()
        logger.info(f"✅ Calendar sync complete: {meetings_created} created, {meetings_updated} updated, {meetings_skipped} duplicates skipped")
        return meetings_created, meetings_updated, len(filtered_events)
        
    except Exception as e:
        logger.error(f"❌ Calendar sync error: {str(e)}")
        db.session.rollback()
        raise e

def auto_sync_calendar_for_all_users():
    """Automatically sync calendar for all users - called by scheduler"""
    try:
        logger.info("🕐 Auto calendar sync: Starting daily sync for all users")
        
        users = User.query.all()
        total_created = 0
        total_updated = 0
        users_synced = 0
        
        for user in users:
            try:
                created, updated, total_events = fetch_and_sync_calendar_events(user)
                total_created += created
                total_updated += updated
                users_synced += 1
                logger.info(f"✅ Auto sync for {user.email}: {created} created, {updated} updated")
            except Exception as e:
                logger.error(f"❌ Auto sync failed for {user.email}: {str(e)}")
                continue
        
        logger.info(f"🕐 Auto calendar sync complete: {users_synced} users, {total_created} total created, {total_updated} total updated")
        
    except Exception as e:
        logger.error(f"❌ Auto calendar sync error: {str(e)}")

@app.route('/admin/sync_calendar', methods=['POST'])
@login_required  
def admin_sync_calendar():
    """Sync calendar and create/update meetings"""
    try:
        logger.info("🗓️ Admin: Manual calendar sync triggered")
        
        created, updated, total = fetch_and_sync_calendar_events(current_user)
        
        flash(f"Calendar sync completed! {created} meetings created, {updated} updated from {total} calendar events.", "success")
        return redirect(request.referrer or url_for('admin_dashboard'))
    except Exception as e:
        logger.error(f"❌ Admin calendar sync error: {str(e)}")
        flash(f"Error syncing calendar: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/cleanup-duplicates', methods=['POST'])
@login_required
def admin_cleanup_duplicates():
    """Remove duplicate meetings from the database"""
    try:
        logger.info("🧹 Admin: Manual duplicate cleanup triggered")
        
        # Find duplicates based on subject + start_time + user_id
        from sqlalchemy import func
        
        # Get meetings that have duplicates (same subject, start time within 5 minutes, same user)
        duplicates_query = db.session.query(
            Meeting.subject,
            Meeting.user_id,
            func.date(Meeting.start_time).label('meeting_date')
        ).filter(
            Meeting.user_id == current_user.id
        ).group_by(
            Meeting.subject,
            Meeting.user_id, 
            func.date(Meeting.start_time)
        ).having(func.count(Meeting.id) > 1)
        
        duplicates_removed = 0
        
        for duplicate_group in duplicates_query.all():
            subject, user_id, meeting_date = duplicate_group
            
            # Get all meetings for this subject on this date
            same_meetings = Meeting.query.filter(
                Meeting.subject == subject,
                Meeting.user_id == user_id,
                func.date(Meeting.start_time) == meeting_date
            ).order_by(Meeting.start_time, Meeting.last_updated.desc()).all()
            
            if len(same_meetings) <= 1:
                continue
                
            # Group by start time (within 5 minutes tolerance)
            time_groups = {}
            for meeting in same_meetings:
                # Round to nearest 5-minute interval for grouping
                rounded_time = meeting.start_time.replace(
                    minute=(meeting.start_time.minute // 5) * 5,
                    second=0,
                    microsecond=0
                )
                
                if rounded_time not in time_groups:
                    time_groups[rounded_time] = []
                time_groups[rounded_time].append(meeting)
            
            # For each time group, keep the most complete/recent one
            for time_group in time_groups.values():
                if len(time_group) <= 1:
                    continue
                    
                # Sort by completeness (has calendar_event_id, has recording, most recent)
                time_group.sort(key=lambda m: (
                    bool(m.calendar_event_id),
                    bool(m.recording_id),
                    m.last_updated or m.discovered_at
                ), reverse=True)
                
                # Keep the first (best) one, delete the rest
                best_meeting = time_group[0]
                duplicates_to_remove = time_group[1:]
                
                for duplicate in duplicates_to_remove:
                    logger.info(f"🗑️ Removing duplicate: {duplicate.subject} at {duplicate.start_time}")
                    db.session.delete(duplicate)
                    duplicates_removed += 1
        
        db.session.commit()
        
        if duplicates_removed > 0:
            logger.info(f"✅ Cleanup complete: {duplicates_removed} duplicate meetings removed")
            flash(f"Cleanup completed! {duplicates_removed} duplicate meetings removed.", "success")
        else:
            logger.info("✅ No duplicates found to remove")
            flash("No duplicate meetings found to remove.", "info")
            
        return redirect(request.referrer or url_for('admin_dashboard'))
        
    except Exception as e:
        logger.error(f"❌ Duplicate cleanup error: {str(e)}")
        db.session.rollback()
        flash(f"Error during cleanup: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/auto-sync-test', methods=['POST'])
@login_required
def admin_test_auto_sync():
    """Manually trigger auto-sync for testing"""
    try:
        logger.info("🧪 Admin: Manual auto-sync test triggered")
        
        auto_sync_calendar_for_all_users()
        
        flash("Auto-sync test completed! Check logs for details.", "success")
        return redirect(request.referrer or url_for('admin_dashboard'))
        
    except Exception as e:
        logger.error(f"❌ Auto-sync test error: {str(e)}")
        flash(f"Auto-sync test failed: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/meetings/<int:meeting_id>/toggle-recording', methods=['POST'])
@login_required
def admin_toggle_meeting_recording(meeting_id):
    """Toggle auto-recording for a meeting"""
    try:
        meeting = Meeting.query.filter_by(id=meeting_id, user_id=current_user.id).first_or_404()
        
        # Toggle auto-record flag
        meeting.auto_record = not meeting.auto_record
        
        # Update recording status
        if meeting.auto_record:
            meeting.is_excluded = False
            if meeting.is_upcoming:
                meeting.recording_status = 'scheduled'
        else:
            meeting.is_excluded = True
            meeting.recording_status = 'excluded'
        
        db.session.commit()
        
        action = "enabled" if meeting.auto_record else "disabled"
        flash(f"Auto-recording {action} for '{meeting.subject}'", "success")
        
        return redirect(url_for('admin_meeting_detail', meeting_id=meeting_id))
    except Exception as e:
        logger.error(f"❌ Toggle recording error: {str(e)}")
        flash(f"Error updating meeting: {str(e)}", "error")
        return redirect(url_for('admin_meetings'))

def start_scheduler():
    """Start the background scheduler for retry and calendar sync"""
    scheduler = BackgroundScheduler()
    
    # Add retry job (every 5 minutes)
    scheduler.add_job(check_and_retry_failed, 'interval', minutes=5, id='retry_failed')
    
    # Add daily calendar sync job (every day at 6 AM)
    scheduler.add_job(auto_sync_calendar_for_all_users, 'cron', hour=6, minute=0, id='daily_calendar_sync')
    
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())
    logger.info("🔄 Background scheduler started:")
    logger.info("   - Retry failed uploads: every 5 minutes")
    logger.info("   - Calendar sync: daily at 6:00 AM")
    return scheduler

def cleanup_stuck_recordings():
    """Clean up any recordings stuck in 'recording' state on startup"""
    try:
        logger.info("🧹 Checking for stuck recordings on startup...")
        stuck_recordings = Recording.query.filter_by(status='recording').all()
        
        if stuck_recordings:
            logger.warning(f"⚠️ Found {len(stuck_recordings)} stuck recording(s), cleaning up...")
            for recording in stuck_recordings:
                logger.info(f"   🔧 Fixing stuck recording ID: {recording.id} - {recording.title}")
                recording.status = 'failed'
                recording.ended_at = datetime.utcnow()
                recording.duration = 0
            
            db.session.commit()
            logger.info("✅ Cleanup complete - all stuck recordings marked as failed")
        else:
            logger.info("✅ No stuck recordings found")
            
        # Also reset global recording state
        recording_state['active'] = False
        recording_state['streamer'] = None
        recording_state['thread'] = None
        recording_state['recording_id'] = None
        logger.info("🔄 Global recording state reset")
        
    except Exception as e:
        logger.error(f"❌ Error during startup cleanup: {str(e)}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
        cleanup_stuck_recordings()  # Clean up any stuck recordings
    
    # Start the retry scheduler after Flask is ready
    scheduler = start_scheduler()
    
    app.run(debug=True, host='0.0.0.0', port=5000)