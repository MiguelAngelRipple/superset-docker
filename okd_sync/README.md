# ODK OData to PostgreSQL Sync Service

This Python service synchronizes data from an ODK Central OData feed to a PostgreSQL database, performing upsert operations (insert or update) based on UUID. It's designed to run periodically in a Docker container as part of the Superset Docker deployment.

## Overview

The ODK Sync service performs the following functions:

1. Connects to an ODK Central instance via OData API
2. Retrieves new or updated form submissions since the last synchronization
3. Creates the PostgreSQL tables if they don't exist
4. Inserts new records or updates existing ones based on UUID
5. Creates a unified view that combines data from multiple tables
6. Tracks the last synchronization timestamp for incremental updates

## Project Structure

- `main.py`: Main synchronization script with all the logic
- `.env`: Environment variables for configuration (not to be committed to git)
- `requirements.txt`: Python dependencies
- `Dockerfile`: Container definition for the service
- `last_sync.txt`: Local file to store the last synchronization timestamp
- `README.md`: Documentation for the service

## Configuration

### Environment Variables

Copy the `.env.example` file to `.env` and fill in the values:

```
# ODK Central OData API configuration
ODK_BASE_URL=https://your-odk-central-instance.com
ODK_PROJECT_ID=1
ODK_FORM_ID=Your%20Form%20Name

# ODK Central credentials
ODATA_USER=your-username
ODATA_PASS=your-password

# PostgreSQL connection details
PG_HOST=postgres
PG_PORT=5432
PG_DB=Submissions
PG_USER=postgres
PG_PASS=postgres

# Synchronization interval in seconds
SYNC_INTERVAL=60
```

**Important**: Make sure the `PG_PORT` value matches the port exposed by your PostgreSQL container (default is 5432).

### Required Python Packages

The service requires the following Python packages (included in `requirements.txt`):

```
requests
psycopg2-binary
python-dotenv
```

## Running the Service

### Within Docker Compose

The service is designed to run as part of the Superset Docker deployment using Docker Compose. It's defined in the main `docker-compose.yml` file and will start automatically when you run:

```bash
docker-compose up -d
```

### Manual Execution

You can also run the script manually to test or trigger an immediate synchronization:

```bash
# From the host machine
docker-compose run --rm okd_sync python main.py

# Or directly within the container
docker exec -it superset-docker_okd_sync_1 python main.py
```

### Standalone Installation

If you want to run the service outside of Docker:

1. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the `.env` file with appropriate connection details

3. Run the script:
   ```bash
   python main.py
   ```

4. (Optional) Set up periodic execution with cron:
   ```
   * * * * * cd /path/to/okd_sync && /usr/bin/python3 main.py
   ```

## How It Works

### Synchronization Process

1. **Fetch Last Sync Time**: The script reads the last synchronization timestamp from `last_sync.txt`

2. **Query OData API**: It queries the ODK Central OData API for submissions newer than the last sync time

3. **Process Main Submissions**: It processes the main form submissions and inserts/updates them in the database

4. **Process Person Details**: It processes the person details related to each submission

5. **Create Unified View**: It creates a unified view that combines data from both tables, with person details stored in a JSON field

6. **Update Last Sync Time**: It updates the last synchronization timestamp

3. **Table Creation**: If the `Submissions` table doesn't exist, it's created automatically with columns matching the OData feed

4. **Upsert Operation**: For each record:
   - If the UUID doesn't exist in the database, the record is inserted
   - If the UUID exists, the record is updated with new values
   - If a record lacks a UUID, it's logged and skipped

5. **Update Last Sync Time**: The timestamp of the most recent submission is saved for the next run

### UUID Handling

The script uses the `UUID` field as the primary key for upsert operations. If a record doesn't have a `UUID` field, it tries to use:
1. The `__id` field
2. The `meta.instanceID` field

If no valid UUID can be found, the record is skipped and logged as a warning.

## Logging

The service logs its activity to the console with timestamps. You can view these logs using:

```bash
docker-compose logs -f okd_sync
```

Logs include:
- Synchronization start/end
- Number of records retrieved
- Number of records inserted/updated
- Errors and warnings
- Next scheduled execution time

## Unified Data Structure

The service creates three tables in the PostgreSQL database:

1. **GRARentalDataCollection**: Contains the main form submissions
2. **GRARentalDataCollection_person_details**: Contains the person details related to each submission
3. **GRARentalDataCollection_unified**: A unified view that combines data from both tables

The unified table structure includes:
- All fields from the main table with their original names
- A JSON field called `person_details` that contains all the data from the person details table

This structure allows you to query the data in Superset using standard SQL and JSON functions.

### Example Queries

```sql
-- Basic query to get main data with person details
SELECT 
  __id, 
  survey_date, 
  property_description,
  person_details->>'individual_first_name' as first_name,
  person_details->>'individual_last_name' as last_name
FROM "GRARentalDataCollection_unified"
LIMIT 10;

-- Query with JSON filtering
SELECT 
  __id, 
  survey_date, 
  person_details->>'individual_first_name' as first_name,
  person_details->>'mobile_1' as contact
FROM "GRARentalDataCollection_unified"
WHERE person_details::jsonb @> '{"individual_gender": "male"}'
LIMIT 5;
```

## Troubleshooting

### Common Issues

- **Connection Errors**: Check that your ODK Central instance is accessible and credentials are correct
- **Database Errors**: Verify PostgreSQL connection details and that the database exists
- **Permission Issues**: Ensure the PostgreSQL user has sufficient privileges
- **Port Conflicts**: If PostgreSQL fails to start, check for port conflicts with local services

### Quick Fixes

1. **Reset the Database**:
   ```bash
   docker exec -it superset_postgres psql -U postgres -d Submissions -c "DROP TABLE IF EXISTS \"GRARentalDataCollection_unified\", \"GRARentalDataCollection_person_details\", \"GRARentalDataCollection\" CASCADE;"
   ```

2. **Restart the Sync Service**:
   ```bash
   docker-compose restart okd_sync
   ```

## Security Considerations

- Never commit the `.env` file or `last_sync.txt` to version control
- Use strong passwords for both ODK Central and PostgreSQL
- Consider using environment variables instead of the `.env` file in production
