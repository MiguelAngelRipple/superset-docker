#!/bin/bash
set -e

# Setup environment
export PYTHONPATH="${PYTHONPATH}:/app/pythonpath"
export FLASK_APP="superset"

# Connection string for PostgreSQL
DB_CONNECTION_STRING="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@${DATABASE_HOST}:${DATABASE_PORT}/${DATABASE_DB}"
echo "Database connection string: $DB_CONNECTION_STRING"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
  pg_isready -h "${DATABASE_HOST}" -p "${DATABASE_PORT}" -U "${DATABASE_USER}" && echo "PostgreSQL is ready!" && break
  echo "Waiting for PostgreSQL... ($i/30)"
  sleep 2
  if [ $i -eq 30 ]; then
    echo "Error: PostgreSQL did not become ready in time."
    exit 1
  fi
done

# Start Superset with Gunicorn
echo "Starting Superset with Gunicorn..."
echo "FLASK_APP: $FLASK_APP"
echo "PYTHONPATH: $PYTHONPATH"
echo "Superset port: $SUPERSET_PORT"

# Start Gunicorn with error handling
if ! gunicorn \
    --bind "0.0.0.0:8088" \
    --workers 4 \
    --timeout 120 \
    --limit-request-line 0 \
    --limit-request-field_size 0 \
    --log-level=info \
    "superset.app:create_app()"; then
    echo "Error: Failed to start Gunicorn server."
    exit 1
fi

