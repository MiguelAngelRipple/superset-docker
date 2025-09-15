"""
ODK Sync Main Module with Database-based Sync Tracking

This version replaces file-based last_sync.txt with database tracking
"""
import logging
import time
from datetime import datetime

import sys
import os

# Add the current directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import configuration
from config import MAX_WORKERS, PRIORITIZE_NEW, UNIFIED_TABLE, SYNC_INTERVAL, AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_BUCKET_NAME, ENABLE_URL_REFRESH, URL_REFRESH_THRESHOLD_HOURS

# Import NEW database-based sync helpers
from utils.db_helpers import main_submissions_sync, person_details_sync, image_processing_sync, url_refresh_sync
from utils.db_sync_manager import db_sync_manager, DatabaseSyncManager

# Import ODK modules
from odk.api import fetch_main_submissions, fetch_person_details
from odk.parser import process_submission

# Import database modules
from db.connection import table_exists
from db.sqlalchemy_models import create_tables, UNIFIED_TABLE
from db.sqlalchemy_operations import upsert_submissions, upsert_person_details, create_unified_view

# Import storage modules
from storage.s3 import process_attachments, refresh_expired_urls, update_unified_html_after_refresh

# Configure logging
logger = logging.getLogger(__name__)

def main(max_workers=MAX_WORKERS, prioritize_new=PRIORITIZE_NEW):
    """
    Main synchronization function with database-based sync tracking
    
    This function orchestrates the entire synchronization process with proper
    error handling and progress tracking in the database.
    
    Args:
        max_workers: Maximum number of concurrent workers for parallel processing
        prioritize_new: If True, prioritize processing new submissions first
    """
    
    # Ensure the main table exists
    create_tables()
    
    # Track main submissions sync
    with main_submissions_sync() as main_sync:
        try:
            # Get the last synchronization time from database
            last_sync = db_sync_manager.get_last_sync_time(DatabaseSyncManager.MAIN_SUBMISSIONS)
            if last_sync:
                logger.info(f"Last main submissions sync: {last_sync}")
            else:
                logger.info("No previous main submissions sync found - full sync will be performed")
            
            # Fetch main submissions
            main_records = fetch_main_submissions(last_sync)
            
            if main_records:
                logger.info(f"Processing {len(main_records)} main submission records")
                
                # Process each submission
                for i, record in enumerate(main_records):
                    main_records[i] = process_submission(record)
                
                # Update sync progress
                main_sync.update_progress(
                    records_processed=len(main_records),
                    metadata={'raw_records_fetched': len(main_records)}
                )
                
                # Process attachments and upload to S3 with separate tracking
                if AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME:
                    with image_processing_sync() as image_sync:
                        logger.info("Processing attachments and uploading to S3...")
                        
                        # Log sample property_description for debugging
                        if main_records and 'property_description' in main_records[0]:
                            sample_record = main_records[0]
                            prop_desc = sample_record['property_description']
                            prop_desc_type = type(prop_desc).__name__
                            logger.info(f"Sample property_description type: {prop_desc_type}")
                            
                            if isinstance(prop_desc, dict) and 'building_image' in prop_desc:
                                logger.info(f"Found building_image in property_description dict")
                        
                        # Process images with parallel processing
                        start_time = datetime.now()
                        main_records = process_attachments(main_records, max_workers=max_workers, prioritize_new=prioritize_new)
                        end_time = datetime.now()
                        duration = (end_time - start_time).total_seconds()
                        
                        # Update image processing progress
                        images_processed = sum(1 for record in main_records if record.get('building_image_url'))
                        image_sync.update_progress(
                            records_processed=images_processed,
                            metadata={
                                'processing_duration_seconds': duration,
                                'total_records': len(main_records),
                                'images_found': images_processed
                            }
                        )
                        
                        logger.info(f"S3 process completed in {duration:.2f} seconds")
                
                # Update the database with processed records
                upsert_submissions(main_records)
                
                # Update sync with final timestamp
                if main_records:
                    try:
                        latest_ts = max(r['SubmittedDate'] for r in main_records if r.get('SubmittedDate'))
                        main_sync.update_progress(latest_timestamp=latest_ts)
                        logger.info(f"Latest submission timestamp: {latest_ts}")
                    except Exception as e:
                        logger.warning(f"Could not determine latest timestamp: {e}")
            
            else:
                logger.info("No new main submissions found")
                main_sync.update_progress(records_processed=0)
        
        except Exception as e:
            logger.error(f"Error in main submissions sync: {e}")
            raise  # Re-raise to trigger sync failure recording
    
    # URL refresh process (independent of new submissions)
    if ENABLE_URL_REFRESH:
        with url_refresh_sync() as refresh_sync:
            try:
                logger.info("Checking for expired image URLs that need refreshing...")
                refreshed_count = refresh_expired_urls(max_workers=max_workers)
                
                refresh_sync.update_progress(
                    records_processed=refreshed_count,
                    metadata={'threshold_hours': URL_REFRESH_THRESHOLD_HOURS}
                )
                
                if refreshed_count > 0:
                    logger.info(f"Refreshed {refreshed_count} expired image URLs")
                    # Update HTML fields in unified table after URL refresh
                    update_unified_html_after_refresh()
                else:
                    logger.debug("No expired URLs found to refresh")
                    
            except Exception as e:
                logger.error(f"Error during URL refresh process: {e}")
                raise  # Re-raise to trigger sync failure recording
    else:
        logger.debug("URL refresh is disabled (ENABLE_URL_REFRESH=false)")
    
    # Person details sync
    with person_details_sync() as person_sync:
        try:
            # Get last sync time for person details (could be different from main submissions)
            person_last_sync = db_sync_manager.get_last_sync_time(DatabaseSyncManager.PERSON_DETAILS)
            
            # Fetch person_details
            person_details_records = fetch_person_details(person_last_sync)
            
            if person_details_records:
                logger.info(f"Processing {len(person_details_records)} person_details records")
                
                # Filter person_details based on main submissions if we have recent main records
                if person_last_sync and main_records:
                    # Get the UUIDs of main submissions that were processed in this cycle
                    processed_uuids = {record.get('UUID') for record in main_records if record.get('UUID')}
                    
                    # Filter person_details to only include those related to processed main submissions
                    filtered_person_details = []
                    for person_record in person_details_records:
                        # Check if this person_detail belongs to a processed main submission
                        submission_id = person_record.get('__Submissions-id')
                        if submission_id and submission_id in processed_uuids:
                            filtered_person_details.append(person_record)
                    
                    logger.info(f"Filtered person_details: {len(filtered_person_details)} out of {len(person_details_records)} records belong to processed main submissions")
                    person_details_records = filtered_person_details
                
                upsert_person_details(person_details_records)
                
                # Update progress
                person_sync.update_progress(
                    records_processed=len(person_details_records),
                    metadata={'total_fetched': len(person_details_records)}
                )
            else:
                logger.info("No new person details found")
                person_sync.update_progress(records_processed=0)
                
        except Exception as e:
            logger.error(f"Error in person details sync: {e}")
            raise  # Re-raise to trigger sync failure recording
    
    # Create or update the unified view after processing the data
    try:
        logger.info(f"Recreating unified table {UNIFIED_TABLE} to ensure it has the latest data")
        create_unified_view(force_recreate=True)
        logger.info(f"Successfully recreated unified table {UNIFIED_TABLE}")
        
        # Verify that the table was created correctly
        if table_exists(UNIFIED_TABLE):
            logger.info(f"Verified that unified table {UNIFIED_TABLE} exists")
        else:
            logger.error(f"Unified table {UNIFIED_TABLE} does not exist after recreation attempt")
            
    except Exception as e:
        logger.error(f"Error recreating unified table: {e}")
        # Try to create the table from scratch if there was an error
        try:
            logger.info(f"Attempting to create unified table from scratch")
            from db.connection import execute_query
            drop_query = f"DROP TABLE IF EXISTS \"{UNIFIED_TABLE}\" CASCADE"
            execute_query(drop_query)
            create_unified_view(force_recreate=True)
        except Exception as inner_e:
            logger.error(f"Failed to create unified table from scratch: {inner_e}")
            logger.warning("Continuing without unified table. This may affect Superset visualizations.")
    
    # Log final statistics
    total_main = len(main_records) if 'main_records' in locals() and main_records else 0
    total_person = len(person_details_records) if 'person_details_records' in locals() and person_details_records else 0
    
    if total_main > 0 or total_person > 0:
        logger.info(f"Sync cycle completed: {total_main} main records, {total_person} person details")

