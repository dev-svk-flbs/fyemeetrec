#!/usr/bin/env python3
"""
Background Upload Module for IDrive E2 Integration
"""

import threading
import time
import os
import sys
import json
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import requests
from logging_config import app_logger as logger

class BackgroundUploader:
    """Handles asynchronous uploading of recordings to IDrive E2"""
    
    def __init__(self, db_path=None):
        # IDrive E2 Configuration
        self.bucket_name = 'fyemeet'
        self.region = 'us-west-1'
        self.endpoint_url = f'https://s3.{self.region}.idrivee2.com'
        
        # Django Webhook Configuration
        self.webhook_url = 'https://ops.fyelabs.com/recordings/webhook/'
        self.webhook_token = 'fye_webhook_secure_token_2025_recordings'
        
        # Database path - handle PyInstaller frozen executable
        if db_path is None:
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller bundle
                base_dir = Path(sys.executable).parent
            else:
                # Running as normal Python script
                base_dir = Path(__file__).parent.absolute()
            
            instance_dir = base_dir / 'instance'
            instance_dir.mkdir(exist_ok=True)
            db_path = instance_dir / 'recordings.db'
        
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
                access_key = "9oP9oM38k9d5wMTm1zuT"
                secret_key = "xVVpTAdLKZj3SpCW9AEzJ0ovgv0n3ts3rzVIZAJv"
                
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=self.endpoint_url,
                    region_name=self.region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
                # Test connection
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.info(f" IDrive E2 connection established to bucket: {self.bucket_name}")
            except NoCredentialsError:
                logger.error(" IDrive E2 credentials not found. Please configure AWS credentials.")
                raise
            except ClientError as e:
                logger.error(f" IDrive E2 connection failed: {e}")
                raise
            except Exception as e:
                logger.error(f" Unexpected error connecting to IDrive E2: {e}")
                raise
        
        return self.s3_client
    
    def _get_db_connection(self):
        """Get database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            return conn
        except Exception as e:
            logger.error(f" Database connection failed: {e}")
            raise
    
    def _get_recording_info(self, recording_id):
        """Get recording information from database including user info and meeting details"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get recording with user info and meeting details (if linked)
            cursor.execute("""
                SELECT r.*, u.username, u.email,
                       m.id as meeting_id, m.subject as meeting_subject, 
                       m.start_time as meeting_start_time, m.end_time as meeting_end_time,
                       m.duration_minutes as meeting_duration_minutes, m.organizer as meeting_organizer,
                       m.required_attendees, m.optional_attendees, m.attendee_count,
                       m.location as meeting_location, m.web_link as meeting_web_link,
                       m.meeting_type, m.is_teams_meeting, m.is_recurring,
                       m.discovered_at as meeting_discovered_at, m.calendar_event_id as meeting_calendar_id
                FROM recording r
                JOIN user u ON r.user_id = u.id
                LEFT JOIN meeting m ON m.recording_id = r.id
                WHERE r.id = ?
            """, (recording_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return dict(result)
            else:
                logger.error(f" Recording {recording_id} not found in database")
                return None
                
        except Exception as e:
            logger.error(f" Failed to get recording info: {e}")
            return None
    
    def _find_recording_files(self, recording_info):
        """Find video, transcript, and thumbnail files for a recording"""
        files = {'video': None, 'transcript': None, 'thumbnail': None}
        
        try:
            # Get base directory (works with PyInstaller)
            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent.absolute()
            recordings_dir = base_dir / 'recordings'
            
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
                    logger.info(f" Found video file: {video_path}")
                    
                    # Look for thumbnail (same name with _thumb.jpg)
                    base_name = os.path.splitext(video_path)[0]
                    thumbnail_path = f"{base_name}_thumb.jpg"
                    if os.path.exists(thumbnail_path):
                        files['thumbnail'] = thumbnail_path
                        logger.info(f" Found thumbnail: {thumbnail_path}")
                else:
                    logger.warning(f" Video file not found: {video_path}")
            
            # Look for transcript file
            safe_title = "".join(c for c in recording_info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
            transcript_filename = f"{safe_title}_transcript.txt"
            transcript_path = recordings_dir / transcript_filename
            
            if os.path.exists(transcript_path):
                files['transcript'] = str(transcript_path)
                logger.info(f" Found transcript: {transcript_path}")
            else:
                logger.warning(f" Transcript not found: {transcript_path}")
            
            return files
            
        except Exception as e:
            logger.error(f" Error finding recording files: {e}")
            return files
    
    def _get_video_duration(self, video_path):
        """Get actual video duration using ffprobe"""
        try:
            # Get base directory (works with PyInstaller)
            if getattr(sys, 'frozen', False):
                # PyInstaller: ffmpeg is in _internal/ffmpeg/
                base_dir = Path(sys._MEIPASS)
            else:
                # Normal Python: ffmpeg is in same dir as script
                base_dir = Path(__file__).parent.absolute()
            local_ffprobe = base_dir / "ffmpeg" / "bin" / "ffprobe.exe"
            
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
                        logger.warning(f" Invalid duration format: {duration_str}")
                        return None
            
            logger.warning(f" ffprobe failed, using database duration")
            return None
                
        except Exception as e:
            logger.warning(f" ffprobe error: {e}")
            return None
    
    def _generate_thumbnail_if_missing(self, video_path):
        """Generate thumbnail if it doesn't exist"""
        try:
            base_name = os.path.splitext(video_path)[0]
            thumbnail_path = f"{base_name}_thumb.jpg"
            
            if os.path.exists(thumbnail_path):
                return thumbnail_path
            
            logger.info(f" Generating thumbnail for: {os.path.basename(video_path)}")
            
            # Get ffmpeg path (works with PyInstaller)
            if getattr(sys, 'frozen', False):
                # PyInstaller: ffmpeg is in _internal/ffmpeg/
                base_dir = Path(sys._MEIPASS)
            else:
                # Normal Python: ffmpeg is in same dir as script
                base_dir = Path(__file__).parent.absolute()
            local_ffmpeg = base_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
            ffmpeg_cmd = str(local_ffmpeg) if local_ffmpeg.exists() else "ffmpeg"
            
            subprocess.run([
                ffmpeg_cmd, '-i', video_path,
                '-ss', '00:00:05',  # Seek to 5 seconds
                '-vframes', '1',    # Extract 1 frame
                '-y',               # Overwrite output
                '-q:v', '2',        # High quality
                '-vf', 'scale=320:180',  # Scale to 16:9 aspect ratio (320x180)
                thumbnail_path
            ], check=True, capture_output=True, timeout=30)
            
            if os.path.exists(thumbnail_path):
                logger.info(f" Thumbnail generated: {thumbnail_path}")
                return thumbnail_path
            else:
                logger.warning(f" Thumbnail generation failed")
                return None
                
        except Exception as e:
            logger.error(f" Thumbnail generation error: {e}")
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
            logger.info(f" Uploading {os.path.basename(file_path)} to {s3_key}")
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
            
            logger.info(f" Upload completed: {s3_key}")
            return url
            
        except Exception as e:
            logger.error(f" Upload failed for {s3_key}: {e}")
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
            
            # Update associated meeting status if it exists
            # Use current UTC timestamp in a format compatible with SQLAlchemy
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
            cursor.execute("""
                UPDATE meeting 
                SET recording_status = 'recorded_synced', last_updated = ?
                WHERE recording_id = ?
            """, (current_time, recording_id))
            
            # Check if any meeting was updated
            updated_rows = cursor.rowcount
            if updated_rows > 0:
                logger.info(f" Updated meeting status to 'recorded_synced' for recording {recording_id}")
            else:
                logger.info(f"ℹ No meeting found linked to recording {recording_id}")
            
            conn.commit()
            conn.close()
            
            logger.info(f" Database updated with upload URLs for recording {recording_id}")
            
        except Exception as e:
            logger.error(f" Database update failed: {e}")
            raise
    
    def upload_recording_async(self, recording_id):
        """Start asynchronous upload of a recording"""
        def upload_worker():
            try:
                logger.info(f" Starting background upload for recording {recording_id}")
                
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
                    logger.warning(f" Failed to update upload status: {e}")
                
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
                
                # Upload files with better error handling
                urls = {}
                folder_prefix = f"{recording_id}/"
                upload_errors = []
                
                # Upload video file
                if files['video']:
                    try:
                        urls['video'] = self._upload_file_to_s3(
                            files['video'], 
                            f"{folder_prefix}video.mkv", 
                            recording_id
                        )
                        logger.info(f" Video upload completed for recording {recording_id}")
                    except Exception as e:
                        error_msg = f"Video upload failed: {e}"
                        upload_errors.append(error_msg)
                        logger.error(f" {error_msg}")
                
                # Upload transcript file
                if files['transcript']:
                    try:
                        urls['transcript'] = self._upload_file_to_s3(
                            files['transcript'], 
                            f"{folder_prefix}transcript.txt", 
                            recording_id
                        )
                        logger.info(f" Transcript upload completed for recording {recording_id}")
                    except Exception as e:
                        error_msg = f"Transcript upload failed: {e}"
                        upload_errors.append(error_msg)
                        logger.error(f" {error_msg}")
                
                # Upload thumbnail file
                if files['thumbnail']:
                    try:
                        urls['thumbnail'] = self._upload_file_to_s3(
                            files['thumbnail'], 
                            f"{folder_prefix}thumbnail.jpg", 
                            recording_id
                        )
                        logger.info(f" Thumbnail upload completed for recording {recording_id}")
                    except Exception as e:
                        error_msg = f"Thumbnail upload failed: {e}"
                        upload_errors.append(error_msg)
                        logger.error(f" {error_msg}")
                
                # Check if we have any successful uploads
                if not urls:
                    raise Exception(f"All uploads failed: {'; '.join(upload_errors)}")
                
                # Create comprehensive metadata
                logger.info("=" * 60)
                logger.info(" CREATING UPLOAD METADATA")
                logger.info("=" * 60)
                metadata = self._create_upload_metadata(recording_info, files, urls)
                
                # Log metadata summary
                logger.info(f" Metadata Summary:")
                logger.info(f"   Recording ID: {metadata.get('recording_id')}")
                logger.info(f"   Title: {metadata.get('title')}")
                logger.info(f"   Duration: {metadata.get('duration_seconds')} seconds")
                logger.info(f"   User: {metadata.get('user_info', {}).get('email', 'N/A')}")
                logger.info(f"   Total Size: {metadata.get('file_info', {}).get('total_size_mb', 0)} MB")
                logger.info(f"   Meeting Linked: {metadata.get('meeting_info', {}).get('is_linked_to_meeting', False)}")
                if metadata.get('meeting_info', {}).get('is_linked_to_meeting'):
                    meeting_info = metadata['meeting_info']
                    logger.info(f"   Meeting Subject: {meeting_info.get('subject', 'N/A')}")
                    logger.info(f"   Meeting Type: {meeting_info.get('meeting_type', 'N/A')}")
                    logger.info(f"   Attendees: {meeting_info.get('attendee_count', 0)}")
                logger.info("=" * 60)
                
                # Upload metadata.json (optional - don't fail if this fails)
                try:
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
                        
                    logger.info(f" Metadata upload completed for recording {recording_id}")
                        
                except Exception as e:
                    logger.warning(f" Metadata upload failed (non-critical): {e}")
                    # Don't add to upload_errors since metadata is optional
                
                # Update database with URLs
                self._update_database_with_urls(recording_id, urls, metadata)
                
                # Send webhook to Django server (non-blocking, won't fail upload if webhook fails)
                try:
                    logger.info("=" * 80)
                    logger.info(" PREPARING WEBHOOK TO ops.fyelabs.com")
                    logger.info("=" * 80)
                    logger.info(f" Recording ID: {recording_id}")
                    logger.info(f" Recording Title: {recording_info.get('title', 'N/A')}")
                    logger.info(f" User: {recording_info.get('username', 'N/A')} ({recording_info.get('email', 'N/A')})")
                    logger.info(f" Meeting Linked: {'Yes' if recording_info.get('meeting_id') else 'No'}")
                    if recording_info.get('meeting_id'):
                        logger.info(f" Meeting: {recording_info.get('meeting_subject', 'N/A')}")
                    logger.info(f" Files to Send: {len(urls)} URLs")
                    logger.info(f" Total Size: {metadata.get('file_info', {}).get('total_size_mb', 0)} MB")
                    
                    webhook_sent = self._send_webhook_to_django(metadata)
                    if webhook_sent:
                        logger.info("=" * 80)
                        logger.info(f" WEBHOOK DELIVERY COMPLETE - Recording {recording_id}")
                        logger.info(" ops.fyelabs.com has been notified of the upload")
                        logger.info("=" * 80)
                    else:
                        logger.warning("=" * 80)
                        logger.warning(f" WEBHOOK DELIVERY FAILED - Recording {recording_id}")
                        logger.warning(" ops.fyelabs.com was NOT notified (upload still succeeded)")
                        logger.warning("=" * 80)
                except Exception as webhook_error:
                    logger.error("=" * 80)
                    logger.error(f" WEBHOOK ERROR - Recording {recording_id}")
                    logger.error(f" Exception: {webhook_error}")
                    logger.error(" Upload succeeded but webhook failed")
                    logger.error("=" * 80)
                    # Don't fail the upload if webhook fails
                
                # Determine final status
                if upload_errors:
                    final_status = 'partially_completed'
                    logger.warning(f" Partial upload for recording {recording_id}: {len(urls)} succeeded, {len(upload_errors)} failed")
                else:
                    final_status = 'completed'
                    logger.info(f" Complete upload for recording {recording_id}: all files uploaded successfully")
                
                # Mark upload as completed
                with self.upload_lock:
                    if recording_id in self.active_uploads:
                        self.active_uploads[recording_id]['status'] = final_status
                        self.active_uploads[recording_id]['completion_time'] = datetime.now().isoformat()
                        self.active_uploads[recording_id]['urls'] = urls
                        self.active_uploads[recording_id]['errors'] = upload_errors
                
                logger.info(f" Upload summary for recording {recording_id}: {len(urls)} files uploaded")
                for file_type, url in urls.items():
                    logger.info(f"   {file_type}: {url}")
                
                if upload_errors:
                    for error in upload_errors:
                        logger.warning(f"   Error: {error}")
                
            except Exception as e:
                logger.error(f" Background upload failed for recording {recording_id}: {e}")
                
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
                    
                    # Also update associated meeting status if it exists
                    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
                    cursor.execute("""
                        UPDATE meeting 
                        SET recording_status = 'upload_failed', last_updated = ?
                        WHERE recording_id = ?
                    """, (current_time, recording_id))
                    
                    # Check if any meeting was updated
                    updated_rows = cursor.rowcount
                    if updated_rows > 0:
                        logger.info(f" Updated meeting status to 'upload_failed' for recording {recording_id}")
                    
                    conn.commit()
                    conn.close()
                except Exception as db_error:
                    logger.error(f" Failed to update database with failure status: {db_error}")
            
            finally:
                # Clean up active uploads tracking after some time
                def cleanup_tracking():
                    time.sleep(300)  # Wait 5 minutes
                    with self.upload_lock:
                        if recording_id in self.active_uploads:
                            status = self.active_uploads[recording_id].get('status')
                            if status in ['completed', 'failed', 'partially_completed']:
                                del self.active_uploads[recording_id]
                                logger.debug(f" Cleaned up tracking for recording {recording_id}")
                
                cleanup_thread = threading.Thread(target=cleanup_tracking, daemon=True)
                cleanup_thread.start()
        
        # Start upload in background thread
        upload_thread = threading.Thread(target=upload_worker, daemon=True)
        upload_thread.name = f"UploadWorker-{recording_id}"
        upload_thread.start()
        
        logger.info(f" Background upload thread started for recording {recording_id}")
        return True
    
    def _send_webhook_to_django(self, metadata):
        """Send recording metadata to Django webhook"""
        try:
            recording_id = metadata.get('recording_id', 'unknown')
            logger.info(f" Sending webhook to {self.webhook_url} for recording {recording_id}")
            
            # Log the complete JSON payload being sent
            logger.info("=" * 80)
            logger.info(" WEBHOOK PAYLOAD TO ops.fyelabs.com")
            logger.info("=" * 80)
            logger.info(f" URL: {self.webhook_url}")
            logger.info(f" Auth Token: {self.webhook_token[:20]}...")
            logger.info(f" Recording ID: {recording_id}")
            
            # Pretty print the JSON payload
            import json
            payload_json = json.dumps(metadata, indent=2, default=str)
            logger.info(" JSON Payload:")
            logger.info("-" * 40)
            for line_num, line in enumerate(payload_json.split('\n'), 1):
                logger.info(f"{line_num:3d}: {line}")
            logger.info("-" * 40)
            
            # Log meeting info summary
            if metadata.get('meeting_info', {}).get('is_linked_to_meeting'):
                meeting_info = metadata['meeting_info']
                logger.info(" Meeting Details Summary:")
                logger.info(f"   Subject: {meeting_info.get('subject', 'N/A')}")
                logger.info(f"   Start: {meeting_info.get('start_time', 'N/A')}")
                logger.info(f"   Organizer: {meeting_info.get('organizer', 'N/A')}")
                logger.info(f"   Attendees: {meeting_info.get('attendee_count', 0)}")
                logger.info(f"   Type: {meeting_info.get('meeting_type', 'N/A')}")
            else:
                logger.info(" Recording Type: Standalone (No Meeting Linked)")
            
            # Log file URLs
            logger.info(" Uploaded Files:")
            for file_type, url in metadata.get('uploaded_files', {}).items():
                logger.info(f"   {file_type}: {url}")
            
            # Log file sizes
            file_info = metadata.get('file_info', {})
            logger.info(f" Total Size: {file_info.get('total_size_mb', 0)} MB")
            
            logger.info("=" * 80)
            logger.info(" SENDING WEBHOOK REQUEST...")
            
            response = requests.post(
                self.webhook_url,
                json=metadata,
                headers={
                    'Content-Type': 'application/json',
                    'X-Webhook-Token': self.webhook_token
                },
                timeout=30  # 30 second timeout
            )
            
            # Log response details
            logger.info("=" * 80)
            logger.info(" WEBHOOK RESPONSE RECEIVED")
            logger.info("=" * 80)
            logger.info(f" Status Code: {response.status_code}")
            logger.info(f" Response Time: {response.elapsed.total_seconds():.2f} seconds")
            logger.info(f" Content Length: {len(response.content)} bytes")
            
            # Log response headers
            logger.info(" Response Headers:")
            for key, value in response.headers.items():
                logger.info(f"   {key}: {value}")
            
            # Log response body
            logger.info(" Response Body:")
            try:
                response_data = response.json()
                response_json = json.dumps(response_data, indent=2)
                for line_num, line in enumerate(response_json.split('\n'), 1):
                    logger.info(f"{line_num:3d}: {line}")
            except:
                logger.info(f"   (Raw text): {response.text}")
            
            logger.info("=" * 80)
            
            if response.status_code in [200, 201]:
                try:
                    response_data = response.json()
                    logger.info(f" Webhook sent successfully: {response_data.get('message', 'Success')}")
                    logger.info(f"   Action: {response_data.get('action', 'unknown')}")
                    logger.info(f"   Django PK: {response_data.get('pk', 'unknown')}")
                    logger.info(f"   Server Response: {response_data.get('status', 'success')}")
                except:
                    logger.info(f" Webhook sent successfully (non-JSON response)")
                
                logger.info(" WEBHOOK DELIVERY SUCCESSFUL!")
                logger.info("=" * 80)
                return True
            elif response.status_code == 401:
                logger.error(f" Webhook authentication failed - invalid token")
                logger.error(" Check webhook token configuration")
                logger.error("=" * 80)
                return False
            else:
                logger.error(f" Webhook failed with status {response.status_code}")
                logger.error(f" Response: {response.text}")
                logger.error("=" * 80)
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f" Webhook timeout after 30 seconds")
            logger.error(f" URL: {self.webhook_url}")
            logger.error(" Server may be slow or unresponsive")
            logger.error("=" * 80)
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f" Webhook connection failed: {e}")
            logger.error(f" URL: {self.webhook_url}")
            logger.error(" Check network connectivity to ops.fyelabs.com")
            logger.error("=" * 80)
            return False
        except Exception as e:
            logger.error(f" Webhook send failed: {e}")
            logger.error(f" URL: {self.webhook_url}")
            logger.error(" Unexpected error during webhook delivery")
            logger.error("=" * 80)
            return False
    
    def _create_upload_metadata(self, recording_info, files, urls):
        """Create comprehensive metadata for the upload including meeting details"""
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
            
            # Parse attendees JSON if available
            required_attendees = []
            optional_attendees = []
            try:
                if recording_info.get('required_attendees'):
                    import json
                    required_attendees = json.loads(recording_info['required_attendees'])
            except:
                pass
            
            try:
                if recording_info.get('optional_attendees'):
                    import json
                    optional_attendees = json.loads(recording_info['optional_attendees'])
            except:
                pass
            
            # Base metadata
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
            
            # Add meeting information if recording is linked to a meeting
            if recording_info.get('meeting_id'):
                metadata['meeting_info'] = {
                    'meeting_id': recording_info['meeting_id'],
                    'subject': recording_info.get('meeting_subject'),
                    'start_time': recording_info.get('meeting_start_time'),
                    'end_time': recording_info.get('meeting_end_time'),
                    'duration_minutes': recording_info.get('meeting_duration_minutes'),
                    'organizer': recording_info.get('meeting_organizer'),
                    'location': recording_info.get('meeting_location'),
                    'web_link': recording_info.get('meeting_web_link'),
                    'meeting_type': recording_info.get('meeting_type', 'teams'),
                    'is_teams_meeting': bool(recording_info.get('is_teams_meeting', False)),
                    'is_recurring': bool(recording_info.get('is_recurring', False)),
                    'attendee_count': recording_info.get('attendee_count', 0),
                    'required_attendees': required_attendees,
                    'optional_attendees': optional_attendees,
                    'calendar_event_id': recording_info.get('meeting_calendar_id'),
                    'discovered_at': recording_info.get('meeting_discovered_at'),
                    'is_linked_to_meeting': True
                }
                logger.info(f" Including meeting info for recording {recording_info['id']}: {recording_info.get('meeting_subject')}")
            else:
                metadata['meeting_info'] = {
                    'is_linked_to_meeting': False
                }
                logger.info(f" Recording {recording_info['id']} is not linked to any meeting")
            
            return metadata
            
        except Exception as e:
            logger.error(f" Metadata creation failed: {e}")
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
        logger.error(f" Failed to trigger upload for recording {recording_id}: {e}")
        return False