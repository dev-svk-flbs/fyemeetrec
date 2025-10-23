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
import shutil

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
ALLOWED_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.txt', '.json'}

# Create upload directories
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)
Path(f"{UPLOAD_FOLDER}/videos").mkdir(exist_ok=True)
Path(f"{UPLOAD_FOLDER}/transcriptions").mkdir(exist_ok=True)
Path(f"{UPLOAD_FOLDER}/transcript_files").mkdir(exist_ok=True)

# Store transcription log
transcription_log = []

@app.route('/')
def index():
    # Enhanced status page
    videos = list(Path(f"{UPLOAD_FOLDER}/videos").glob("*"))
    transcript_files = list(Path(f"{UPLOAD_FOLDER}/transcript_files").glob("*.txt"))
    
    return render_template_string("""
    <h1>🎯 Upload Server Status</h1>
    <div style="display: flex; gap: 20px;">
        <div>
            <h3>📊 Statistics</h3>
            <p><strong>Videos:</strong> {{ video_count }}</p>
            <p><strong>Live Transcriptions:</strong> {{ transcription_count }}</p>
            <p><strong>Transcript Files:</strong> {{ transcript_file_count }}</p>
            <p><strong>Last transcription:</strong> {{ last_transcription }}</p>
        </div>
        <div>
            <h3>🎬 Recent Videos</h3>
            <ul>
            {% for video in recent_videos %}
                <li>{{ video.name }} ({{ "%.1f"|format(video.stat().st_size/1024/1024) }} MB)</li>
            {% endfor %}
            </ul>
        </div>
        <div>
            <h3>📝 Recent Transcript Files</h3>
            <ul>
            {% for transcript in recent_transcripts %}
                <li><a href="/download/transcript/{{ transcript.name }}">{{ transcript.name }}</a> ({{ "%.1f"|format(transcript.stat().st_size/1024) }} KB)</li>
            {% endfor %}
            </ul>
        </div>
    </div>
    """, 
    video_count=len(videos),
    transcription_count=len(transcription_log),
    transcript_file_count=len(transcript_files),
    last_transcription=transcription_log[-1]['text'][:50] + '...' if transcription_log else 'None',
    recent_videos=videos[-10:],
    recent_transcripts=transcript_files[-10:]
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
        original_name = Path(file.filename).stem
        safe_filename = f"{timestamp}_{original_name}{file_ext}"
        
        # Determine save location based on file type
        if file_ext in {'.mkv', '.mp4', '.avi', '.mov'}:
            file_path = Path(f"{UPLOAD_FOLDER}/videos/{safe_filename}")
            file_type = "video"
        elif file_ext == '.txt':
            file_path = Path(f"{UPLOAD_FOLDER}/transcript_files/{safe_filename}")
            file_type = "transcript"
        else:
            file_path = Path(f"{UPLOAD_FOLDER}/transcriptions/{safe_filename}")
            file_type = "transcription"
        
        # Save file
        file.save(str(file_path))
        file_size = file_path.stat().st_size
        
        print(f"✅ Uploaded {file_type}: {safe_filename} ({file_size/1024/1024:.1f} MB)")
        
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
            'original_name': file.filename,
            'type': file_type,
            'size': file_size,
            'path': str(file_path)
        })
        
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/upload-transcript', methods=['POST'])
def upload_transcript_file():
    """Dedicated endpoint for transcript file uploads"""
    try:
        if 'transcript' not in request.files:
            return jsonify({'error': 'No transcript file provided'}), 400
        
        file = request.files['transcript']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        
        # Get metadata
        recording_title = request.form.get('recording_title', 'Unknown Recording')
        recording_id = request.form.get('recording_id', 'unknown')
        
        # Generate safe filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in recording_title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_filename = f"{timestamp}_{safe_title}_transcript.txt"
        
        file_path = Path(f"{UPLOAD_FOLDER}/transcript_files/{safe_filename}")
        
        # Save transcript file
        file.save(str(file_path))
        file_size = file_path.stat().st_size
        
        # Save metadata
        metadata_file = file_path.with_suffix('.meta.json')
        with open(metadata_file, 'w') as f:
            json.dump({
                'recording_title': recording_title,
                'recording_id': recording_id,
                'original_filename': file.filename,
                'upload_time': datetime.now().isoformat(),
                'file_size': file_size
            }, f, indent=2)
        
        print(f"📝 Uploaded transcript: {safe_filename} for '{recording_title}' ({file_size/1024:.1f} KB)")
        
        return jsonify({
            'status': 'success',
            'filename': safe_filename,
            'recording_title': recording_title,
            'size': file_size,
            'path': str(file_path)
        })
        
    except Exception as e:
        print(f"Transcript upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/transcript/<filename>')
def download_transcript(filename):
    """Download transcript file"""
    try:
        file_path = Path(f"{UPLOAD_FOLDER}/transcript_files/{filename}")
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        from flask import send_file
        return send_file(str(file_path), as_attachment=True)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def server_status():
    """API endpoint for server status"""
    videos = list(Path(f"{UPLOAD_FOLDER}/videos").glob("*"))
    transcript_files = list(Path(f"{UPLOAD_FOLDER}/transcript_files").glob("*.txt"))
    total_size = sum(v.stat().st_size for v in videos)
    
    return jsonify({
        'video_count': len(videos),
        'transcription_count': len(transcription_log),
        'transcript_file_count': len(transcript_files),
        'total_size_mb': round(total_size / 1024 / 1024, 1),
        'uptime': 'running'
    })

@app.route('/api/recordings')
def list_recordings():
    """API endpoint to list all recordings with their transcripts"""
    videos = list(Path(f"{UPLOAD_FOLDER}/videos").glob("*"))
    transcripts = list(Path(f"{UPLOAD_FOLDER}/transcript_files").glob("*.txt"))
    
    recordings = []
    for video in videos:
        video_info = {
            'filename': video.name,
            'size_mb': round(video.stat().st_size / 1024 / 1024, 1),
            'upload_time': datetime.fromtimestamp(video.stat().st_mtime).isoformat(),
            'has_transcript': False,
            'transcript_file': None
        }
        
        # Look for matching transcript
        video_stem = video.stem
        for transcript in transcripts:
            if video_stem in transcript.name or transcript.name.startswith(video_stem):
                video_info['has_transcript'] = True
                video_info['transcript_file'] = transcript.name
                break
        
        recordings.append(video_info)
    
    return jsonify({
        'recordings': recordings,
        'total_videos': len(videos),
        'total_transcripts': len(transcripts)
    })

if __name__ == '__main__':
    print("🚀 Starting enhanced upload server...")
    print(f"📁 Upload folder: {Path(UPLOAD_FOLDER).absolute()}")
    print("🎯 Endpoints:")
    print("   POST /transcription - Receive live text")
    print("   POST /upload - Receive video/transcript files")
    print("   POST /upload-transcript - Dedicated transcript upload")
    print("   GET /download/transcript/<filename> - Download transcript")
    print("   GET /status - Server status")
    print("   GET /api/recordings - List all recordings")
    print("   GET / - Status page")
    app.run(debug=False, host='0.0.0.0', port=8000, threaded=True)