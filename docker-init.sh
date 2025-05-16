#!/bin/bash
set -e

# Initialize the database
superset db upgrade

# Create admin user
superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME}" \
    --firstname Admin \
    --lastname User \
    --email "${SUPERSET_ADMIN_EMAIL}" \
    --password "${SUPERSET_ADMIN_PASSWORD}"

# Initialize
superset init

# Create default roles and permissions
superset set-database-uri -d examples -u sqlite:////app/superset_home/superset.db

echo "Superset has been initialized successfully!"

