#!/usr/bin/env python3
"""
Simple Auto-Retry Manager for Failed Uploads
Runs as a background thread within the Flask app
"""

import threading
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from logging_config import app_logger as logger

class RetryManager:
    """Lightweight auto-retry system for failed uploads"""
    
    def __init__(self, db_path=None, retry_interval=300):  # 5 minutes
        # Database path
        if db_path is None:
            current_dir = Path(__file__).parent.absolute()
            db_path = current_dir / 'instance' / 'recordings.db'
        self.db_path = str(db_path)
        
        # Retry configuration
        self.retry_interval = retry_interval  # seconds between retry checks
        self.max_retries = 5  # max retry attempts per recording
        self.retry_backoff = [5, 15, 30, 60, 120]  # minutes to wait after each failure
        
        # Control
        self.running = False
        self.retry_thread = None
    
    def start(self):
        """Start the retry manager background thread"""
        if self.running:
            logger.warning(" Retry manager already running")
            return
        
        self.running = True
        self.retry_thread = threading.Thread(target=self._retry_loop, daemon=True)
        self.retry_thread.name = "RetryManager"
        self.retry_thread.start()
        logger.info(f" Auto-retry manager started (check every {self.retry_interval}s)")
    
    def stop(self):
        """Stop the retry manager"""
        self.running = False
        if self.retry_thread:
            self.retry_thread.join(timeout=5)
        logger.info(" Auto-retry manager stopped")
    
    def _get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_failed_recordings(self):
        """Get recordings that failed upload and are eligible for retry"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get recordings with failed upload status that haven't exceeded max retries
            query = """
                SELECT id, title, upload_status, created_at, retry_count, last_retry_at
                FROM recording 
                WHERE upload_status = 'failed' 
                AND (retry_count IS NULL OR retry_count < ?)
                ORDER BY created_at ASC
            """
            
            cursor.execute(query, (self.max_retries,))
            results = cursor.fetchall()
            conn.close()
            
            # Filter based on backoff timing
            eligible_recordings = []
            now = datetime.now()
            
            for row in results:
                recording = dict(row)
                retry_count = recording.get('retry_count') or 0
                last_retry_str = recording.get('last_retry_at')
                
                # If never retried, eligible immediately
                if not last_retry_str:
                    eligible_recordings.append(recording)
                    continue
                
                # Check if enough time has passed based on backoff
                try:
                    last_retry = datetime.fromisoformat(last_retry_str)
                    backoff_minutes = self.retry_backoff[min(retry_count, len(self.retry_backoff) - 1)]
                    next_retry_time = last_retry + timedelta(minutes=backoff_minutes)
                    
                    if now >= next_retry_time:
                        eligible_recordings.append(recording)
                        logger.debug(f" Recording {recording['id']} eligible for retry #{retry_count + 1}")
                    else:
                        time_left = (next_retry_time - now).total_seconds() / 60
                        logger.debug(f" Recording {recording['id']} retry in {time_left:.1f} minutes")
                        
                except Exception as e:
                    logger.error(f" Error parsing retry time for recording {recording['id']}: {e}")
                    # If parsing fails, allow retry
                    eligible_recordings.append(recording)
            
            return eligible_recordings
            
        except Exception as e:
            logger.error(f" Failed to get failed recordings: {e}")
            return []
    
    def _update_retry_attempt(self, recording_id, success=False):
        """Update retry count and timestamp"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            if success:
                # Reset retry count on success
                cursor.execute("""
                    UPDATE recording 
                    SET retry_count = 0, last_retry_at = ?, upload_status = 'completed'
                    WHERE id = ?
                """, (now, recording_id))
            else:
                # Increment retry count
                cursor.execute("""
                    UPDATE recording 
                    SET retry_count = COALESCE(retry_count, 0) + 1, 
                        last_retry_at = ?,
                        upload_status = 'failed'
                    WHERE id = ?
                """, (now, recording_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f" Failed to update retry attempt for recording {recording_id}: {e}")
    
    def _retry_upload(self, recording):
        """Attempt to retry upload for a single recording"""
        recording_id = recording['id']
        retry_count = (recording.get('retry_count') or 0) + 1
        
        logger.info(f" Retrying upload for recording {recording_id} (attempt #{retry_count})")
        logger.info(f"   Title: {recording['title']}")
        
        try:
            # Import here to avoid circular imports
            from background_uploader import trigger_upload
            
            # Attempt the upload
            success = trigger_upload(recording_id)
            
            if success:
                logger.info(f" Retry successful for recording {recording_id}")
                self._update_retry_attempt(recording_id, success=True)
                return True
            else:
                logger.warning(f" Retry failed for recording {recording_id}")
                self._update_retry_attempt(recording_id, success=False)
                return False
                
        except Exception as e:
            logger.error(f" Retry attempt failed for recording {recording_id}: {e}")
            self._update_retry_attempt(recording_id, success=False)
            return False
    
    def _retry_loop(self):
        """Main retry loop that runs in background thread"""
        logger.info(" Auto-retry loop started")
        
        while self.running:
            try:
                # Get eligible failed recordings
                failed_recordings = self._get_failed_recordings()
                
                if failed_recordings:
                    logger.info(f" Found {len(failed_recordings)} recordings eligible for retry")
                    
                    for recording in failed_recordings:
                        if not self.running:  # Check if we should stop
                            break
                            
                        self._retry_upload(recording)
                        
                        # Small delay between retries to avoid overwhelming the system
                        time.sleep(2)
                else:
                    logger.debug(" No failed uploads found for retry")
                
            except Exception as e:
                logger.error(f" Error in retry loop: {e}")
            
            # Wait for next check
            time.sleep(self.retry_interval)
        
        logger.info(" Auto-retry loop stopped")
    
    def manual_retry_all_failed(self):
        """Manually trigger retry for all failed recordings (ignoring backoff)"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get all failed recordings regardless of retry count/timing
            cursor.execute("""
                SELECT id, title, retry_count 
                FROM recording 
                WHERE upload_status = 'failed'
                ORDER BY created_at ASC
            """)
            
            failed_recordings = cursor.fetchall()
            conn.close()
            
            if not failed_recordings:
                logger.info(" No failed uploads found")
                return 0
            
            logger.info(f" Manually retrying {len(failed_recordings)} failed uploads")
            
            success_count = 0
            for recording in failed_recordings:
                if self._retry_upload(dict(recording)):
                    success_count += 1
                time.sleep(1)  # Small delay between retries
            
            logger.info(f" Manual retry complete: {success_count}/{len(failed_recordings)} succeeded")
            return success_count
            
        except Exception as e:
            logger.error(f" Manual retry failed: {e}")
            return 0
    
    def get_retry_stats(self):
        """Get statistics about retry status"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # Get counts by status
            cursor.execute("""
                SELECT 
                    upload_status,
                    COUNT(*) as count,
                    AVG(COALESCE(retry_count, 0)) as avg_retries
                FROM recording 
                GROUP BY upload_status
            """)
            
            stats = {}
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'count': row[1],
                    'avg_retries': round(row[2], 1)
                }
            
            # Get recordings with max retries exceeded
            cursor.execute("""
                SELECT COUNT(*) 
                FROM recording 
                WHERE upload_status = 'failed' AND retry_count >= ?
            """, (self.max_retries,))
            
            stats['max_retries_exceeded'] = cursor.fetchone()[0]
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f" Failed to get retry stats: {e}")
            return {}

# Global instance
_retry_manager_instance = None

def get_retry_manager():
    """Get global retry manager instance (singleton pattern)"""
    global _retry_manager_instance
    if _retry_manager_instance is None:
        _retry_manager_instance = RetryManager()
    return _retry_manager_instance

def start_retry_manager():
    """Start the global retry manager"""
    manager = get_retry_manager()
    manager.start()
    return manager

def stop_retry_manager():
    """Stop the global retry manager"""
    global _retry_manager_instance
    if _retry_manager_instance:
        _retry_manager_instance.stop()