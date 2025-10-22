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
import threading
import time
import subprocess
import json
import re
import os
import mimetypes
from pathlib import Path

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

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = None  # Disable automatic login messages
login_manager.login_message_category = 'info'

# Initialize database
init_db(app)

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
    """Get monitor manufacturer info using WMI InstanceNames"""
    try:
        # Get WMI monitor basic display params which includes InstanceName with manufacturer codes
        wmi_command = 'Get-WmiObject -Namespace root\\wmi -Class WmiMonitorBasicDisplayParams | Select-Object InstanceName | ConvertTo-Json'
        
        result = subprocess.run([
            'powershell', '-Command', wmi_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            wmi_data = json.loads(result.stdout.strip())
            if isinstance(wmi_data, dict):
                wmi_data = [wmi_data]
            
            # Manufacturer code to name mapping
            manufacturer_codes = {
                'LEN': 'Lenovo',
                'HKC': 'HKC',
                'ACR': 'Acer', 
                'SAM': 'Samsung',
                'DEL': 'Dell',
                'AOC': 'AOC',
                'BNQ': 'BenQ',
                'ASU': 'ASUS',
                'MSI': 'MSI',
                'LG': 'LG',
                'HP': 'HP'
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
    """Get list of available monitors using PowerShell with manufacturer info"""
    try:
        # Get manufacturer info first
        manufacturer_list = get_monitor_manufacturers()
        
        # PowerShell command to get monitor info - using single line approach
        ps_command = 'Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Screen]::AllScreens | ForEach-Object { [PSCustomObject]@{ DeviceName = $_.DeviceName; Primary = $_.Primary; X = $_.Bounds.X; Y = $_.Bounds.Y; Width = $_.Bounds.Width; Height = $_.Bounds.Height } } | ConvertTo-Json'
        
        result = subprocess.run([
            'powershell', '-Command', ps_command
        ], capture_output=True, text=True, shell=False)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"PowerShell output: {result.stdout.strip()}")  # Debug line
            monitors_data = json.loads(result.stdout.strip())
            
            # Handle single monitor case (JSON returns dict instead of list)
            if isinstance(monitors_data, dict):
                monitors_data = [monitors_data]
            
            # Format monitor info for UI
            monitors = []
            for i, monitor in enumerate(monitors_data):
                # Try to get manufacturer info - match by index since both are ordered
                manufacturer_info = ""
                if i < len(manufacturer_list):
                    mfg = manufacturer_list[i]
                    if mfg['product_id']:
                        manufacturer_info = f" ({mfg['name']} {mfg['product_id']})"
                    else:
                        manufacturer_info = f" ({mfg['name']})"
                
                # Build display name with manufacturer if available
                display_name = f"Monitor {i+1}{manufacturer_info}"
                if monitor['Primary']:
                    display_name += " - Primary"
                display_name += f" - {monitor['Width']}x{monitor['Height']}"
                if monitor['X'] != 0 or monitor['Y'] != 0:
                    display_name += f" at ({monitor['X']}, {monitor['Y']})"
                
                monitors.append({
                    'id': i,
                    'name': display_name,
                    'device_name': monitor['DeviceName'],
                    'primary': monitor['Primary'],
                    'x': monitor['X'],
                    'y': monitor['Y'],
                    'width': monitor['Width'],
                    'height': monitor['Height']
                })
            
            return monitors
        else:
            # Fallback if PowerShell fails
            print(f"PowerShell failed: returncode={result.returncode}, stderr={result.stderr}")  # Debug line
            return [{'id': 0, 'name': 'Primary Monitor (Default)', 'x': 0, 'y': 0, 'width': 1920, 'height': 1080, 'primary': True}]
            
    except Exception as e:
        print(f"Error getting monitors: {e}")
        return [{'id': 0, 'name': 'Primary Monitor (Default)', 'x': 0, 'y': 0, 'width': 1920, 'height': 1080, 'primary': True}]

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
    recordings = Recording.query.filter_by(user_id=current_user.id)\
        .order_by(Recording.created_at.desc())\
        .paginate(page=page, per_page=12, error_out=False)
    
    return render_template('recordings.html', recordings=recordings)

@app.route('/record')
@login_required
def record():
    monitors = get_monitors()
    return render_template('record.html', 
                         monitors=monitors, 
                         default_monitor=current_user.default_monitor)

@app.route('/monitors')
@login_required
def list_monitors():
    """API endpoint to get available monitors"""
    monitors = get_monitors()
    return jsonify({'monitors': monitors})

@app.route('/start', methods=['POST'])
@login_required
def start_recording():
    if recording_state['active']:
        return jsonify({'error': 'Already recording'}), 400
    
    # Get monitor selection and title from request
    data = request.get_json() or {}
    monitor_id = data.get('monitor_id')
    
    # Use user's default monitor if no monitor specified
    if monitor_id is None and current_user.default_monitor:
        try:
            monitor_id = int(current_user.default_monitor)
        except (ValueError, TypeError):
            monitor_id = 0  # Fall back to primary monitor if conversion fails
    elif monitor_id is None:
        monitor_id = 0  # Fall back to primary monitor
    
    recording_title = data.get('title', f"Meeting {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Get monitor info
    monitors = get_monitors()
    selected_monitor = None
    for monitor in monitors:
        if monitor['id'] == monitor_id:
            selected_monitor = monitor
            break
    
    if not selected_monitor:
        return jsonify({'error': 'Invalid monitor selection'}), 400
    
    # Create database record for this recording
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
    
    # Store selected monitor and recording ID
    recording_state['selected_monitor'] = selected_monitor
    recording_state['recording_id'] = recording.id
    
    # Create upload callback function
    def upload_callback(file_path, success, message):
        """Called when upload completes or fails"""
        with app.app_context():
            if 'recording_id' in recording_state:
                rec = Recording.query.get(recording_state['recording_id'])
                if rec:
                    if success:
                        rec.uploaded = True
                        rec.upload_url = message if message.startswith('http') else None
                        print(f"📊 Database updated: Recording #{rec.id} marked as uploaded")
                    else:
                        print(f"📊 Upload failed for recording #{rec.id}: {message}")
                    db.session.commit()

    # Create streamer instance with monitor config
    recording_state['streamer'] = DualModeStreamer(
        monitor_config=selected_monitor
    )
    recording_state['streamer'].upload_callback = upload_callback  # Set the callback
    recording_state['active'] = True
    recording_state['transcriptions'] = []
    
    # Start recording in background thread
    def record_thread():
        success = recording_state['streamer'].dual_mode_record()
        recording_state['active'] = False
        
        # Update database record when recording completes
        if 'recording_id' in recording_state:
            with app.app_context():  # Ensure we have application context
                rec = Recording.query.get(recording_state['recording_id'])
                if rec:
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
                            
                            # Calculate duration from start/end times
                            if rec.started_at and rec.ended_at:
                                duration = (rec.ended_at - rec.started_at).total_seconds()
                                rec.duration = int(duration)
                            
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
                            except Exception:
                                pass  # Fall back to calculated duration
                    
                    db.session.commit()
    
    recording_state['thread'] = threading.Thread(target=record_thread, daemon=True)
    recording_state['thread'].start()
    
    return jsonify({
        'status': 'started',
        'monitor': selected_monitor['name'],
        'recording_id': recording.id
    })

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
    upload_status = {}
    if recording_state.get('streamer'):
        upload_status = recording_state['streamer'].upload_status
    
    return jsonify({
        'active': recording_state['active'],
        'transcription_count': len(recording_state['transcriptions']),
        'upload_active': upload_status.get('active', False),
        'upload_progress': upload_status.get('progress', 0),
        'upload_file': upload_status.get('file', None)
    })

@app.route('/transcriptions')
@login_required
def get_transcriptions():
    return jsonify({'transcriptions': recording_state['transcriptions'][-50:]})

# Monkey patch to capture transcriptions
original_send = DualModeStreamer.send_text_to_server
def patched_send(self, text):
    recording_state['transcriptions'].append({
        'text': text,
        'timestamp': time.strftime('%H:%M:%S')
    })
    return original_send(self, text)
DualModeStreamer.send_text_to_server = patched_send

@app.route('/video/<int:recording_id>')
@login_required
def serve_video(recording_id):
    """Serve video file for playback"""
    print(f"🎥 VIDEO REQUEST: User {current_user.username} requesting video ID {recording_id}")
    
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    print(f"🎥 FOUND RECORDING: '{recording.title}' - Stored Path: {recording.file_path}")
    
    # Use resolved file path that works across different machines
    resolved_path = recording.resolved_file_path
    print(f"🎥 RESOLVED PATH: {resolved_path}")
    
    if not resolved_path or not os.path.exists(resolved_path):
        print(f"❌ VIDEO FILE NOT FOUND: {resolved_path}")
        abort(404)
    
    # Get MIME type for the video file
    mime_type, _ = mimetypes.guess_type(resolved_path)
    if not mime_type:
        mime_type = 'video/mp4'  # Default fallback
    
    print(f"🎥 SERVING VIDEO: {resolved_path} (MIME: {mime_type})")
    return send_file(resolved_path, mimetype=mime_type)

@app.route('/thumbnail/<int:recording_id>')
@login_required
def serve_thumbnail(recording_id):
    """Serve thumbnail image for video preview"""
    print(f"🖼️ THUMBNAIL REQUEST: User {current_user.username} requesting thumbnail for recording ID {recording_id}")
    
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    print(f"🖼️ FOUND RECORDING: '{recording.title}' - Stored Path: {recording.file_path}")
    
    # Use resolved file path that works across different machines
    resolved_path = recording.resolved_file_path
    print(f"🖼️ RESOLVED PATH: {resolved_path}")
    
    if not resolved_path or not os.path.exists(resolved_path):
        print(f"❌ VIDEO FILE NOT FOUND: {resolved_path}")
        abort(404)
    
    # Generate thumbnail path based on resolved path
    base_name = os.path.splitext(resolved_path)[0]
    thumbnail_path = f"{base_name}_thumb.jpg"
    print(f"🖼️ THUMBNAIL PATH: {thumbnail_path}")
    
    # Generate thumbnail if it doesn't exist
    if not os.path.exists(thumbnail_path):
        print(f"🖼️ GENERATING THUMBNAIL: Creating thumbnail for {resolved_path}")
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
            print(f"✅ THUMBNAIL GENERATED: Successfully created {thumbnail_path}")
        except Exception as e:
            error_msg = f"Failed to generate thumbnail: {e}"
            print(f"❌ THUMBNAIL ERROR: {error_msg}")
            # Return a default placeholder or 404
            abort(404)
    else:
        print(f"✅ THUMBNAIL EXISTS: Using existing thumbnail {thumbnail_path}")
    
    print(f"🖼️ SERVING THUMBNAIL: {thumbnail_path}")
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
    print(f"🗑️ DELETE REQUEST: User {current_user.username} attempting to delete recording ID {recording_id}")
    
    recording = Recording.query.filter_by(id=recording_id, user_id=current_user.id).first_or_404()
    print(f"🗑️ FOUND RECORDING: '{recording.title}' - Stored Path: {recording.file_path}")
    
    # Get delete options from request
    data = request.get_json() or {}
    delete_file = data.get('delete_file', True)  # Default to deleting file
    print(f"🗑️ DELETE OPTIONS: delete_file={delete_file}, request_data={data}")
    
    deleted_items = []
    errors = []
    
    try:
        # Delete physical file if requested and exists
        resolved_path = recording.resolved_file_path
        print(f"🗑️ RESOLVED PATH: {resolved_path}")
        
        if delete_file and resolved_path and os.path.exists(resolved_path):
            print(f"🗑️ DELETING PHYSICAL FILE: {resolved_path}")
            try:
                os.remove(resolved_path)
                deleted_items.append('video_file')
                print(f"✅ VIDEO FILE DELETED: {resolved_path}")
                
                # Also delete thumbnail if it exists
                base_name = os.path.splitext(resolved_path)[0]
                thumbnail_path = f"{base_name}_thumb.jpg"
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
                    deleted_items.append('thumbnail')
                    print(f"✅ THUMBNAIL DELETED: {thumbnail_path}")
                    
            except Exception as e:
                error_msg = f"Failed to delete file: {str(e)}"
                errors.append(error_msg)
                print(f"❌ FILE DELETE ERROR: {error_msg}")
        elif delete_file and resolved_path:
            print(f"⚠️ FILE NOT FOUND: {resolved_path}")
        else:
            print(f"🗑️ SKIPPING FILE DELETE: delete_file={delete_file}, resolved_path={resolved_path}")
        
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
@login_required
def cleanup_orphaned_recordings():
    """Delete all recordings that have no corresponding file"""
    orphaned_recordings = Recording.query.filter_by(user_id=current_user.id).filter(
        (Recording.file_path == None) | (Recording.file_path == '')
    ).all()
    
    deleted_count = 0
    deleted_titles = []
    
    for recording in orphaned_recordings:
        deleted_titles.append(recording.title)
        db.session.delete(recording)
        deleted_count += 1
    
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Cleaned up {deleted_count} orphaned recording(s)',
            'deleted_count': deleted_count,
            'deleted_titles': deleted_titles
        })
    except Exception as e:
        db.session.rollback()
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

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Settings page for user preferences"""
    if request.method == 'POST':
        try:
            # Update user settings
            default_monitor = request.form.get('default_monitor', '')
            current_user.default_monitor = default_monitor if default_monitor else None
            
            # Handle auto delete days
            auto_delete_days = request.form.get('auto_delete_days', '30')
            try:
                auto_delete_days = int(auto_delete_days)
                if auto_delete_days < 0 or auto_delete_days > 365:
                    flash('Auto-delete days must be between 0 and 365.', 'error')
                    return redirect(url_for('settings'))
            except ValueError:
                flash('Invalid auto-delete days value.', 'error')
                return redirect(url_for('settings'))
            
            current_user.auto_delete_days = auto_delete_days
            db.session.commit()
            
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('settings'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to update settings: {str(e)}', 'error')
            return redirect(url_for('settings'))
    
    # Get available monitors for dropdown
    monitors = get_monitors()
    
    return render_template('settings.html', 
                         user=current_user, 
                         monitors=monitors)

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