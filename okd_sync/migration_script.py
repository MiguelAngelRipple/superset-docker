#!/usr/bin/env python3
"""
Migration script to transfer last_sync.txt data to database-based tracking
"""
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Import configuration and new database components
from config import LAST_SYNC_FILE
from db.sync_tracking_models import create_sync_tracking_tables
from utils.db_sync_manager import DatabaseSyncManager

def migrate_last_sync_file():
    """
    Migrate existing last_sync.txt to database-based tracking
    """
    logger.info("Starting migration from last_sync.txt to database tracking")
    
    # Create sync tracking tables
    logger.info("Creating sync tracking tables...")
    if not create_sync_tracking_tables():
        logger.error("Failed to create sync tracking tables")
        return False
    
    # Initialize database sync manager
    db_sync_manager = DatabaseSyncManager()
    
    # Check if last_sync.txt exists
    if not os.path.exists(LAST_SYNC_FILE):
        logger.info("No last_sync.txt file found - starting with clean database tracking")
        return True
    
    try:
        # Read the timestamp from the file
        with open(LAST_SYNC_FILE, 'r') as f:
            ts_str = f.read().strip()
            
        if not ts_str:
            logger.info("last_sync.txt is empty - starting with clean database tracking")
            return True
        
        # Parse the timestamp
        try:
            last_sync_timestamp = datetime.fromisoformat(ts_str)
            logger.info(f"Found last sync timestamp in file: {last_sync_timestamp}")
        except ValueError as e:
            logger.error(f"Could not parse timestamp '{ts_str}' from last_sync.txt: {e}")
            logger.info("Starting with clean database tracking")
            return True
        
        # Create initial database records for main sync types
        sync_types = [
            DatabaseSyncManager.MAIN_SUBMISSIONS,
            DatabaseSyncManager.PERSON_DETAILS,
        ]
        
        for sync_type in sync_types:
            # Check if this sync type already has database records
            existing_last_sync = db_sync_manager.get_last_sync_time(sync_type)
            
            if existing_last_sync:
                logger.info(f"Database already has sync record for {sync_type}: {existing_last_sync}")
                logger.info(f"File timestamp: {last_sync_timestamp}")
                
                # Use the more recent timestamp
                if last_sync_timestamp > existing_last_sync:
                    logger.info(f"Updating {sync_type} with more recent timestamp from file")
                    # Create a migration sync record
                    history_id = db_sync_manager.start_sync(sync_type + "_migration")
                    db_sync_manager.complete_sync(
                        history_id, 
                        sync_type + "_migration", 
                        0, 
                        last_sync_timestamp,
                        metadata={"source": "migrated_from_file", "original_file_timestamp": ts_str}
                    )
                    
                    # Update the main sync type
                    history_id = db_sync_manager.start_sync(sync_type)
                    db_sync_manager.complete_sync(
                        history_id, 
                        sync_type, 
                        0, 
                        last_sync_timestamp,
                        metadata={"source": "migrated_from_file"}
                    )
                else:
                    logger.info(f"Keeping existing database timestamp for {sync_type} (more recent)")
            else:
                # Create initial sync record
                logger.info(f"Creating initial database record for {sync_type}")
                history_id = db_sync_manager.start_sync(sync_type)
                db_sync_manager.complete_sync(
                    history_id, 
                    sync_type, 
                    0, 
                    last_sync_timestamp,
                    metadata={"source": "migrated_from_file", "original_file_timestamp": ts_str}
                )
        
        # Create backup of the original file
        backup_file = LAST_SYNC_FILE + ".backup"
        try:
            with open(backup_file, 'w') as f:
                f.write(ts_str)
            logger.info(f"Created backup of original file: {backup_file}")
        except Exception as e:
            logger.warning(f"Could not create backup file: {e}")
        
        logger.info("✅ Migration completed successfully")
        logger.info(f"Original file preserved as: {backup_file}")
        logger.info("You can now switch to using main_with_db_sync.py")
        
        # Show final status
        stats = db_sync_manager.get_sync_statistics()
        logger.info("Current database sync status:")
        for sync_type, status in stats.items():
            if sync_type != 'recent_history' and isinstance(status, dict):
                logger.info(f"  {sync_type}: {status.get('last_sync_timestamp', 'No timestamp')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False

def verify_migration():
    """
    Verify that the migration was successful
    """
    logger.info("Verifying migration...")
    
    try:
        db_sync_manager = DatabaseSyncManager()
        stats = db_sync_manager.get_sync_statistics()
        
        # Check that we have sync status records
        main_status = stats.get(DatabaseSyncManager.MAIN_SUBMISSIONS)
        if main_status and main_status.get('last_sync_timestamp'):
            logger.info("✅ Main submissions sync status found in database")
        else:
            logger.warning("⚠️ No main submissions sync status in database")
        
        person_status = stats.get(DatabaseSyncManager.PERSON_DETAILS)
        if person_status and person_status.get('last_sync_timestamp'):
            logger.info("✅ Person details sync status found in database")
        else:
            logger.warning("⚠️ No person details sync status in database")
        
        # Check sync history
        history = stats.get('recent_history', [])
        logger.info(f"✅ Found {len(history)} sync history records")
        
        return True
        
    except Exception as e:
        logger.error(f"Error verifying migration: {e}")
        return False

def show_current_status():
    """
    Show current sync status from both file and database
    """
    logger.info("=== Current Sync Status ===")
    
    # Check file-based status
    if os.path.exists(LAST_SYNC_FILE):
        try:
            with open(LAST_SYNC_FILE, 'r') as f:
                ts_str = f.read().strip()
            logger.info(f"File (last_sync.txt): {ts_str}")
        except Exception as e:
            logger.info(f"File (last_sync.txt): Error reading - {e}")
    else:
        logger.info("File (last_sync.txt): Not found")
    
    # Check database status
    try:
        db_sync_manager = DatabaseSyncManager()
        stats = db_sync_manager.get_sync_statistics()
        
        logger.info("Database status:")
        for sync_type, status in stats.items():
            if sync_type != 'recent_history' and isinstance(status, dict):
                last_sync = status.get('last_sync_timestamp', 'Never')
                success_count = status.get('successful_syncs', 0)
                logger.info(f"  {sync_type}: {last_sync} ({success_count} successful syncs)")
                
    except Exception as e:
        logger.info(f"Database status: Error - {e}")

if __name__ == "__main__":
    logger.info("ODK Sync Migration Tool")
    logger.info("=" * 50)
    
    # Show current status
    show_current_status()
    
    # Ask for confirmation
    print("\nThis will migrate your sync state from last_sync.txt to database tracking.")
    print("The original file will be backed up as last_sync.txt.backup")
    response = input("Continue with migration? (y/N): ").strip().lower()
    
    if response == 'y':
        # Perform migration
        if migrate_last_sync_file():
            # Verify migration
            verify_migration()
            
            print("\n" + "=" * 50)
            print("✅ Migration completed successfully!")
            print("")
            print("Next steps:")
            print("1. Test the new system: docker-compose exec odk_sync python main_with_db_sync.py")
            print("2. If working correctly: cp main_with_db_sync.py main.py")
            print("3. Restart the service: docker-compose restart odk_sync")
            print("4. Monitor logs: docker-compose logs -f odk_sync")
        else:
            print("❌ Migration failed. Check the logs above for details.")
    else:
        print("Migration cancelled.")
        show_current_status()