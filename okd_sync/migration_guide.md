# Migration Guide: File-based to Database-based Sync Tracking

## Overview

This guide shows how to migrate from the current `last_sync.txt` file-based tracking to a database-based sync tracking system.

## Benefits of Database-based Sync Tracking

### Current Issues with `last_sync.txt`:
- ❌ **Container Persistence**: File lost when container restarts without volumes
- ❌ **Scaling Issues**: Multiple service instances can't share state
- ❌ **No Audit Trail**: No history of sync attempts or failures
- ❌ **Race Conditions**: Concurrent processes could corrupt file
- ❌ **Backup Complexity**: Sync state not included in database backups

### Benefits of Database Approach:
- ✅ **Persistent**: State survives container restarts
- ✅ **Scalable**: Multiple service instances can coordinate
- ✅ **Audit Trail**: Complete history of all sync attempts
- ✅ **Thread-safe**: Database transactions prevent race conditions
- ✅ **Monitoring**: Rich statistics and health monitoring
- ✅ **Backup Integration**: Sync state backed up with data

## Database Schema

The new system creates two tables:

### `odk_sync_status` - Current Status
```sql
CREATE TABLE odk_sync_status (
    sync_type VARCHAR(50) PRIMARY KEY,           -- 'main_submissions', 'person_details', etc.
    last_sync_timestamp TIMESTAMP WITH TIME ZONE, -- Last successful sync
    last_attempt_timestamp TIMESTAMP WITH TIME ZONE, -- Last attempt (success or failure)
    last_sync_status VARCHAR(20) DEFAULT 'pending', -- 'success', 'error', 'in_progress'
    last_error_message TEXT,                     -- Error details if failed
    successful_sync_count INTEGER DEFAULT 0,     -- Total successful syncs
    failed_sync_count INTEGER DEFAULT 0,         -- Total failed syncs
    last_records_processed INTEGER,              -- Records in last successful sync
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### `odk_sync_history` - Audit Trail
```sql
CREATE TABLE odk_sync_history (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,              -- Type of sync
    sync_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(), -- When sync started
    status VARCHAR(20) NOT NULL,                 -- 'success', 'error', 'in_progress'
    records_processed INTEGER,                   -- Number of records processed
    duration_seconds INTEGER,                    -- How long sync took
    error_message TEXT,                          -- Error details if failed
    metadata TEXT,                               -- Additional JSON metadata
    service_instance VARCHAR(100)                -- Which service instance ran sync
);
```

## Migration Steps

### Step 1: Backup Current State
```bash
# Backup current last_sync.txt if it exists
docker-compose exec odk_sync cat /app/last_sync.txt > backup_last_sync.txt 2>/dev/null || echo "No last_sync.txt found"

# Backup database before migration
docker exec -t superset_postgres pg_dump -U postgres Submissions > backup_before_migration.sql
```

### Step 2: Add New Dependencies
Add to `okd_sync/requirements.txt` if not already present:
```
SQLAlchemy>=1.4.0
```

### Step 3: Update Docker Compose (if needed)
Ensure your `docker-compose.yml` includes the database dependency:
```yaml
okd_sync:
  build:
    context: ./okd_sync
  depends_on:
    - postgres  # Make sure this dependency exists
  # ... rest of configuration
```

### Step 4: Deploy New Implementation

#### Option A: Gradual Migration (Recommended)
1. **Test the new system alongside the old:**
```bash
# Test database connection and table creation
docker-compose exec odk_sync python -c "
from db.sync_tracking_models import create_sync_tracking_tables
create_sync_tracking_tables()
print('✅ Sync tracking tables created successfully')
"
```

2. **Migrate existing timestamp if available:**
```bash
# Run migration script
docker-compose exec odk_sync python migration_script.py
```

3. **Switch to new main.py:**
```bash
# Backup original
docker-compose exec odk_sync cp main.py main_original.py

# Replace with new version
docker-compose exec odk_sync cp main_with_db_sync.py main.py

# Restart service
docker-compose restart odk_sync
```

#### Option B: Fresh Start
Simply replace `main.py` with `main_with_db_sync.py` and restart - the system will perform a full sync on first run.

### Step 5: Verify Migration
```bash
# Check service logs
docker-compose logs -f odk_sync

# Verify sync status in database
docker-compose exec postgres psql -U postgres -d Submissions -c "
SELECT * FROM odk_sync_status;
SELECT COUNT(*) as history_records FROM odk_sync_history;
"

# Check sync statistics
docker-compose exec odk_sync python -c "
from utils.db_sync_manager import db_sync_manager
import json
stats = db_sync_manager.get_sync_statistics()
print(json.dumps(stats, indent=2))
"
```

## Usage Examples

### Basic Usage (Drop-in Replacement)
```python
# OLD WAY
from utils.helpers import get_last_sync_time, set_last_sync_time

last_sync = get_last_sync_time()
# ... process data ...
set_last_sync_time(latest_timestamp)

