#!/usr/bin/env python3
"""
Background Upload Module for IDrive E2 Integration
"""

import threading
import time
import os
import json
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from logging_config import app_logger as logger

class BackgroundUploader:
    """Handles asynchronous uploading of recordings to IDrive E2"""
    
    def __init__(self, db_path=None):
        # IDrive E2 Configuration
        self.bucket_name = 'fyemeet'
        self.region = 'us-west-1'
        self.endpoint_url = f'https://s3.{self.region}.idrivee2.com'
        
        # Database path
        if db_path is None:
            current_dir = Path(__file__).parent.absolute()
            db_path = current_dir / 'instance' / 'recordings.db'
        self.db_path = str(db_path)
        
        # S3 client (will be initialized when needed)
        self.s3_client = None
        
        # Track active uploads
        self.active_uploads = {}
        self.upload_lock = threading.Lock()
    
    def _get_s3_client(self):
        """Initialize and return S3 client for IDrive E2"""
        if self.s3_client is None:
            try:
                # IDrive E2 credentials - matching upload_to_idrive.py
                access_key = "BtvRQTb87eNP5lLw3WDO"
                secret_key = "Esp3hhG5TuwhcOT76dr6m5ZUU5Strv1oLqwpRRgr"
                
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    region_name=self.region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
                # Test connection
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f"✅ IDrive E2 connection established to bucket: {self.bucket_name}")
            except NoCredentialsError:
                logger.error("❌ IDrive E2 credentials not found. Please configure AWS credentials.")
                raise
            except ClientError as e:
                logger.error(f"❌ IDrive E2 connection failed: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error connecting to IDrive E2: {e}")
                raise
        
        return self.s3_client
    
    def _get_db_connection(self):
        """Get database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            return conn
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise
    
    def _get_recording_info(self, recording_id):
        """Get recording information from database including user info"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get recording with user info
            cursor.execute("""
                SELECT r.*, u.username, u.email 
                FROM recording r
                JOIN user u ON r.user_id = u.id
                WHERE r.id = ?
            """, (recording_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return dict(result)
            else:
                logger.error(f"❌ Recording {recording_id} not found in database")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get recording info: {e}")
            return None
    
    def _find_recording_files(self, recording_info):
        """Find video, transcript, and thumbnail files for a recording"""
        files = {'video': None, 'transcript': None, 'thumbnail': None}
        
        try:
            current_dir = Path(__file__).parent.absolute()
            recordings_dir = current_dir / 'recordings'
            
            # Get video file path
            if recording_info.get('file_path'):
                if os.path.isabs(recording_info['file_path']):
                    # Old format: full path
                    video_path = recording_info['file_path']
                else:
                    # New format: just filename
                    video_path = recordings_dir / recording_info['file_path']
                
                if os.path.exists(video_path):
                    files['video'] = str(video_path)
                    logger.info(f"📹 Found video file: {video_path}")
                    
                    # Look for thumbnail (same name with _thumb.jpg)
                    base_name = os.path.splitext(video_path)[0]
                    thumbnail_path = f"{base_name}_thumb.jpg"
                    if os.path.exists(thumbnail_path):
                        files['thumbnail'] = thumbnail_path
                        logger.info(f"🖼️ Found thumbnail: {thumbnail_path}")
                else:
                    logger.warning(f"⚠️ Video file not found: {video_path}")
            
            # Look for transcript file
            safe_title = "".join(c for c in recording_info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            transcript_filename = f"{safe_title}_transcript.txt"
            transcript_path = recordings_dir / transcript_filename
            
            if os.path.exists(transcript_path):
                files['transcript'] = str(transcript_path)
                logger.info(f"📝 Found transcript: {transcript_path}")
            else:
                logger.warning(f"⚠️ Transcript not found: {transcript_path}")
            
            return files
            
        except Exception as e:
            logger.error(f"❌ Error finding recording files: {e}")
            return files
    
    def _get_video_duration(self, video_path):
        """Get actual video duration using ffprobe"""
        try:
            # Try local ffprobe first
            current_dir = Path(__file__).parent.absolute()
            local_ffprobe = current_dir / "ffmpeg" / "bin" / "ffprobe.exe"
            
            ffprobe_cmd = str(local_ffprobe) if local_ffprobe.exists() else "ffprobe"
            
            result = subprocess.run([
                ffprobe_cmd, '-v', 'quiet', '-show_entries', 
                'format=duration', '-of', 'csv=p=0', video_path
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                duration_str = result.stdout.strip()
                # Handle N/A or invalid duration
                if duration_str.lower() != 'n/a' and duration_str != '':
                    try:
                        return int(float(duration_str))
                    except ValueError:
                        logger.warning(f"⚠️ Invalid duration format: {duration_str}")
                        return None
            
            logger.warning(f"⚠️ ffprobe failed, using database duration")
            return None
                
        except Exception as e:
            logger.warning(f"⚠️ ffprobe error: {e}")
            return None
    
    def _generate_thumbnail_if_missing(self, video_path):
        """Generate thumbnail if it doesn't exist"""
        try:
            base_name = os.path.splitext(video_path)[0]
            thumbnail_path = f"{base_name}_thumb.jpg"
            
            if os.path.exists(thumbnail_path):
                return thumbnail_path
            
            logger.info(f"🖼️ Generating thumbnail for: {os.path.basename(video_path)}")
            
            # Try local ffmpeg first
            current_dir = Path(__file__).parent.absolute()
            local_ffmpeg = current_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
            ffmpeg_cmd = str(local_ffmpeg) if local_ffmpeg.exists() else "ffmpeg"
            
            subprocess.run([
                ffmpeg_cmd, '-i', video_path,
                '-ss', '00:00:05',  # Seek to 5 seconds
                '-vframes', '1',    # Extract 1 frame
                '-y',               # Overwrite output
                '-q:v', '2',        # High quality
                '-vf', 'scale=320:240',  # Scale to reasonable size
                thumbnail_path
            ], check=True, capture_output=True, timeout=30)
            
            if os.path.exists(thumbnail_path):
                logger.info(f"✅ Thumbnail generated: {thumbnail_path}")
                return thumbnail_path
            else:
                logger.warning(f"⚠️ Thumbnail generation failed")
                return None
                
        except Exception as e:
            logger.error(f"❌ Thumbnail generation error: {e}")
            return None
    
    def _upload_file_to_s3(self, file_path, s3_key, recording_id):
        """Upload a single file to IDrive E2 with progress tracking"""
        try:
            s3_client = self._get_s3_client()
            
            # Update upload status
            with self.upload_lock:
                if recording_id not in self.active_uploads:
                    self.active_uploads[recording_id] = {'files': {}, 'total_progress': 0}
                self.active_uploads[recording_id]['files'][s3_key] = {'status': 'uploading', 'progress': 0}
            
            # Upload with progress callback
            def upload_progress(bytes_transferred):
                file_size = os.path.getsize(file_path)
                progress = int((bytes_transferred / file_size) * 100)
                with self.upload_lock:
                    if recording_id in self.active_uploads:
                        self.active_uploads[recording_id]['files'][s3_key]['progress'] = progress
            
            # Perform upload
            logger.info(f"⬆️ Uploading {os.path.basename(file_path)} to {s3_key}")
            s3_client.upload_file(
                file_path, 
                self.bucket_name, 
                s3_key,
                Callback=upload_progress
            )
            
            # Generate public URL
            url = f"https://s3.{self.region}.idrivee2.com/{self.bucket_name}/{s3_key}"
            
            # Update status
            with self.upload_lock:
                if recording_id in self.active_uploads:
                    self.active_uploads[recording_id]['files'][s3_key] = {
                        'status': 'completed', 
                        'progress': 100,
                        'url': url
                    }
            
            logger.info(f"✅ Upload completed: {s3_key}")
            return url
            
        except Exception as e:
            logger.error(f"❌ Upload failed for {s3_key}: {e}")
            with self.upload_lock:
                if recording_id in self.active_uploads:
                    self.active_uploads[recording_id]['files'][s3_key] = {
                        'status': 'failed', 
                        'progress': 0,
                        'error': str(e)
                    }
            raise
    
    def _update_database_with_urls(self, recording_id, urls, metadata):
        """Update database with upload URLs and metadata"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Update recording with upload info
            cursor.execute("""
                UPDATE recording 
                SET video_url = ?, transcript_url = ?, thumbnail_url = ?, 
                    uploaded = 1, upload_status = 'completed',
                    upload_metadata = ?
                WHERE id = ?
            """, (
                urls.get('video'),
                urls.get('transcript'), 
                urls.get('thumbnail'),
                json.dumps(metadata),
                recording_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Database updated with upload URLs for recording {recording_id}")
            
        except Exception as e:
            logger.error(f"❌ Database update failed: {e}")
            raise
    
    def upload_recording_async(self, recording_id):
        """Start asynchronous upload of a recording"""
        def upload_worker():
            try:
                logger.info(f"🚀 Starting background upload for recording {recording_id}")
                
                # Mark upload as starting
                with self.upload_lock:
                    self.active_uploads[recording_id] = {
                        'status': 'starting',
                        'files': {},
                        'start_time': datetime.now().isoformat()
                    }
                
                # Update database status
                try:
                    conn = self._get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE recording SET upload_status = 'uploading' WHERE id = ?", (recording_id,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.warning(f"⚠️ Failed to update upload status: {e}")
                
                # Get recording info
                recording_info = self._get_recording_info(recording_id)
                if not recording_info:
                    raise Exception("Recording not found in database")
                
                # Find files to upload
                files = self._find_recording_files(recording_info)
                
                # Generate thumbnail if missing and video exists
                if files['video'] and not files['thumbnail']:
                    thumbnail_path = self._generate_thumbnail_if_missing(files['video'])
                    if thumbnail_path:
                        files['thumbnail'] = thumbnail_path
                
                # Upload files
                urls = {}
                folder_prefix = f"{recording_id}/"
                
                if files['video']:
                    urls['video'] = self._upload_file_to_s3(
                        files['video'], 
                        f"{folder_prefix}video.mkv", 
                        recording_id
                    )
                
                if files['transcript']:
                    urls['transcript'] = self._upload_file_to_s3(
                        files['transcript'], 
                        f"{folder_prefix}transcript.txt", 
                        recording_id
                    )
                
                if files['thumbnail']:
                    urls['thumbnail'] = self._upload_file_to_s3(
                        files['thumbnail'], 
                        f"{folder_prefix}thumbnail.jpg", 
                        recording_id
                    )
                
                # Create comprehensive metadata
                metadata = self._create_upload_metadata(recording_info, files, urls)
                
                # Upload metadata.json
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(metadata, f, indent=2)
                    metadata_path = f.name
                
                urls['metadata'] = self._upload_file_to_s3(
                    metadata_path, 
                    f"{folder_prefix}metadata.json", 
                    recording_id
                )
                
                # Clean up temp metadata file
                try:
                    os.remove(metadata_path)
                except:
                    pass
                
                # Update database with URLs
                self._update_database_with_urls(recording_id, urls, metadata)
                
                # Mark upload as completed
                with self.upload_lock:
                    if recording_id in self.active_uploads:
                        self.active_uploads[recording_id]['status'] = 'completed'
                        self.active_uploads[recording_id]['completion_time'] = datetime.now().isoformat()
                        self.active_uploads[recording_id]['urls'] = urls
                
                logger.info(f"✅ Background upload completed successfully for recording {recording_id}")
                logger.info(f"📊 Upload summary: {len(urls)} files uploaded")
                for file_type, url in urls.items():
                    logger.info(f"   {file_type}: {url}")
                
            except Exception as e:
                logger.error(f"❌ Background upload failed for recording {recording_id}: {e}")
                
                # Mark upload as failed
                with self.upload_lock:
                    if recording_id in self.active_uploads:
                        self.active_uploads[recording_id]['status'] = 'failed'
                        self.active_uploads[recording_id]['error'] = str(e)
                        self.active_uploads[recording_id]['failure_time'] = datetime.now().isoformat()
                
                # Update database status
                try:
                    conn = self._get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE recording SET upload_status = 'failed' WHERE id = ?", (recording_id,))
                    conn.commit()
                    conn.close()
                except Exception as db_error:
                    logger.error(f"❌ Failed to update database with failure status: {db_error}")
        
        # Start upload in background thread
        upload_thread = threading.Thread(target=upload_worker, daemon=True)
        upload_thread.name = f"UploadWorker-{recording_id}"
        upload_thread.start()
        
        logger.info(f"🎬 Background upload thread started for recording {recording_id}")
        return True
    
    def _create_upload_metadata(self, recording_info, files, urls):
        """Create comprehensive metadata for the upload"""
        try:
            # Get file sizes
            file_sizes = {}
            total_size = 0
            
            if files['video'] and os.path.exists(files['video']):
                size = os.path.getsize(files['video'])
                file_sizes['video.mkv'] = round(size / (1024 * 1024), 2)  # MB
                total_size += size
            
            if files['transcript'] and os.path.exists(files['transcript']):
                size = os.path.getsize(files['transcript'])
                file_sizes['transcript.txt'] = round(size / (1024 * 1024), 2)  # MB
                total_size += size
            
            if files['thumbnail'] and os.path.exists(files['thumbnail']):
                size = os.path.getsize(files['thumbnail'])
                file_sizes['thumbnail.jpg'] = round(size / (1024 * 1024), 2)  # MB
                total_size += size
            
            # Get actual video duration
            actual_duration = recording_info.get('duration', 0)
            if files['video']:
                ffprobe_duration = self._get_video_duration(files['video'])
                if ffprobe_duration:
                    actual_duration = ffprobe_duration
            
            metadata = {
                'recording_id': recording_info['id'],
                'title': recording_info['title'],
                'created_at': recording_info['created_at'],
                'duration_seconds': actual_duration,
                'duration_database': recording_info.get('duration', 0),
                'user_info': {
                    'username': recording_info['username'],
                    'email': recording_info['email']
                },
                'file_info': {
                    'total_size_mb': round(total_size / (1024 * 1024), 2),
                    'individual_sizes_mb': file_sizes
                },
                'uploaded_files': urls,
                'upload_timestamp': datetime.now().isoformat(),
                'upload_source': 'background_thread',
                'bucket_name': self.bucket_name,
                'region': self.region
            }
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Metadata creation failed: {e}")
            return {
                'recording_id': recording_info['id'],
                'title': recording_info['title'],
                'error': 'Failed to generate complete metadata',
                'upload_timestamp': datetime.now().isoformat()
            }
    
    def get_upload_status(self, recording_id):
        """Get current upload status for a recording"""
        with self.upload_lock:
            return self.active_uploads.get(recording_id, {'status': 'not_found'})
    
    def get_all_active_uploads(self):
        """Get status of all active uploads"""
        with self.upload_lock:
            return dict(self.active_uploads)

# Global instance
_uploader_instance = None

def get_uploader():
    """Get global uploader instance (singleton pattern)"""
    global _uploader_instance
    if _uploader_instance is None:
        _uploader_instance = BackgroundUploader()
    return _uploader_instance

def trigger_upload(recording_id):
    """Convenience function to trigger upload for a recording"""
    try:
        uploader = get_uploader()
        return uploader.upload_recording_async(recording_id)
    except Exception as e:
        logger.error(f"❌ Failed to trigger upload for recording {recording_id}: {e}")
        return False