"""
Database-based sync tracking manager
"""
import logging
import json
import socket
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from typing import Optional, Dict, Any

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.sync_tracking_models import SyncStatus, SyncHistory, get_sync_tracking_session, create_sync_tracking_tables

logger = logging.getLogger(__name__)

class DatabaseSyncManager:
    """
    Database-based sync tracking manager that replaces file-based last_sync.txt
    """
    
    # Sync types
    MAIN_SUBMISSIONS = "main_submissions"
    PERSON_DETAILS = "person_details"
    IMAGE_PROCESSING = "image_processing"
    URL_REFRESH = "url_refresh"
    
    def __init__(self):
        """Initialize sync manager and create tables if needed"""
        self.service_instance = self._get_service_instance_id()
        create_sync_tracking_tables()
    
    def _get_service_instance_id(self) -> str:
        """Get unique identifier for this service instance"""
        try:
            hostname = socket.gethostname()
            pid = os.getpid()
            return f"{hostname}-{pid}"
        except:
            return f"unknown-{os.getpid()}"
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions with automatic cleanup"""
        session = get_sync_tracking_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def get_last_sync_time(self, sync_type: str = MAIN_SUBMISSIONS) -> Optional[datetime]:
        """
        Get the timestamp of the last successful synchronization
        
        Args:
            sync_type: Type of sync to check (main_submissions, person_details, etc.)
            
        Returns:
            datetime or None: The timestamp of the last synchronization, or None if never synchronized
        """
        try:
            with self.get_session() as session:
                sync_status = session.query(SyncStatus).filter_by(sync_type=sync_type).first()
                
                if sync_status and sync_status.last_sync_timestamp:
                    logger.info(f"Last {sync_type} sync: {sync_status.last_sync_timestamp}")
                    return sync_status.last_sync_timestamp
                else:
                    logger.info(f"No previous {sync_type} sync found")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting last sync time for {sync_type}: {e}")
            return None
    
    def start_sync(self, sync_type: str) -> int:
        """
        Mark the beginning of a sync process
        
        Args:
            sync_type: Type of sync being started
            
        Returns:
            int: History record ID for tracking this sync attempt
        """
        try:
            with self.get_session() as session:
                # Create history record for this sync attempt
                history_record = SyncHistory(
                    sync_type=sync_type,
                    sync_timestamp=datetime.now(timezone.utc),
                    status='in_progress',
                    service_instance=self.service_instance
                )
                session.add(history_record)
                session.flush()  # Get the ID without committing
                
                # Update or create status record
                sync_status = session.query(SyncStatus).filter_by(sync_type=sync_type).first()
                if sync_status:
                    sync_status.last_attempt_timestamp = datetime.now(timezone.utc)
                    sync_status.last_sync_status = 'in_progress'
                    sync_status.last_error_message = None
                    sync_status.updated_at = datetime.now(timezone.utc)
                else:
                    sync_status = SyncStatus(
                        sync_type=sync_type,
                        last_attempt_timestamp=datetime.now(timezone.utc),
                        last_sync_status='in_progress',
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(sync_status)
                
                session.commit()
                logger.info(f"Started {sync_type} sync with history ID: {history_record.id}")
                return history_record.id
                
        except Exception as e:
            logger.error(f"Error starting sync for {sync_type}: {e}")
            return -1
    
    def complete_sync(self, history_id: int, sync_type: str, 
                     records_processed: int = 0, 
                     latest_timestamp: Optional[datetime] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """
        Mark a sync process as completed successfully
        
        Args:
            history_id: ID from start_sync call
            sync_type: Type of sync being completed
            records_processed: Number of records processed
            latest_timestamp: Latest record timestamp for incremental sync
            metadata: Additional metadata to store
        """
        try:
            with self.get_session() as session:
                # Update history record
                history_record = session.query(SyncHistory).filter_by(id=history_id).first()
                if history_record:
                    start_time = history_record.sync_timestamp
                    duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
                    
                    history_record.status = 'success'
                    history_record.records_processed = records_processed
                    history_record.duration_seconds = duration
                    history_record.sync_metadata = json.dumps(metadata) if metadata else None
                
                # Update status record
                sync_status = session.query(SyncStatus).filter_by(sync_type=sync_type).first()
                if sync_status:
                    sync_status.last_sync_status = 'success'
                    sync_status.successful_sync_count += 1
                    sync_status.last_records_processed = records_processed
                    sync_status.last_error_message = None
                    sync_status.updated_at = datetime.now(timezone.utc)
                    
                    # Update last sync timestamp if provided
                    if latest_timestamp:
                        sync_status.last_sync_timestamp = latest_timestamp
                
                session.commit()
                logger.info(f"Completed {sync_type} sync: {records_processed} records processed")
                
        except Exception as e:
            logger.error(f"Error completing sync for {sync_type}: {e}")
    
    def fail_sync(self, history_id: int, sync_type: str, error_message: str):
        """
        Mark a sync process as failed
        
        Args:
            history_id: ID from start_sync call
            sync_type: Type of sync that failed
            error_message: Error description
        """
        try:
            with self.get_session() as session:
                # Update history record
                history_record = session.query(SyncHistory).filter_by(id=history_id).first()
                if history_record:
                    start_time = history_record.sync_timestamp
                    duration = int((datetime.now(timezone.utc) - start_time).total_seconds())
                    
                    history_record.status = 'error'
                    history_record.duration_seconds = duration
                    history_record.error_message = error_message[:1000]  # Truncate if too long
                
                # Update status record
                sync_status = session.query(SyncStatus).filter_by(sync_type=sync_type).first()
                if sync_status:
                    sync_status.last_sync_status = 'error'
                    sync_status.failed_sync_count += 1
                    sync_status.last_error_message = error_message[:1000]
                    sync_status.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                logger.error(f"Failed {sync_type} sync: {error_message}")
                
        except Exception as e:
            logger.error(f"Error recording sync failure for {sync_type}: {e}")
    
    def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive sync statistics for monitoring
        
        Returns:
            Dict containing sync statistics
        """
        try:
            with self.get_session() as session:
                stats = {}
                
                # Get status for each sync type
                sync_statuses = session.query(SyncStatus).all()
                for status in sync_statuses:
                    stats[status.sync_type] = {
                        'last_sync_timestamp': status.last_sync_timestamp.isoformat() if status.last_sync_timestamp else None,
                        'last_attempt_timestamp': status.last_attempt_timestamp.isoformat() if status.last_attempt_timestamp else None,
                        'last_sync_status': status.last_sync_status,
                        'successful_syncs': status.successful_sync_count,
                        'failed_syncs': status.failed_sync_count,
                        'last_records_processed': status.last_records_processed,
                        'last_error': status.last_error_message
                    }
                
                # Get recent sync history
                recent_history = session.query(SyncHistory).order_by(
                    SyncHistory.sync_timestamp.desc()
                ).limit(10).all()
                
                stats['recent_history'] = []
                for history in recent_history:
                    stats['recent_history'].append({
                        'sync_type': history.sync_type,
                        'timestamp': history.sync_timestamp.isoformat(),
                        'status': history.status,
                        'records_processed': history.records_processed,
                        'duration_seconds': history.duration_seconds,
                        'service_instance': history.service_instance
                    })
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting sync statistics: {e}")
            return {'error': str(e)}
    
    def cleanup_old_history(self, days_to_keep: int = 30):
        """
        Clean up old sync history records to prevent table bloat
        
        Args:
            days_to_keep: Number of days of history to retain
        """
        try:
            with self.get_session() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
                
                deleted_count = session.query(SyncHistory).filter(
                    SyncHistory.sync_timestamp < cutoff_date
                ).delete()
                
                session.commit()
                logger.info(f"Cleaned up {deleted_count} old sync history records")
                
        except Exception as e:
            logger.error(f"Error cleaning up sync history: {e}")

# Create global instance
db_sync_manager = DatabaseSyncManager()