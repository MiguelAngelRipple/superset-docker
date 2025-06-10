# ODK OData to PostgreSQL Sync Service

This Python service synchronizes data from an ODK Central OData feed to a PostgreSQL database using SQLAlchemy ORM, performing upsert operations (insert or update) based on UUID. It's designed to run periodically in a Docker container as part of the Superset Docker deployment.

## Overview

The ODK Sync service performs the following functions:

1. Connects to an ODK Central instance via OData API
2. Retrieves new or updated form submissions since the last synchronization
3. Creates the PostgreSQL tables if they don't exist
4. Inserts new records or updates existing ones based on UUID
5. Creates a unified view that combines data from multiple tables
6. Tracks the last synchronization timestamp for incremental updates

## Project Structure

The project has been refactored into a modular structure for better maintainability and readability, now using SQLAlchemy ORM for database operations:

- `main.py`: Main entry point that orchestrates the synchronization process
- `config.py`: Centralized configuration management
- `db/`: Database-related modules
  - `connection.py`: Database connection handling
  - `sqlalchemy_models.py`: SQLAlchemy ORM models and table definitions
  - `sqlalchemy_operations.py`: Database operations using SQLAlchemy (upsert, create views, etc.)
- `odk/`: ODK Central API interaction
  - `api.py`: Functions to fetch data from ODK Central
  - `parser.py`: Functions to parse and process ODK data
- `storage/`: Storage operations
  - `s3.py`: AWS S3 operations for image uploads
- `utils/`: Utility functions
  - `helpers.py`: Helper functions for various tasks
  - `logger.py`: Logging configuration
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

# AWS S3 configuration
AWS_ACCESS_KEY=your-access-key
AWS_SECRET_KEY=your-secret-key
AWS_BUCKET_NAME=your-bucket-name
AWS_REGION=your-region

# Synchronization settings
SYNC_INTERVAL=60
MAX_WORKERS=10
PRIORITIZE_NEW=true
```

**Important**: Make sure the `PG_PORT` value matches the port exposed by your PostgreSQL container (default is 5432).

## Optimizations

The service includes several optimizations to improve performance and efficiency:

1. **Parallel Processing**: Uses multithreading to process attachments in parallel, significantly reducing the time required to upload images to S3.

2. **Priority Queue**: Implements a priority queue to ensure that new submissions are processed first, making the system more responsive to recent data.

3. **Modular Architecture**: Separates concerns into different modules, making the code more maintainable and easier to extend.

4. **Improved Error Handling**: Better error handling and logging to identify and resolve issues more quickly.

5. **Configurable Workers**: The number of worker threads can be configured through the `MAX_WORKERS` environment variable to optimize performance based on available resources.

### Required Python Packages

The service requires the following Python packages (included in `requirements.txt`):

```
requests>=2.28.0
psycopg2-binary>=2.9.3
python-dotenv>=0.20.0
boto3>=1.24.0
urllib3>=1.26.0
sqlalchemy>=1.4.0
sqlalchemy-utils>=0.38.0
Pillow>=9.0.0
```
### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
python main.py
```

## Running the Service

### Within Docker Compose

The service is designed to run as part of the Superset Docker deployment using Docker Compose. It's defined in the main `docker-compose.yml` file and will start automatically when you run:

Make sure to build the image first:

```bash
docker-compose build okd_sync
```

And then start the service:

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

3. **Create Tables**: SQLAlchemy models automatically create the necessary tables if they don't exist

4. **Process Main Submissions**: It processes the main form submissions and inserts/updates them in the database using SQLAlchemy ORM

5. **Process Person Details**: It processes the person details related to each submission

6. **Create Unified View**: It creates a unified view that combines data from both tables, with person details stored in a JSONB field

7. **Update Last Sync Time**: It updates the last synchronization timestamp

8. **Upsert Operation**: For each record:
   - If the UUID doesn't exist in the database, the record is inserted
   - If the UUID exists, the record is updated with new values
   - If a record lacks a UUID, it's logged and skipped

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

The service creates three tables in the PostgreSQL database using SQLAlchemy ORM:

1. **GRARentalDataCollection**: Contains the main form submissions
2. **GRARentalDataCollection_person_details**: Contains the person details related to each submission
3. **GRARentalDataCollection_unified**: A unified table that combines data from both tables

### SQLAlchemy Models

The application uses SQLAlchemy ORM models to define the database schema and handle database operations:

- **MainSubmission**: Model for the main submissions table
- **PersonDetail**: Model for the person details table
- **UnifiedView**: Model for the unified table

These models provide a more maintainable and type-safe way to interact with the database compared to raw SQL queries.

The unified table structure includes:
- All fields from the main table with their original names
- A JSON field called `person_details` that contains all the data from the person details table

This structure allows you to query the data in Superset using standard SQL and JSON functions.
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
