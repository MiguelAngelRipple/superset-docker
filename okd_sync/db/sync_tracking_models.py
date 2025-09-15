"""
Database models for sync tracking system
"""
import logging
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Import existing database configuration
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS

logger = logging.getLogger(__name__)

# Create SQLAlchemy base
Base = declarative_base()

class SyncStatus(Base):
    """
    Table to track synchronization status for different data sources
    """
    __tablename__ = 'odk_sync_status'
    
    # Primary key - sync type identifier
    sync_type = Column(String(50), primary_key=True, nullable=False)
    
    # Last successful sync timestamp
    last_sync_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # Last sync attempt (regardless of success/failure)
    last_attempt_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Status of last sync attempt
    last_sync_status = Column(String(20), nullable=False, default='pending')  # 'success', 'error', 'in_progress', 'pending'
    
    # Error message if last sync failed
    last_error_message = Column(Text, nullable=True)
    
    # Total successful syncs
    successful_sync_count = Column(Integer, nullable=False, default=0)
    
    # Total failed syncs
    failed_sync_count = Column(Integer, nullable=False, default=0)
    
    # Records processed in last successful sync
    last_records_processed = Column(Integer, nullable=True)
    
    # Created timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    # Last updated timestamp
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SyncHistory(Base):
    """
    Historical log of all sync attempts for auditing and monitoring
    """
    __tablename__ = 'odk_sync_history'
    
    # Auto-incrementing primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Type of sync (main_submissions, person_details, images, etc.)
    sync_type = Column(String(50), nullable=False, index=True)
    
    # Sync attempt timestamp
    sync_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True)
    
    # Status of this sync attempt
    status = Column(String(20), nullable=False)  # 'success', 'error', 'in_progress'
    
    # Number of records processed
    records_processed = Column(Integer, nullable=True)
    
    # Processing duration in seconds
    duration_seconds = Column(Integer, nullable=True)
    
    # Error message if sync failed
    error_message = Column(Text, nullable=True)
    
    # Additional sync metadata (JSON as text)
    sync_metadata = Column(Text, nullable=True)
    
    # Service instance identifier
    service_instance = Column(String(100), nullable=True)

# Database connection setup
def get_sync_tracking_engine():
    """
    Get database engine for sync tracking tables
    """
    database_url = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(database_url, echo=False)

def create_sync_tracking_tables():
    """
    Create sync tracking tables if they don't exist
    """
    try:
        engine = get_sync_tracking_engine()
        Base.metadata.create_all(engine)
        logger.info("Sync tracking tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating sync tracking tables: {e}")
        return False

def get_sync_tracking_session():
    """
    Get database session for sync tracking operations
    """
    engine = get_sync_tracking_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()