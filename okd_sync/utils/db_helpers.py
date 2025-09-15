"""
Database-based helper functions replacing file-based sync tracking
"""
import logging
from datetime import datetime
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_sync_manager import db_sync_manager, DatabaseSyncManager

logger = logging.getLogger(__name__)

def get_last_sync_time(sync_type: str = DatabaseSyncManager.MAIN_SUBMISSIONS) -> Optional[datetime]:
    """
    Get the timestamp of the last successful synchronization (database version)
    
    Args:
        sync_type: Type of sync to check (main_submissions, person_details, etc.)
    
    Returns:
        datetime or None: The timestamp of the last synchronization, or None if never synchronized
    """
    return db_sync_manager.get_last_sync_time(sync_type)

def set_last_sync_time(ts: datetime, sync_type: str = DatabaseSyncManager.MAIN_SUBMISSIONS):
    """
    Set the timestamp of the last successful synchronization (database version)
    
    This is now handled automatically by complete_sync() but provided for compatibility
    
    Args:
        ts: Timestamp to save
        sync_type: Type of sync being updated
    """
    logger.warning("set_last_sync_time() is deprecated. Use db_sync_manager.complete_sync() instead.")
    
    # For backward compatibility, create a minimal sync record
    history_id = db_sync_manager.start_sync(sync_type)
    db_sync_manager.complete_sync(history_id, sync_type, 0, ts)

class SyncContextManager:
    """
    Context manager for handling sync operations with proper error handling
    """
    
    def __init__(self, sync_type: str):
        self.sync_type = sync_type
        self.history_id = None
        self.records_processed = 0
        self.latest_timestamp = None
        self.metadata = {}
    
    def __enter__(self):
        """Start sync tracking"""
        self.history_id = db_sync_manager.start_sync(self.sync_type)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete or fail sync tracking based on whether exception occurred"""
        if exc_type is None:
            # No exception - sync succeeded
            db_sync_manager.complete_sync(
                self.history_id, 
                self.sync_type, 
                self.records_processed, 
                self.latest_timestamp,
                self.metadata
            )
        else:
            # Exception occurred - sync failed
            error_message = f"{exc_type.__name__}: {str(exc_val)}"
            db_sync_manager.fail_sync(self.history_id, self.sync_type, error_message)
        
        # Don't suppress the exception
        return False
    
    def update_progress(self, records_processed: int = None, 
                       latest_timestamp: datetime = None,
                       metadata: dict = None):
        """Update sync progress information"""
        if records_processed is not None:
            self.records_processed = records_processed
        if latest_timestamp is not None:
            self.latest_timestamp = latest_timestamp
        if metadata is not None:
            self.metadata.update(metadata)

# Convenience functions for specific sync types
def main_submissions_sync():
    """Context manager for main submissions sync"""
    return SyncContextManager(DatabaseSyncManager.MAIN_SUBMISSIONS)

def person_details_sync():
    """Context manager for person details sync"""
    return SyncContextManager(DatabaseSyncManager.PERSON_DETAILS)

def image_processing_sync():
    """Context manager for image processing sync"""
    return SyncContextManager(DatabaseSyncManager.IMAGE_PROCESSING)

def url_refresh_sync():
    """Context manager for URL refresh sync"""
    return SyncContextManager(DatabaseSyncManager.URL_REFRESH)