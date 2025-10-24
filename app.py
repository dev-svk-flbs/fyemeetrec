#!/usr/bin/env python3
"""
Flask Web Interface for Dual Stream Recording with Authentication
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, send_file, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from dual_stream import DualModeStreamer
from models import db, User, Recording, init_db
from settings_config import settings_manager
from logging_config import app_logger as logger
import requests
import threading
import time
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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Global state
recording_state = {
    'active': False,
    'streamer': None,
    'thread': None,
    'transcriptions': [],
    'selected_monitor': None
}

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
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        else:
            return jsonify({'success': False, 'message': 'Invalid username or password'})
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long')
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            errors.append('Username already exists')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered')
        
        if errors:
            return jsonify({'success': False, 'errors': errors})
        
        # Create new user
        try:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            
            # Auto-login the new user
            login_user(new_user, remember=True)
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'errors': ['Registration failed. Please try again.']})
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get recent recordings
    recent_recordings = Recording.query.filter_by(user_id=current_user.id)\
        .order_by(Recording.created_at.desc()).limit(6).all()
    
    # Get recording stats
    total_recordings = Recording.query.filter_by(user_id=current_user.id).count()
    total_duration = db.session.query(db.func.sum(Recording.duration))\
        .filter_by(user_id=current_user.id).scalar() or 0
    
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
    
    # Start with base query
    query = Recording.query.filter_by(user_id=current_user.id)
    
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
@login_required
def start_recording():
    logger.info(f"🎬 Recording start requested by user: {current_user.username}")
    
    if recording_state['active']:
        logger.warning(f"⚠️ Recording already active - rejecting request from {current_user.username}")
        return jsonify({'error': 'Already recording'}), 400
    
    # Get monitor selection and title from request
    data = request.get_json() or {}
    monitor_id = data.get('monitor_id')
    recording_title = data.get('title', f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    logger.info(f"📝 Recording request details:")
    logger.info(f"   Title: {recording_title}")
    logger.info(f"   Requested Monitor ID: {monitor_id}")
    logger.info(f"   Request data: {data}")
    
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
        return jsonify({'error': 'Invalid monitor selection'}), 400
    
    logger.info(f"📺 Selected monitor configuration:")
    logger.info(f"   ID: {selected_monitor['id']}")
    logger.info(f"   Name: {selected_monitor['name']}")
    logger.info(f"   Position: ({selected_monitor['x']}, {selected_monitor['y']})")
    logger.info(f"   Size: {selected_monitor['width']}x{selected_monitor['height']}")
    logger.info(f"   Primary: {selected_monitor.get('primary', False)}")
    
    # Create database record for this recording
    logger.info("💾 Creating database record...")
    recording = Recording(
        title=recording_title,
        filename='',  # Will be set when recording completes
        file_path='',  # Will be set when recording completes
        started_at=datetime.utcnow(),
        monitor_name=selected_monitor['name'],
        resolution=f"{selected_monitor['width']}x{selected_monitor['height']}",
        user_id=current_user.id,
        status='recording'
    )
    db.session.add(recording)
    db.session.commit()
    logger.info(f"✅ Database record created with ID: {recording.id}")
    
    # Store selected monitor and recording ID
    recording_state['selected_monitor'] = selected_monitor
    recording_state['recording_id'] = recording.id
    
    # Create streamer instance with monitor config
    logger.info("🚀 Creating DualModeStreamer instance...")
    recording_state['streamer'] = DualModeStreamer(
        monitor_config=selected_monitor
    )
    recording_state['active'] = True
    recording_state['transcriptions'] = []
    
    logger.info("✅ Recording state updated and streamer created")
    
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
@login_required
def stop_recording():
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
        # Wait briefly for thread to exit
        if recording_state.get('thread'):
            recording_state['thread'].join(timeout=5)
    
    recording_state['active'] = False
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



@app.route('/video/<int:recording_id>')
@login_required
def serve_video(recording_id):
    """Serve video file for playback"""
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
    try:
        upload_transcript_to_server(recording)
        return jsonify({
            'success': True,
            'message': f'Transcript upload started for "{recording.title}"'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Upload failed: {str(e)}'
        }), 500

@app.route('/download-transcript/<int:recording_id>')
@login_required
def download_transcript(recording_id):
    """Download transcript file for a recording"""
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    
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
    all_recordings = Recording.query.filter_by(user_id=current_user.id).all()
    
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
    
    return render_template('settings.html', 
                         user=settings_user, 
                         monitors=monitors,
                         monitors_detected=monitors_detected)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    app.run(debug=True, host='0.0.0.0', port=5000)