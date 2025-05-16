import os
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

ODATA_URL = os.getenv("ODATA_URL")
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

def fetch_odata(last_sync):
    params = {}
    if last_sync:
        params['$filter'] = f"SubmittedDate gt '{last_sync}'"
    params['$format'] = 'json'
    url = ODATA_URL
    session = requests.Session()
    session.auth = (ODATA_USER, ODATA_PASS)
    results = []
    while url:
        try:
            r = session.get(url, params=params)
            if r.status_code != 200:
                logging.error(f"OData error {r.status_code}: {r.text}")
                return []
            data = r.json()
            results.extend(data.get('value', []))
            url = data.get('@odata.nextLink')
            params = {}
        except Exception as e:
            logging.error(f"Error fetching OData: {e}")
            return []
    return results

import json

def upsert_submissions(records):
    if not records:
        return 0
    conn = None
    inserted = 0
    try:
        conn = psycopg2.connect(f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}")
        cur = conn.cursor()
        # --- Create table if it doesn't exist ---
        columns = list(records[0].keys())
        # If the uuid column doesn't exist, add it as PRIMARY KEY
        if 'uuid' not in [c.lower() for c in columns]:
            columns.append('UUID')
            for rec in records:
                if 'UUID' not in rec or not rec.get('UUID'):
                    if '__id' in rec and rec['__id']:
                        rec['UUID'] = rec['__id']
                    elif 'meta' in rec and isinstance(rec['meta'], dict) and rec['meta'].get('instanceID'):
                        rec['UUID'] = rec['meta']['instanceID']
                    else:
                        logging.warning(f"Record without valid UUID, skipped.")
                        continue
        col_defs = []
        for col in columns:
            if col.lower() == 'uuid':
                col_defs.append(f'"{col}" TEXT PRIMARY KEY')
            elif col.lower().endswith('date'):
                col_defs.append(f'"{col}" TIMESTAMP NULL')
            else:
                col_defs.append(f'"{col}" TEXT NULL')
        create_table_sql = f'CREATE TABLE IF NOT EXISTS "Submissions" ({", ".join(col_defs)});'
        cur.execute(create_table_sql)
        conn.commit()
        # --- End table creation ---
        inserted = 0
        updated = 0
        col_names = [f'"{col}"' for col in columns]
        update_assignments = ', '.join([f'{c}=EXCLUDED.{c}' for c in col_names if c.lower() != '"uuid"'])
        for rec in records:
            if 'UUID' not in rec or not rec.get('UUID'):
                logging.warning(f"Record without valid UUID, skipped.")
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
                    INSERT INTO "Submissions" ({','.join(col_names)})
                    VALUES ({','.join(['%s']*len(columns))})
                    ON CONFLICT ("UUID") DO UPDATE SET {update_assignments}
                """, values)
                if cur.rowcount == 1:
                    inserted += 1
                elif cur.rowcount == 0:
                    updated += 1
            except Exception as e:
                logging.warning(f"Error upserting record (UUID: {rec.get('UUID', 'N/A')}): {e}\nRecord: {rec}")
                conn.rollback()
        conn.commit()
        logging.info(f"Inserted {inserted} new records, updated {updated} existing records")
    except Exception as e:
        logging.error(f"DB error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
    return inserted

def main():
    last_sync = get_last_sync_time()
    logging.info(f"Last synchronization: {last_sync if last_sync else 'never'}")
    records = fetch_odata(last_sync)
    if not records:
        logging.info("No new records to synchronize.")
        return
    inserted = upsert_submissions(records)
    try:
        latest_ts = max(r['SubmittedDate'] for r in records if r.get('SubmittedDate'))
        set_last_sync_time(latest_ts)
        logging.info(f"Last synchronization updated to {latest_ts}")
    except Exception as e:
        logging.warning(f"Could not update last synchronization: {e}")
    logging.info(f"Total records processed: {len(records)}")

if __name__ == "__main__":
    import time
    from datetime import datetime, timedelta
    SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "60"))
    logging.info("Synchronization service started. Running every %s seconds...", SYNC_INTERVAL)
    while True:
        try:
            logging.info("\n--- New synchronization cycle ---")
            main()
        except Exception as e:
            logging.error(f"Unexpected error in main cycle: {e}")
        next_sync = datetime.now() + timedelta(seconds=SYNC_INTERVAL)
        logging.info(f"Next execution: {next_sync.strftime('%Y-%m-%d %H:%M:%S')} (in {SYNC_INTERVAL} seconds)")
        time.sleep(SYNC_INTERVAL)
