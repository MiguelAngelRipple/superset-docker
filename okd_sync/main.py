import os
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import logging
from datetime import datetime
import json
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

# Base URL for ODK Central API
ODK_BASE_URL = os.getenv("ODK_BASE_URL")
ODK_PROJECT_ID = os.getenv("ODK_PROJECT_ID")
ODK_FORM_ID = os.getenv("ODK_FORM_ID")

# Construct the OData URL for main submissions
ODATA_URL = f"{ODK_BASE_URL}/v1/projects/{ODK_PROJECT_ID}/forms/{ODK_FORM_ID}.svc/Submissions"

# URL for person_details table - using the correct format for repeat data
PERSON_DETAILS_URL = f"{ODK_BASE_URL}/v1/projects/{ODK_PROJECT_ID}/forms/{ODK_FORM_ID}.svc/Submissions.person_details"

ODATA_USER = os.getenv("ODATA_USER")
ODATA_PASS = os.getenv("ODATA_PASS")
PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_DB = os.getenv("PG_DB")
PG_USER = os.getenv("PG_USER")
PG_PASS = os.getenv("PG_PASS")
LAST_SYNC_FILE = os.path.join(os.path.dirname(__file__), "last_sync.txt")


def get_last_sync_time():
    if not os.path.exists(LAST_SYNC_FILE):
        return None
    with open(LAST_SYNC_FILE, "r") as f:
        return f.read().strip()

def set_last_sync_time(ts):
    with open(LAST_SYNC_FILE, "w") as f:
        f.write(ts)

def fetch_odata(url, last_sync=None, filter_field='SubmittedDate'):
    params = {}
    if last_sync and filter_field:
        params['$filter'] = f"{filter_field} gt '{last_sync}'"
    params['$format'] = 'json'
    session = requests.Session()
    session.auth = (ODATA_USER, ODATA_PASS)
    results = []
    current_url = url
    while current_url:
        try:
            r = session.get(current_url, params=params)
            if r.status_code != 200:
                logging.error(f"OData error {r.status_code}: {r.text}")
                return []
            data = r.json()
            results.extend(data.get('value', []))
            current_url = data.get('@odata.nextLink')
            params = {}  # Clear params for next link
        except Exception as e:
            logging.error(f"Error fetching OData from {url}: {e}")
            return []
    return results

def fetch_main_submissions(last_sync):
    return fetch_odata(ODATA_URL, last_sync, 'SubmittedDate')

def fetch_person_details(last_sync):
    # For person_details, we use the parent's SubmittedDate for filtering
    # since it's a child table related to the main submissions
    return fetch_odata(PERSON_DETAILS_URL, last_sync, 'Submissions/SubmittedDate')

# Already imported at the top