def get_sync_health_status():
    """
    Get comprehensive sync health status for monitoring
    
    Returns:
        Dict containing sync health information
    """
    try:
        stats = db_sync_manager.get_sync_statistics()
        
        # Add service health indicators
        stats['service_info'] = {
            'service_instance': db_sync_manager.service_instance,
            'current_time': datetime.now().isoformat(),
            'sync_interval': SYNC_INTERVAL,
            'max_workers': MAX_WORKERS,
            'url_refresh_enabled': ENABLE_URL_REFRESH
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting sync health status: {e}")
        return {'error': str(e)}

if __name__ == "__main__":
    import time
    from datetime import datetime, timedelta
    
    # Configuration options
    logger.info("Database-based synchronization service started.")
    logger.info(f"Running every {SYNC_INTERVAL} seconds with {MAX_WORKERS} workers. Prioritize new: {PRIORITIZE_NEW}")
    logger.info(f"URL refresh enabled: {ENABLE_URL_REFRESH}. Refresh threshold: {URL_REFRESH_THRESHOLD_HOURS} hours")
    logger.info(f"Service instance: {db_sync_manager.service_instance}")
    
    # Track the last run time to detect long-running processes
    last_run_time = None
    
    while True:
        current_time = datetime.now()
        
        # Check if the previous run is taking too long
        if last_run_time and (current_time - last_run_time).total_seconds() > SYNC_INTERVAL * 2:
            logger.warning(f"Previous synchronization cycle is taking longer than expected: "
                          f"{(current_time - last_run_time).total_seconds():.1f} seconds")
        
        last_run_time = current_time
        
        try:
            # Run the main synchronization process
            main(max_workers=MAX_WORKERS, prioritize_new=PRIORITIZE_NEW)
            
            # Update last_run_time to indicate successful completion
            last_run_time = datetime.now()
            
            # Log sync statistics periodically
            if current_time.minute % 10 == 0:  # Every 10 minutes
                stats = get_sync_health_status()
                logger.info(f"Sync health check: {stats.get('service_info', {})}")
            
        except Exception as e:
            logger.error(f"Unexpected error in main cycle: {e}")
        
        # Periodic cleanup of old history records (once per hour)
        if current_time.hour != getattr(get_sync_health_status, '_last_cleanup_hour', -1):
            try:
                db_sync_manager.cleanup_old_history(days_to_keep=30)
                get_sync_health_status._last_cleanup_hour = current_time.hour
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
        
        # Sleep until the next interval
        time.sleep(SYNC_INTERVAL)