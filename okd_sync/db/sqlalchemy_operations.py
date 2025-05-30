"""
SQLAlchemy operations for the database tables
"""
import logging
import json
from sqlalchemy import text, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.connection import execute_query, table_exists
from db.sqlalchemy_models import engine, MainSubmission, PersonDetail, MAIN_TABLE, PERSON_DETAILS_TABLE, UNIFIED_TABLE

# Logging configuration
logger = logging.getLogger(__name__)

def upsert_submissions(records):
    """
    Insert or update records in the main table
    
    Args:
        records: List of records to insert or update
    """
    if not records:
        logger.info("No main records to upsert")
        return
    
    try:
        logger.info(f"Upserting {len(records)} records into {MAIN_TABLE}")
        
        with Session(engine) as session:
            for record in records:
                # Manejar campos con nombres especiales
                record_copy = record.copy()
                
                # Manejar __id -> id
                if '__id' in record_copy:
                    record_copy['id'] = record_copy.pop('__id')
                
                # Manejar __system -> system
                if '__system' in record_copy:
                    record_copy['system'] = record_copy.pop('__system')
                
                # Manejar person_details@odata.navigationLink -> person_details_link
                if 'person_details@odata.navigationLink' in record_copy:
                    record_copy['person_details_link'] = record_copy.pop('person_details@odata.navigationLink')
                
                # Check if the record already exists
                existing = session.query(MainSubmission).filter_by(UUID=record_copy['UUID']).first()
                
                if existing:
                    # Update existing record
                    for key, value in record_copy.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # Create new record
                    try:
                        new_record = MainSubmission(**record_copy)
                        session.add(new_record)
                    except TypeError as e:
                        logger.error(f"Error creating record: {e}")
                        logger.error(f"Record keys: {record_copy.keys()}")
                        # Try to filter only valid fields
                        valid_fields = {c.key for c in MainSubmission.__table__.columns}
                        filtered_record = {k: v for k, v in record_copy.items() if k in valid_fields}
                        logger.info(f"Trying with filtered fields: {filtered_record.keys()}")
                        new_record = MainSubmission(**filtered_record)
                        session.add(new_record)
            
            # Commit the changes
            session.commit()
        
        logger.info(f"Successfully upserted {len(records)} records into {MAIN_TABLE}")
    except Exception as e:
        logger.error(f"Error upserting records into {MAIN_TABLE}: {e}")
        raise

def upsert_person_details(records):
    """
    Insert or update records in the person details table
    
    Args:
        records: List of records to insert or update
    """
    if not records:
        logger.info("No person details records to upsert")
        return
    
    # Print diagnostic information about the records
    if records and len(records) > 0:
        sample_record = records[0]
        logger.info(f"Sample person_details record keys: {list(sample_record.keys())}")
        logger.info(f"Sample record: {sample_record}")
    
    # Check if records have the UUID field
    has_uuid = all('UUID' in record for record in records)
    logger.info(f"All records have UUID: {has_uuid}")
    
    # If no record has UUID, try to create records with a generated UUID
    if not has_uuid:
        logger.warning("No records have UUID field. Attempting to generate UUIDs.")
        for record in records:
            if '__id' in record and '__Submissions-id' in record:
                record['UUID'] = f"{record['__Submissions-id']}_{record['__id']}"
    
    # Count how many records have UUID after generation
    records_with_uuid = [r for r in records if 'UUID' in r]
    logger.info(f"Records with UUID after generation: {len(records_with_uuid)}/{len(records)}")
    
    # If there are still no records with UUID, we cannot continue
    if not records_with_uuid:
        logger.error("No records have UUID field and could not generate UUIDs. Cannot continue with person_details.")
        return
    
    # Continue only with records that have UUID
    records = records_with_uuid
    
    try:
        logger.info(f"Upserting {len(records)} records into {PERSON_DETAILS_TABLE}")
        
        success_count = 0
        error_count = 0
        
        with Session(engine) as session:
            for record in records:
                try:
                    # Handle fields with special names
                    record_copy = record.copy()
                    
                    # Handle __id -> id
                    if '__id' in record_copy:
                        record_copy['id'] = record_copy.pop('__id')
                    
                    # Handle __Submissions-id -> submissions_id
                    if '__Submissions-id' in record_copy:
                        record_copy['submissions_id'] = record_copy.pop('__Submissions-id')
                    
                    # Filter only valid fields to avoid errors
                    valid_fields = {c.key for c in PersonDetail.__table__.columns}
                    filtered_record = {k: v for k, v in record_copy.items() if k in valid_fields}
                    
                    # Verify that the filtered record has the UUID field
                    if 'UUID' not in filtered_record:
                        logger.warning(f"Skipping record without UUID after filtering: {record_copy}")
                        error_count += 1
                        continue
                    
                    # Check if the record already exists
                    existing = session.query(PersonDetail).filter_by(UUID=filtered_record['UUID']).first()
                    
                    if existing:
                        # Update existing record
                        for key, value in filtered_record.items():
                            if hasattr(existing, key):
                                setattr(existing, key, value)
                        success_count += 1
                    else:
                        # Create new record
                        new_record = PersonDetail(**filtered_record)
                        session.add(new_record)
                        success_count += 1
                except Exception as inner_e:
                    logger.error(f"Error processing record: {inner_e}")
                    if 'UUID' in record_copy:
                        logger.error(f"Record UUID: {record_copy['UUID']}")
                    logger.error(f"Record data: {record_copy}")
                    error_count += 1
            
            # Commit the changes
            try:
                session.commit()
                logger.info(f"Successfully committed changes to database: {success_count} successes, {error_count} errors")
            except Exception as commit_e:
                logger.error(f"Error committing changes to database: {commit_e}")
                session.rollback()
        
        logger.info(f"Completed upserting records into {PERSON_DETAILS_TABLE}")
    except Exception as e:
        logger.error(f"Error upserting records into {PERSON_DETAILS_TABLE}: {e}")
        # Not raising the exception so that the main process can continue
        logger.warning("Continuing with main process despite person details error")
        return

