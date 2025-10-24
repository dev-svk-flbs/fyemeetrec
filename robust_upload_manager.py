#!/usr/bin/env python3
"""
Robust Upload Manager using APScheduler + Event Triggers
Much more reliable than threads
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from logging_config import app_logger as logger
import atexit

class RobustUploadManager:
    """
    Ultra-reliable upload manager using APScheduler
    - Survives app restarts
    - Persistent job storage
    - Built-in retry logic
    - Much more robust than threads
    """
    
    def __init__(self, db_path=None):
        # Database path
        if db_path is None:
            current_dir = Path(__file__).parent.absolute()
            db_path = current_dir / 'instance' / 'recordings.db'
        self.db_path = str(db_path)
        
        # Retry configuration
        self.max_retries = 5
        self.retry_delays = [5, 15, 30, 60, 120]  # minutes
        
        # Setup APScheduler with persistent storage
        self.scheduler = None
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Setup APScheduler with persistent job storage"""
        try:
            # Job store configuration (uses SQLite for persistence)
            jobstores = {
                'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')
            }
            
            # Executor configuration
            executors = {
                'default': ThreadPoolExecutor(max_workers=3)
            }
            
            # Job defaults
            job_defaults = {
                'coalesce': True,  # Combine multiple pending instances of same job
                'max_instances': 1,  # Only one instance of each job at a time
                'misfire_grace_time': 300  # 5 minutes grace period for missed jobs
            }
            
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC'
            )
            
            logger.info("✅ APScheduler configured with persistent storage")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup scheduler: {e}")
            raise
    
    def start(self):
        """Start the robust upload manager"""
        try:
            if self.scheduler.running:
                logger.warning("⚠️ Upload manager already running")
                return
            
            self.scheduler.start()
            
            # Schedule regular failed upload checks
            self.scheduler.add_job(
                func=self._check_and_retry_failed_uploads,
                trigger='interval',
                minutes=5,  # Check every 5 minutes
                id='failed_upload_checker',
                name='Check and Retry Failed Uploads',
                replace_existing=True
            )
            
            # Check for failed uploads immediately on startup
            self.scheduler.add_job(
                func=self._check_and_retry_failed_uploads,
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=10),  # Run in 10 seconds
                id='startup_failed_check',
                name='Startup Failed Upload Check'
            )
            
            # Register cleanup on app exit
            atexit.register(self.stop)
            
            logger.info("🚀 Robust upload manager started with APScheduler")
            logger.info("   - Periodic failed upload checks: every 5 minutes")
            logger.info("   - Jobs persist across app restarts")
            logger.info("   - Built-in retry logic with exponential backoff")
            
        except Exception as e:
            logger.error(f"❌ Failed to start upload manager: {e}")
            raise
    
    def stop(self):
        """Stop the upload manager"""
        try:
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("⏹️ Robust upload manager stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping upload manager: {e}")
    
    def _get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _check_and_retry_failed_uploads(self):
        """Main job function: check for failed uploads and retry them"""
        try:
            logger.info("🔍 Checking for failed uploads to retry...")
            
            # Get failed recordings eligible for retry
            failed_recordings = self._get_failed_recordings()
            
            if not failed_recordings:
                logger.debug("✅ No failed uploads found")
                return
            
            logger.info(f"🔄 Found {len(failed_recordings)} recordings to retry")
            
            for recording in failed_recordings:
                try:
                    self._schedule_upload_retry(recording)
                except Exception as e:
                    logger.error(f"❌ Failed to schedule retry for recording {recording['id']}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error checking failed uploads: {e}")
    
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
                    backoff_minutes = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                    next_retry_time = last_retry + timedelta(minutes=backoff_minutes)
                    
                    if now >= next_retry_time:
                        eligible_recordings.append(recording)
                    
                except Exception as e:
                    logger.error(f"❌ Error parsing retry time for recording {recording['id']}: {e}")
                    # If parsing fails, allow retry
                    eligible_recordings.append(recording)
            
            return eligible_recordings
            
        except Exception as e:
            logger.error(f"❌ Failed to get failed recordings: {e}")
            return []
    
    def _schedule_upload_retry(self, recording):
        """Schedule an upload retry for a single recording"""
        recording_id = recording['id']
        retry_count = (recording.get('retry_count') or 0) + 1
        
        logger.info(f"📅 Scheduling upload retry for recording {recording_id} (attempt #{retry_count})")
        
        # Schedule the actual retry job
        job_id = f"retry_upload_{recording_id}_{retry_count}"
        
        self.scheduler.add_job(
            func=self._perform_upload_retry,
            trigger='date',
            run_date=datetime.now() + timedelta(seconds=5),  # Start in 5 seconds
            args=[recording],
            id=job_id,
            name=f"Retry Upload - Recording {recording_id} (Attempt {retry_count})",
            replace_existing=True,
            max_instances=1
        )
        
        logger.info(f"✅ Retry job scheduled: {job_id}")
    
    def _perform_upload_retry(self, recording):
        """Perform the actual upload retry"""
        recording_id = recording['id']
        retry_count = (recording.get('retry_count') or 0) + 1
        
        logger.info(f"🚀 Starting upload retry for recording {recording_id} (attempt #{retry_count})")
        logger.info(f"   Title: {recording['title']}")
        
        # Update retry tracking
        self._update_retry_attempt(recording_id)
        
        try:
            # Import here to avoid circular imports
            from background_uploader import trigger_upload
            
            # Attempt the upload
            success = trigger_upload(recording_id)
            
            if success:
                logger.info(f"✅ Upload retry successful for recording {recording_id}")
                # Reset retry count on success
                self._reset_retry_count(recording_id)
                return True
            else:
                logger.warning(f"⚠️ Upload retry failed for recording {recording_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Upload retry attempt failed for recording {recording_id}: {e}")
            return False
    
    def _update_retry_attempt(self, recording_id):
        """Update retry count and timestamp"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            # Increment retry count
            cursor.execute("""
                UPDATE recording 
                SET retry_count = COALESCE(retry_count, 0) + 1, 
                    last_retry_at = ?
                WHERE id = ?
            """, (now, recording_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to update retry attempt for recording {recording_id}: {e}")
    
    def _reset_retry_count(self, recording_id):
        """Reset retry count on successful upload"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE recording 
                SET retry_count = 0, last_retry_at = NULL
                WHERE id = ?
            """, (recording_id,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"❌ Failed to reset retry count for recording {recording_id}: {e}")
    
    def trigger_immediate_retry_all(self):
        """Manually trigger immediate retry for all failed uploads"""
        try:
            failed_recordings = self._get_failed_recordings()
            
            if not failed_recordings:
                logger.info("✅ No failed uploads found")
                return 0
            
            logger.info(f"🚀 Scheduling immediate retry for {len(failed_recordings)} failed uploads")
            
            for recording in failed_recordings:
                recording_id = recording['id']
                job_id = f"manual_retry_{recording_id}_{datetime.now().timestamp()}"
                
                self.scheduler.add_job(
                    func=self._perform_upload_retry,
                    trigger='date',
                    run_date=datetime.now() + timedelta(seconds=2),
                    args=[recording],
                    id=job_id,
                    name=f"Manual Retry - Recording {recording_id}",
                    max_instances=1
                )
            
            logger.info(f"✅ {len(failed_recordings)} retry jobs scheduled")
            return len(failed_recordings)
            
        except Exception as e:
            logger.error(f"❌ Manual retry scheduling failed: {e}")
            return 0
    
    def trigger_retry_on_event(self, event_name):
        """Trigger retry check based on app events"""
        logger.info(f"📢 Event triggered retry check: {event_name}")
        
        # Schedule immediate check
        job_id = f"event_retry_{event_name}_{datetime.now().timestamp()}"
        
        self.scheduler.add_job(
            func=self._check_and_retry_failed_uploads,
            trigger='date',
            run_date=datetime.now() + timedelta(seconds=1),
            id=job_id,
            name=f"Event Retry Check - {event_name}",
            max_instances=1
        )
    
    def get_job_status(self):
        """Get status of all scheduled jobs"""
        try:
            jobs = self.scheduler.get_jobs()
            
            job_info = []
            for job in jobs:
                job_info.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger)
                })
            
            return {
                'scheduler_running': self.scheduler.running if self.scheduler else False,
                'job_count': len(jobs),
                'jobs': job_info
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get job status: {e}")
            return {'error': str(e)}

# Global instance
_robust_manager_instance = None

def get_robust_upload_manager():
    """Get global robust upload manager instance (singleton)"""
    global _robust_manager_instance
    if _robust_manager_instance is None:
        _robust_manager_instance = RobustUploadManager()
    return _robust_manager_instance

def start_robust_upload_manager():
    """Start the global robust upload manager"""
    manager = get_robust_upload_manager()
    manager.start()
    return manager