def upsert_data(records, table_name, id_field='UUID'):
    """Generic function to upsert data into a specified table"""
    if not records:
        return 0
    conn = None
    inserted = 0
    updated = 0
    try:
        conn = psycopg2.connect(f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}")
        cur = conn.cursor()
        
        # --- Create table if it doesn't exist ---
        columns = list(records[0].keys())
        
        # Ensure ID field exists
        id_field_lower = id_field.lower()
        if id_field_lower not in [c.lower() for c in columns]:
            columns.append(id_field)
            for rec in records:
                if id_field not in rec or not rec.get(id_field):
                    if '__id' in rec and rec['__id']:
                        rec[id_field] = rec['__id']
                    elif 'meta' in rec and isinstance(rec['meta'], dict) and rec['meta'].get('instanceID'):
                        rec[id_field] = rec['meta']['instanceID']
                    else:
                        logging.warning(f"Record without valid {id_field}, skipped.")
                        continue
        
        # Define column types
        col_defs = []
        for col in columns:
            if col.lower() == id_field_lower:
                col_defs.append(f'"{col}" TEXT PRIMARY KEY')
            elif col.lower().endswith('date'):
                col_defs.append(f'"{col}" TIMESTAMP NULL')
            else:
                col_defs.append(f'"{col}" TEXT NULL')
        
        create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)});'
        cur.execute(create_table_sql)
        conn.commit()
        # --- End table creation ---
        
        # Prepare for upsert
        col_names = [f'"{col}"' for col in columns]
        update_assignments = ', '.join([f'{c}=EXCLUDED.{c}' for c in col_names if c.lower() != f'"{id_field_lower}"'])
        
        for rec in records:
            if id_field not in rec or not rec.get(id_field):
                logging.warning(f"Record without valid {id_field}, skipped.")
                continue
            
            values = []
            for col in columns:
                val = rec.get(col)
                if isinstance(val, (dict, list)):
                    values.append(json.dumps(val))
                else:
                    values.append(val)
            
            try:
                cur.execute(f"""
                    INSERT INTO "{table_name}" ({','.join(col_names)})
                    VALUES ({','.join(['%s']*len(columns))})
                    ON CONFLICT ("{id_field}") DO UPDATE SET {update_assignments}
                """, values)
                
                if cur.rowcount == 1:
                    inserted += 1
                elif cur.rowcount > 0:
                    updated += 1
            except Exception as e:
                logging.warning(f"Error upserting record ({id_field}: {rec.get(id_field, 'N/A')}) to {table_name}: {e}\nRecord: {rec}")
                conn.rollback()
        
        conn.commit()
        logging.info(f"{table_name}: Inserted {inserted} new records, updated {updated} existing records")
    except Exception as e:
        logging.error(f"DB error for {table_name}: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    
    return inserted + updated

def upsert_submissions(records):
    """Upsert main form submissions"""
    return upsert_data(records, "GRARentalDataCollection", "UUID")

def upsert_person_details(records):
    """Upsert person details records"""
    # For person_details, we need to ensure we have a proper primary key
    # In ODK Central repeat data, we typically use a combination of parent ID and index
    for record in records:
        # If the record doesn't have a UUID, create one using parent ID and index
        if 'UUID' not in record or not record.get('UUID'):
            # Get parent submission ID
            parent_id = record.get('__Submissions-id')
            # Get index or position in the repeat group
            index = record.get('__index') or record.get('index') or '0'
            if parent_id:
                # Create a composite key
                record['UUID'] = f"{parent_id}_{index}"
            else:
                logging.warning(f"Person details record without parent ID: {record}")
    
    return upsert_data(records, "GRARentalDataCollection_person_details", "UUID")

def create_unified_view():
    """
    Creates a unified view that combines data from the main tables and details.
    This function creates a new table that facilitates queries in Superset.
    """
    conn = None
    try:
        conn = psycopg2.connect(f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}")
        cur = conn.cursor()
        
        # Check if the tables exist before creating the view
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'GRARentalDataCollection'
            ) AS main_exists,
            EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'GRARentalDataCollection_person_details'
            ) AS details_exists;
        """)
        
        tables_exist = cur.fetchone()
        if not tables_exist or not tables_exist[0] or not tables_exist[1]:
            logging.warning("Cannot create the unified view because base tables are missing")
            return False
        
        # Get the column names from the main table
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'GRARentalDataCollection';
        """)
        main_columns = [row[0] for row in cur.fetchall()]
        # Get the column names from the details table
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'GRARentalDataCollection_person_details';
        """)
        details_columns = [row[0] for row in cur.fetchall()]
        
        # Identify the ID column in the main table (usually __id)
        main_id_col = '__id' if '__id' in main_columns else 'uuid' if 'uuid' in main_columns else 'UUID' if 'UUID' in main_columns else None
        if not main_id_col:
            logging.error("Could not identify the ID column in the main table")
            return False
        
        # Identify the submission date column (usually submitteddate or submitted_date)
        date_col = next((col for col in main_columns if col.lower() == 'submitteddate' or col.lower() == 'submitted_date'), None)
        
        # Identify the relationship column in the details table
        relation_col = next((col for col in details_columns if col.startswith('__Submissions')), None)
        if not relation_col:
            logging.error("Could not identify the relationship column in the details table")
            return False
        
        # Create unified table
        logging.info("Creating unified table GRARentalDataCollection_unified")
        
        # First drop the table if it already exists
        cur.execute('DROP TABLE IF EXISTS "GRARentalDataCollection_unified";')
        
        # Select relevant columns for the unified view
        main_select_cols = []
        details_select_cols = []
        
        # Include all columns from the main table
        important_main_cols = [col for col in main_columns if col != 'person_details@odata.navigationLink']
        # Make sure the main ID is included
        if main_id_col not in important_main_cols:
            important_main_cols.append(main_id_col)
        
        # Include all columns from the details table
        important_details_cols = [col for col in details_columns if col != 'UUID']
        # Make sure the relationship column is included
        if relation_col not in important_details_cols:
            important_details_cols.append(relation_col)
        
        # Build the SQL query that maintains the original names and adds a JSON field
        # First we select all columns from the main table
        main_cols_sql = ', '.join([f'g."{col}"' for col in main_columns if col != 'person_details@odata.navigationLink'])
        
        # Then we add the JSON column with the person details
        # We use PostgreSQL's row_to_json function to convert the entire details row into a JSON object
        
        create_table_sql = f"""
        CREATE TABLE "GRARentalDataCollection_unified" AS
        SELECT 
            g.*,
            row_to_json(p.*) AS person_details
        FROM 
            "GRARentalDataCollection" g
        LEFT JOIN 
            "GRARentalDataCollection_person_details" p 
        ON 
            p."{relation_col}" = g."{main_id_col}";
        """
        
        # Execute the SQL to create the unified table
        cur.execute(create_table_sql)
        
        # Create indexes to improve query performance
        cur.execute(f'CREATE INDEX idx_unified_main_id ON "GRARentalDataCollection_unified" ("{main_id_col}");')
        
        # Check if the jsonb extension is available
        try:
            # Try to create a JSONB index for searches in the JSON field
            cur.execute('CREATE INDEX idx_unified_person_details ON "GRARentalDataCollection_unified" USING GIN ((person_details::jsonb));')
        except Exception as e:
            logging.warning(f"Could not create GIN index for JSON field: {e}")
            # If it fails, we don't create the index but continue with execution
        
        conn.commit()
        logging.info("Unified table created successfully")
        return True
    except Exception as e:
        logging.error(f"Error creating the unified view: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def main():
    last_sync = get_last_sync_time()
    logging.info(f"Last synchronization: {last_sync if last_sync else 'never'}")
    
    # Fetch main submissions
    main_records = fetch_main_submissions(last_sync)
    if main_records:
        logging.info(f"Processing {len(main_records)} main submission records")
        upsert_submissions(main_records)
    
    # Fetch person_details
    person_details_records = fetch_person_details(last_sync)
    if person_details_records:
        logging.info(f"Processing {len(person_details_records)} person_details records")
        upsert_person_details(person_details_records)
    
    # Create or update the unified view after processing the data
    if main_records or person_details_records:
        create_unified_view()
    
    # Update last sync time if we have any records with timestamps
    if main_records:
        try:
            latest_ts = max(r['SubmittedDate'] for r in main_records if r.get('SubmittedDate'))
            set_last_sync_time(latest_ts)
            logging.info(f"Last synchronization updated to {latest_ts}")
        except Exception as e:
            logging.warning(f"Could not update last synchronization: {e}")
    
    if main_records or person_details_records:
        total_records = len(main_records) + len(person_details_records)
        logging.info(f"Total records processed: {total_records}")

if __name__ == "__main__":
    import time
    from datetime import datetime, timedelta
    SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "60"))
    logging.info("Synchronization service started. Running every %s seconds...", SYNC_INTERVAL)
    while True:
        try:
            main()
        except Exception as e:
            logging.error(f"Unexpected error in main cycle: {e}")
        time.sleep(SYNC_INTERVAL)
