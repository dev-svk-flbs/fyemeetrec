#!/usr/bin/env python3
"""
Flask Web Interface for Dual Stream Recording with Authentication
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'  # Change this!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///recordings.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
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
    return render_template('record.html')

@app.route('/monitors')
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
    monitor_id = data.get('monitor_id', 0)  # Default to primary monitor
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
    
    # Create streamer instance with monitor config
    recording_state['streamer'] = DualModeStreamer(
        monitor_config=selected_monitor
    )
    recording_state['active'] = True
    recording_state['transcriptions'] = []
    
    # Start recording in background thread
    def record_thread():
        success = recording_state['streamer'].dual_mode_record()
        recording_state['active'] = False
        
        # Update database record when recording completes
        if 'recording_id' in recording_state:
            rec = Recording.query.get(recording_state['recording_id'])
            if rec:
                rec.ended_at = datetime.utcnow()
                rec.status = 'completed' if success else 'failed'
                
                # Try to get file info if recording succeeded
                if success and hasattr(recording_state['streamer'], 'last_output_file'):
                    file_path = recording_state['streamer'].last_output_file
                    if os.path.exists(file_path):
                        rec.file_path = file_path
                        rec.filename = os.path.basename(file_path)
                        rec.file_size = os.path.getsize(file_path)
                        
                        # Calculate duration from start/end times
                        if rec.started_at and rec.ended_at:
                            duration = (rec.ended_at - rec.started_at).total_seconds()
                            rec.duration = int(duration)
                
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)