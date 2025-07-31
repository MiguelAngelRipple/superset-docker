"""
ODK Sync Main Module

This is the main entry point for the ODK Sync application.
It orchestrates the synchronization process between ODK Central and PostgreSQL.
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

# Import utility modules
from utils.helpers import get_last_sync_time, set_last_sync_time

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
    Main synchronization function
    
    This function orchestrates the entire synchronization process:
    1. Fetch new submissions from ODK Central
    2. Process attachments and upload to S3
    3. Update the database with new records
    4. Create a unified view for Superset
    
    Args:
        max_workers: Maximum number of concurrent workers for parallel processing
        prioritize_new: If True, prioritize processing new submissions first
    """
    # Get the last synchronization time
    last_sync = get_last_sync_time()
    if last_sync:
        logger.info(f"Last synchronization: {last_sync}")
    else:
        logger.info("Last synchronization: never")
    
    # Ensure the main table exists
    create_tables()
    
    # Fetch main submissions
    main_records = fetch_main_submissions(last_sync)
    if main_records:
        logger.info(f"Processing {len(main_records)} main submission records")
        
        # Process each submission
        for i, record in enumerate(main_records):
            main_records[i] = process_submission(record)
        
        # Process attachments and upload to S3
        if AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME:
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
            logger.info(f"S3 process completed in {duration:.2f} seconds")
        
        # Update the database with processed records
        upsert_submissions(main_records)
    
    # Refresh expired URLs for existing records (independent of new submissions)
    # This ensures that image URLs remain valid even if no new submissions are processed
    if ENABLE_URL_REFRESH:
        try:
            logger.info("Checking for expired image URLs that need refreshing...")
            refreshed_count = refresh_expired_urls(max_workers=max_workers)
            if refreshed_count > 0:
                logger.info(f"Refreshed {refreshed_count} expired image URLs")
                # Update HTML fields in unified table after URL refresh
                update_unified_html_after_refresh()
            else:
                logger.debug("No expired URLs found to refresh")
        except Exception as e:
            logger.error(f"Error during URL refresh process: {e}")
            logger.warning("Continuing with sync process despite URL refresh error")
    else:
        logger.debug("URL refresh is disabled (ENABLE_URL_REFRESH=false)")
    
    # Fetch person_details
    person_details_records = fetch_person_details(last_sync)
    if person_details_records:
        logger.info(f"Processing {len(person_details_records)} person_details records")
        
        # Filter person_details based on main submissions if we have a last_sync
        if last_sync and main_records:
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
    
    # Create or update the unified view after processing the data
    # Always recreate the unified table to ensure it has the latest data
    # and that it is correctly structured
    try:
        logger.info(f"Recreating unified table {UNIFIED_TABLE} to ensure it has the latest data")
        create_unified_view(force_recreate=True)
    except Exception as e:
        logger.error(f"Error recreating unified table: {e}")
        # Try to create the table from scratch if there was an error
        try:
            logger.info(f"Attempting to create unified table from scratch")
            # Execute the SQL query directly to create the unified table
            from db.connection import execute_query
            drop_query = f"DROP TABLE IF EXISTS \"{UNIFIED_TABLE}\" CASCADE"
            execute_query(drop_query)
            create_unified_view(force_recreate=True)
        except Exception as inner_e:
            logger.error(f"Failed to create unified table from scratch: {inner_e}")
            logger.warning("Continuing without unified table. This may affect Superset visualizations.")
    else:
        logger.info(f"Successfully recreated unified table {UNIFIED_TABLE}")
        # Verify that the table was created correctly
        if table_exists(UNIFIED_TABLE):
            logger.info(f"Verified that unified table {UNIFIED_TABLE} exists")
        else:
            logger.error(f"Unified table {UNIFIED_TABLE} does not exist after recreation attempt")
            logger.warning("This may affect Superset visualizations.")

    
    # Update last sync time if we have any records with timestamps
    if main_records:
        try:
            latest_ts = max(r['SubmittedDate'] for r in main_records if r.get('SubmittedDate'))
            set_last_sync_time(latest_ts)
            logger.info(f"Last synchronization updated to {latest_ts}")
        except Exception as e:
            logger.warning(f"Could not update last synchronization: {e}")
    
    if main_records or person_details_records:
        total_records = len(main_records) + len(person_details_records)
        logger.info(f"Total records processed: {total_records}")

if __name__ == "__main__":
    import time
    from datetime import datetime, timedelta
    
    # Configuration options
    logger.info("Synchronization service started. Running every %s seconds with %s workers. Prioritize new submissions: %s", 
                SYNC_INTERVAL, MAX_WORKERS, PRIORITIZE_NEW)
    logger.info("URL refresh enabled: %s. Refresh threshold: %s hours", 
                ENABLE_URL_REFRESH, URL_REFRESH_THRESHOLD_HOURS)
    
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
            
        except Exception as e:
            logger.error(f"Unexpected error in main cycle: {e}")
        
        # Sleep until the next interval
        time.sleep(SYNC_INTERVAL)