def create_unified_view(force_recreate=False):
    """
    Create a unified view that combines data from the main table and person details table
    
    This function creates a materialized table that combines data from the main table
    (GRARentalDataCollection) with the data from the person details table 
    (GRARentalDataCollection_person_details). The unified table facilitates querying data
    in tools like Superset without the need for complex joins.
    
    Args:
        force_recreate: If True, drop and recreate the unified view
    """
    try:
        # Check if the main table exists
        if not table_exists(MAIN_TABLE):
            logger.error(f"Main table {MAIN_TABLE} does not exist. Cannot create unified view.")
            return False
        
        # Check if the person details table exists
        person_details_exists = table_exists(PERSON_DETAILS_TABLE)
        if not person_details_exists:
            logger.warning(f"Person details table {PERSON_DETAILS_TABLE} does not exist. Creating unified view with main table only.")
        
        # Check if the unified table exists
        unified_exists = table_exists(UNIFIED_TABLE)
        
        # If the unified table exists and we're not forcing a recreate, return
        if unified_exists and not force_recreate:
            logger.info(f"Unified table {UNIFIED_TABLE} already exists. Skipping creation.")
            return True
        
        # If the unified table exists and we're forcing a recreate, drop it
        if unified_exists:
            logger.info(f"Dropping existing unified table {UNIFIED_TABLE}")
            drop_query = f"DROP TABLE IF EXISTS \"{UNIFIED_TABLE}\" CASCADE"
            execute_query(drop_query)
        
        # Create the unified table
        logger.info(f"Creating unified table {UNIFIED_TABLE}")
        
        # Base query to create the unified table from the main table
        create_query = f"""
        CREATE TABLE "{UNIFIED_TABLE}" AS
        SELECT 
            m.*,
            NULL::jsonb as person_details,
            CASE 
                WHEN m.building_image_url IS NOT NULL 
                THEN '<img src="' || m.building_image_url || '" width="200" />' 
                ELSE NULL 
            END as building_image_url_html
        FROM "{MAIN_TABLE}" m
        """
        
        # If the person details table exists, use a more complex query to include person details
        if person_details_exists:
            create_query = f"""
            CREATE TABLE "{UNIFIED_TABLE}" AS
            SELECT 
                m.*,
                jsonb_agg(
                    jsonb_build_object(
                        'UUID', p."UUID",
                        'person_type', p."person_type",
                        'shop_apt_unit_number', p."shop_apt_unit_number",
                        'type', p."type",
                        'business_name', p."business_name",
                        'tax_registered', p."tax_registered",
                        'tin', p."tin",
                        'individual_first_name', p."individual_first_name",
                        'individual_middle_name', p."individual_middle_name",
                        'individual_last_name', p."individual_last_name",
                        'individual_gender', p."individual_gender",
                        'individual_id_type', p."individual_id_type",
                        'individual_nin', p."individual_nin",
                        'individual_drivers_licence', p."individual_drivers_licence",
                        'individual_passport_number', p."individual_passport_number",
                        'passport_country', p."passport_country",
                        'individual_residence_permit_number', p."individual_residence_permit_number",
                        'residence_permit_country', p."residence_permit_country",
                        'individual_dob', p."individual_dob",
                        'mobile_1', p."mobile_1",
                        'mobile_2', p."mobile_2",
                        'email', p."email",
                        'occupancy', p."occupancy"
                    )
                ) FILTER (WHERE p."UUID" IS NOT NULL) as person_details,
                CASE 
                    WHEN m.building_image_url IS NOT NULL 
                    THEN '<img src="' || m.building_image_url || '" width="200" />' 
                    ELSE NULL 
                END as building_image_url_html
            FROM "{MAIN_TABLE}" m
            LEFT JOIN "{PERSON_DETAILS_TABLE}" p ON m."UUID" = p."__Submissions-id"
            GROUP BY m."UUID", m."__id", m."survey_date", m."survey_start", m."survey_end", m."logo", 
                     m."start_geopoint", m."property_location", m."property_description", 
                     m."generated_note_name_35", m."sum_owner", m."sum_landlord", m."sum_occupant", 
                     m."check_counts_1", m."check_counts_2", m."End", m."meta", m."__system", 
                     m."person_details@odata.navigationLink", m."building_image_url"
            """
        
        # Execute the query to create the unified table
        execute_query(create_query)
        
        # Add a primary key to the unified table
        pk_query = f"""
        ALTER TABLE "{UNIFIED_TABLE}" ADD PRIMARY KEY ("UUID")
        """
        execute_query(pk_query)
        
        logger.info(f"Successfully created unified table {UNIFIED_TABLE}")
        return True
    except Exception as e:
        logger.error(f"Error creating unified table {UNIFIED_TABLE}: {e}")
        return False