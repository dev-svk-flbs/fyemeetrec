#!/usr/bin/env python3
"""
Professional File Upload Server
Receives video files and transcriptions from clients
"""

from flask import Flask, request, jsonify, render_template_string
import os
import time
from datetime import datetime
from pathlib import Path
import json

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.txt', '.json'}

# Create upload directories
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(f"{UPLOAD_FOLDER}/videos").mkdir(exist_ok=True)
Path(f"{UPLOAD_FOLDER}/transcriptions").mkdir(exist_ok=True)

# Store transcription log
transcription_log = []

@app.route('/')
def index():
    # Simple status page
    videos = list(Path(f"{UPLOAD_FOLDER}/videos").glob("*"))
    return render_template_string("""
    <h1>🎯 Upload Server Status</h1>
    <p><strong>Videos:</strong> {{ video_count }}</p>
    <p><strong>Transcriptions:</strong> {{ transcription_count }}</p>
    <p><strong>Last transcription:</strong> {{ last_transcription }}</p>
    <h3>Recent Videos</h3>
    <ul>
    {% for video in recent_videos %}
        <li>{{ video.name }} ({{ "%.1f"|format(video.stat().st_size/1024/1024) }} MB)</li>
    {% endfor %}
    </ul>
    """, 
    video_count=len(videos),
    transcription_count=len(transcription_log),
    last_transcription=transcription_log[-1]['text'][:50] + '...' if transcription_log else 'None',
    recent_videos=videos[-10:]
    )

@app.route('/transcription', methods=['POST'])
def receive_transcription():
    """Receive real-time transcription text"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        
        if text:
            transcription_entry = {
                'text': text,
                'timestamp': data.get('timestamp', time.time()),
                'source': data.get('source', 'unknown'),
                'received_at': datetime.now().isoformat()
            }
            
            transcription_log.append(transcription_entry)
            
            # Keep only last 1000 transcriptions in memory
            if len(transcription_log) > 1000:
                transcription_log.pop(0)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        print(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 400

@app.route('/upload', methods=['POST'])
def upload_file():
    """Receive video file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            return jsonify({'error': f'File type {file_ext} not allowed'}), 400
        
        # Generate safe filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"
        
        # Save video file
        if file_ext in {'.mkv', '.mp4', '.avi', '.mov'}:
            file_path = Path(f"{UPLOAD_FOLDER}/videos/{safe_filename}")
        else:
            file_path = Path(f"{UPLOAD_FOLDER}/transcriptions/{safe_filename}")
        
        # Save file
        file.save(str(file_path))
        file_size = file_path.stat().st_size
        
        print(f"✅ Uploaded: {safe_filename} ({file_size/1024/1024:.1f} MB)")
        
        # Save transcription log if it's a video
        if file_ext in {'.mkv', '.mp4', '.avi', '.mov'} and transcription_log:
            log_file = file_path.with_suffix('.json')
            with open(log_file, 'w') as f:
                json.dump({
                    'video_file': safe_filename,
                    'transcriptions': transcription_log.copy(),
                    'upload_time': datetime.now().isoformat()
                }, f, indent=2)
            print(f"💾 Saved transcription log: {log_file.name}")
        
        return jsonify({
            'status': 'success',
            'filename': safe_filename,
            'size': file_size,
            'path': str(file_path)
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def server_status():
    """API endpoint for server status"""
    videos = list(Path(f"{UPLOAD_FOLDER}/videos").glob("*"))
    total_size = sum(v.stat().st_size for v in videos)
    
    return jsonify({
        'video_count': len(videos),
        'transcription_count': len(transcription_log),
        'total_size_mb': round(total_size / 1024 / 1024, 1),
        'uptime': 'running'
    })

if __name__ == '__main__':
    print("🚀 Starting professional upload server...")
    print(f"📁 Upload folder: {Path(UPLOAD_FOLDER).absolute()}")
    print("🎯 Endpoints:")
    print("   POST /transcription - Receive live text")
    print("   POST /upload - Receive video files")
    print("   GET / - Status page")
    app.run(debug=False, host='0.0.0.0', port=8000, threaded=True)