# NEW WAY (using compatibility functions)
from utils.db_helpers import get_last_sync_time, set_last_sync_time

last_sync = get_last_sync_time()  # Now reads from database
# ... process data ...
set_last_sync_time(latest_timestamp)  # Now writes to database
```

### Advanced Usage (Recommended)
```python
# Using context managers for automatic error handling
from utils.db_helpers import main_submissions_sync

with main_submissions_sync() as sync:
    # Fetch and process data
    records = fetch_main_submissions(sync_manager.get_last_sync_time())
    
    # Update progress
    sync.update_progress(
        records_processed=len(records),
        latest_timestamp=max_timestamp,
        metadata={'processing_notes': 'Custom metadata'}
    )
    
    # If exception occurs, sync automatically marked as failed
    # If successful, sync automatically marked as completed
```

### Monitoring and Statistics
```python
from utils.db_sync_manager import db_sync_manager

# Get comprehensive sync statistics
stats = db_sync_manager.get_sync_statistics()
print(f"Last successful sync: {stats['main_submissions']['last_sync_timestamp']}")
print(f"Success rate: {stats['main_submissions']['successful_syncs']} successes")

# Manual sync operations
history_id = db_sync_manager.start_sync('custom_process')
try:
    # Your processing code here
    db_sync_manager.complete_sync(history_id, 'custom_process', records_count)
except Exception as e:
    db_sync_manager.fail_sync(history_id, 'custom_process', str(e))
```

## Monitoring and Troubleshooting

### Health Check Endpoint
```python
# Add this to your monitoring system
from main_with_db_sync import get_sync_health_status

health = get_sync_health_status()
# Returns comprehensive status including:
# - Last sync times for each sync type
# - Success/failure counts
# - Recent sync history
# - Service instance information
```

### Common Queries for Monitoring
```sql
-- Check current sync status
SELECT 
    sync_type,
    last_sync_timestamp,
    last_sync_status,
    successful_sync_count,
    failed_sync_count,
    last_records_processed
FROM odk_sync_status;

-- View recent sync attempts
SELECT 
    sync_type,
    sync_timestamp,
    status,
    records_processed,
    duration_seconds,
    service_instance
FROM odk_sync_history 
ORDER BY sync_timestamp DESC 
LIMIT 10;

-- Find failed syncs
SELECT 
    sync_type,
    sync_timestamp,
    error_message,
    service_instance
FROM odk_sync_history 
WHERE status = 'error' 
ORDER BY sync_timestamp DESC;

-- Sync performance over time
SELECT 
    DATE_TRUNC('hour', sync_timestamp) as hour,
    sync_type,
    AVG(duration_seconds) as avg_duration,
    SUM(records_processed) as total_records
FROM odk_sync_history 
WHERE status = 'success'
  AND sync_timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour, sync_type 
ORDER BY hour DESC;
```

### Troubleshooting Issues

#### Issue: Tables not created
```bash
# Manually create tables
docker-compose exec odk_sync python -c "
from db.sync_tracking_models import create_sync_tracking_tables
create_sync_tracking_tables()
"
```

#### Issue: Permission errors
```bash
# Check database permissions
docker-compose exec postgres psql -U postgres -d Submissions -c "
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_user;
"
```

#### Issue: Service won't start
```bash
# Check logs for specific errors
docker-compose logs odk_sync

# Test database connection
docker-compose exec odk_sync python -c "
from db.sync_tracking_models import get_sync_tracking_engine
engine = get_sync_tracking_engine()
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('✅ Database connection successful')
"
```

## Rollback Plan

If issues occur, you can rollback:

### Quick Rollback
```bash
# Restore original main.py
docker-compose exec odk_sync cp main_original.py main.py

# Restart service
docker-compose restart odk_sync
```

### Complete Rollback
```bash
# Restore database backup
docker exec -i superset_postgres psql -U postgres Submissions < backup_before_migration.sql

# Restore last_sync.txt if needed
echo "2024-01-15T10:30:00.000000" | docker-compose exec -T odk_sync tee /app/last_sync.txt

# Use original main.py
docker-compose exec odk_sync cp main_original.py main.py
docker-compose restart odk_sync
```

## Performance Considerations

### Database Impact
- **Minimal**: Sync tracking tables are lightweight
- **Indexes**: Automatically created on frequently queried fields
- **Cleanup**: Old history records automatically cleaned up (configurable)

### Memory Usage
- **Negligible**: Additional memory usage is minimal
- **Connection Pooling**: Reuses database connections efficiently

### Monitoring Overhead
- **Optional**: Statistics gathering is optional and lightweight
- **Configurable**: History retention period is configurable

## Support and Troubleshooting

If you encounter issues during migration:

1. **Check Logs**: `docker-compose logs odk_sync`
2. **Verify Database**: Ensure PostgreSQL is accessible
3. **Test Connections**: Use the provided test scripts
4. **Rollback if Needed**: Use the rollback procedures above

The new database-based system provides much better reliability and monitoring capabilities while maintaining backward compatibility with existing code.