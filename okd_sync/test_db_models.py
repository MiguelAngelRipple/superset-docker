#!/usr/bin/env python3
"""
Test script to verify database models work correctly
"""
import logging
import sys
import os

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

def test_import():
    """Test importing the modules"""
    try:
        logger.info("Testing module imports...")
        
        # Test config import
        from config import PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASS
        logger.info(f"✅ Config imported: DB={PG_DB}, Host={PG_HOST}")
        
        # Test sync tracking models
        from db.sync_tracking_models import SyncStatus, SyncHistory, create_sync_tracking_tables
        logger.info("✅ Sync tracking models imported successfully")
        
        # Test database sync manager
        from utils.db_sync_manager import DatabaseSyncManager
        logger.info("✅ Database sync manager imported successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False

def test_table_creation():
    """Test creating the sync tracking tables"""
    try:
        logger.info("Testing table creation...")
        from db.sync_tracking_models import create_sync_tracking_tables
        
        success = create_sync_tracking_tables()
        if success:
            logger.info("✅ Sync tracking tables created successfully")
            return True
        else:
            logger.error("❌ Failed to create sync tracking tables")
            return False
    except Exception as e:
        logger.error(f"❌ Table creation failed: {e}")
        return False

def test_sync_manager():
    """Test basic sync manager functionality"""
    try:
        logger.info("Testing sync manager...")
        from utils.db_sync_manager import DatabaseSyncManager
        
        manager = DatabaseSyncManager()
        logger.info(f"✅ Sync manager created with instance: {manager.service_instance}")
        
        # Test getting last sync time (should return None for new installation)
        last_sync = manager.get_last_sync_time()
        logger.info(f"✅ Last sync time retrieved: {last_sync}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Sync manager test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting database models test...")
    
    all_passed = True
    
    # Run tests
    all_passed &= test_import()
    all_passed &= test_table_creation()
    all_passed &= test_sync_manager()
    
    if all_passed:
        logger.info("🎉 All tests passed! The database models are working correctly.")
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        sys.exit(1)