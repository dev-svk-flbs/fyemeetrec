#!/usr/bin/env python3
"""
Minimal script to upload latest recording to IDrive E2
"""
import os
import sqlite3
import boto3
from pathlib import Path
import glob
import subprocess
import json

# IDrive E2 Configuration
ENDPOINT_URL = "https://s3.us-west-1.idrivee2.com"
BUCKET_NAME = "fyemeet"
ACCESS_KEY = "BtvRQTb87eNP5lLw3WDO"
SECRET_KEY = "Esp3hhG5TuwhcOT76dr6m5ZUU5Strv1oLqwpRRgr"

def get_latest_recording():
    """Get the most recent completed recording from database with user info"""
    conn = sqlite3.connect('instance/recordings.db')
    cursor = conn.cursor()
    
    # Get latest recording with user information
    cursor.execute("""
        SELECT r.id, r.title, r.file_path, r.created_at, r.duration, 
               u.username, u.email, r.file_size
        FROM recording r
        JOIN user u ON r.user_id = u.id
        WHERE r.file_path IS NOT NULL 
        ORDER BY r.created_at DESC 
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'id': result[0],
            'title': result[1], 
            'file_path': result[2],
            'created_at': result[3],
            'duration': result[4],
            'username': result[5],
            'email': result[6],
            'file_size': result[7]
        }
    return None

def find_recording_files(recording):
    """Find video, transcript and thumbnail files for the recording"""
    recordings_dir = "recordings"
    
    # Look for video file in recordings folder
    video_patterns = [
        os.path.join(recordings_dir, "*.mkv"),
        os.path.join(recordings_dir, "*.mp4")
    ]
    
    video_file = None
    for pattern in video_patterns:
        matches = glob.glob(pattern)
        if matches:
            video_file = matches[-1]  # Get most recent
            break
    
    # Look for transcript file 
    transcript_patterns = [
        os.path.join(recordings_dir, "*_transcript.txt"),
        os.path.join(recordings_dir, f"{recording['title']}_transcript.txt")
    ]
    
    transcript_file = None
    for pattern in transcript_patterns:
        matches = glob.glob(pattern)
        if matches:
            transcript_file = matches[-1]  # Get most recent
            break
    
    # Look for thumbnail file
    thumbnail_file = None
    if video_file:
        base_name = os.path.splitext(video_file)[0]
        thumbnail_file = f"{base_name}_thumb.jpg"
        if not os.path.exists(thumbnail_file):
            thumbnail_file = None
    
    return video_file, transcript_file, thumbnail_file

def get_video_duration(video_path):
    """Get actual video duration using ffmpeg"""
    try:
        cmd = [
            'ffmpeg/bin/ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        return int(duration)
        
    except (subprocess.CalledProcessError, KeyError, ValueError, json.JSONDecodeError):
        # Fallback to database duration or file size estimation
        return None

def get_file_size_mb(file_path):
    """Get file size in MB"""
    try:
        size_bytes = os.path.getsize(file_path)
        return round(size_bytes / (1024 * 1024), 2)
    except:
        return None

def upload_to_idrive():
    """Upload latest recording files to IDrive E2"""
    
    # Initialize S3 client for IDrive E2
    s3 = boto3.client(
        's3',
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name='us-west-1'
    )
    
    # Get latest recording
    recording = get_latest_recording()
    if not recording:
        print("❌ No completed recordings found in database")
        return
    
    print(f"📹 Found recording: {recording['title']} (ID: {recording['id']})")
    
    # Find actual files in recordings folder
    video_path, transcript_path, thumbnail_path = find_recording_files(recording)
    
    files_to_upload = []
    
    # Video file
    if video_path and os.path.exists(video_path):
        # Keep original extension (.mkv or .mp4)
        video_filename = f"video{os.path.splitext(video_path)[1]}"
        files_to_upload.append((video_filename, video_path))
        print(f"✅ Video found: {video_path}")
    else:
        print(f"❌ Video not found in recordings folder")
    
    # Transcript file  
    if transcript_path and os.path.exists(transcript_path):
        files_to_upload.append(('transcript.txt', transcript_path))
        print(f"✅ Transcript found: {transcript_path}")
    else:
        print(f"⚠️ No transcript found in recordings folder")
    
    # Thumbnail file
    if thumbnail_path and os.path.exists(thumbnail_path):
        files_to_upload.append(('thumbnail.jpg', thumbnail_path))  
        print(f"✅ Thumbnail found: {thumbnail_path}")
    else:
        print(f"⚠️ No thumbnail found in recordings folder")
    
    if not files_to_upload:
        print("❌ No files to upload!")
        return
    
    # Upload files
    recording_id = recording['id']
    folder_path = f"recordings/{recording_id}/"
    
    uploaded_urls = {}
    
    for filename, local_path in files_to_upload:
        s3_key = f"{folder_path}{filename}"
        
        try:
            print(f"⬆️ Uploading {filename}...")
            
            s3.upload_file(
                local_path, 
                BUCKET_NAME, 
                s3_key,
                ExtraArgs={'ACL': 'private'}  # Keep files private
            )
            
            # Generate URL
            url = f"{ENDPOINT_URL}/{s3_key}"
            uploaded_urls[filename] = url
            
            print(f"✅ Uploaded: {url}")
            
        except Exception as e:
            print(f"❌ Failed to upload {filename}: {e}")
    
    # Get actual video duration and file sizes
    actual_duration = None
    file_sizes = {}
    
    if video_path:
        actual_duration = get_video_duration(video_path)
        
    for filename, local_path in files_to_upload:
        file_sizes[filename] = get_file_size_mb(local_path)
    
    # Save comprehensive metadata file
    try:
        metadata = {
            'recording_id': recording['id'],
            'title': recording['title'],
            'created_at': recording['created_at'],
            'duration_seconds': actual_duration or recording['duration'],
            'duration_database': recording['duration'],  # Keep original for comparison
            'user_info': {
                'username': recording['username'],
                'email': recording['email']
            },
            'file_info': {
                'total_size_mb': sum(file_sizes.values()) if file_sizes else None,
                'individual_sizes_mb': file_sizes
            },
            'uploaded_files': uploaded_urls,
            'upload_timestamp': __import__('datetime').datetime.now().isoformat(),
            'upload_source': 'manual_script',
            'bucket_name': BUCKET_NAME,
            'region': 'us-west-1'
        }
        
        import json
        metadata_json = json.dumps(metadata, indent=2)
        
        # Upload metadata
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{folder_path}metadata.json",
            Body=metadata_json,
            ContentType='application/json'
        )
        
        print(f"✅ Metadata saved to: {folder_path}metadata.json")
        
    except Exception as e:
        print(f"❌ Failed to save metadata: {e}")
    
    print(f"\n🎉 Upload completed! Files available at:")
    for filename, url in uploaded_urls.items():
        print(f"   {filename}: {url}")

if __name__ == "__main__":
    print("🚀 IDrive E2 Upload Script")
    print(f"📦 Bucket: {BUCKET_NAME}")
    print("=" * 50)
    
    # Check if credentials are set
    if ACCESS_KEY == "your_access_key_here" or SECRET_KEY == "your_secret_key_here":
        print("❌ Please set your IDrive E2 access credentials first!")
        print("   Get them from: https://www.idrive.com/e2/")
        print("   Update ACCESS_KEY and SECRET_KEY in this script")
        exit(1)
    
    upload_to_idrive()