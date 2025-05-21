# Superset Docker with ODK Sync

This repository contains a Docker-based deployment of Apache Superset with an integrated ODK (Open Data Kit) synchronization service. The setup allows you to visualize data from ODK forms in Superset dashboards.

## Overview

The project consists of the following components:

- **Apache Superset**: A modern data exploration and visualization platform
- **PostgreSQL**: Database for storing both Superset metadata and ODK submissions
- **Redis**: For caching and Celery task queue
- **ODK Sync Service**: A Python service that periodically synchronizes data from ODK Central to PostgreSQL

## Quick Start Guide

Follow these steps to get the system up and running quickly:

1. **Clone the repository**
2. **Configure the environment files**
3. **Start the Docker containers**
4. **Access Superset and create dashboards**

Detailed instructions for each step are provided below.

## Prerequisites

- Docker and Docker Compose installed on your system
- Git (optional, for cloning the repository)
- Basic knowledge of Docker, PostgreSQL, and Superset

## Installation

### 1. Clone or download this repository

```bash
git clone <repository-url>
cd superset-docker
```

### 2. Configure environment variables

Copy the example environment file and modify it according to your needs:

```bash
cp .env.example .env
```

Edit the `.env` file to set your credentials and configuration options:

```
# Superset admin credentials
SUPERSET_ADMIN_USERNAME=admin
SUPERSET_ADMIN_PASSWORD=admin123
SUPERSET_ADMIN_EMAIL=admin@superset.com

# PostgreSQL credentials
POSTGRES_DB=Submissions
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_INTERNAL_PORT=5432

# Variables for okd_sync
PG_DB=Submissions
PG_USER=postgres
PG_PASS=postgres
PG_HOST=postgres
PG_PORT=5432

# Superset secret key
SUPERSET_SECRET_KEY=supersecretkey123456789

# Superset configuration
SUPERSET_PORT=8088
PYTHONPATH=/app/pythonpath
FLASK_APP=superset

# Redis (for caching and Celery)
REDIS_HOST=redis
REDIS_PORT=6380
```

### 3. Configure ODK Sync

Create and configure the environment file for the ODK sync service:

```bash
cp okd_sync/.env.example okd_sync/.env
```

Edit the `okd_sync/.env` file with your ODK Central credentials:

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

**Important**: Make sure the PostgreSQL port configuration is consistent between both `.env` files.

### 4. Start the services

Before starting the services, make sure no other PostgreSQL instances are running on your system that might conflict with the Docker container:

```bash
# Check for running PostgreSQL instances
ps aux | grep postgres

# If needed, stop the local PostgreSQL service
sudo service postgresql stop
```

Now start the Docker containers:

```bash
docker-compose up -d
```

This command will:
- Build the necessary Docker images
- Create and start all containers
- Initialize Superset (create admin user, setup database)
- Start the ODK sync service

## Usage

### Accessing Superset

Once the services are up and running, you can access the Superset web interface at:

```
http://localhost:8088
```

Log in with the admin credentials you set in the `.env` file (default: admin/admin123).

### Verifying Data Synchronization

To verify that data is being synchronized from ODK Central to PostgreSQL:

```bash
# Check the logs of the ODK sync service
docker-compose logs -f okd_sync

# Connect to the PostgreSQL database and check the tables
docker exec -it superset_postgres psql -U postgres -d Submissions -c "\dt"
```

## Connecting to the Submissions Database

1. In Superset, go to **Data** > **Databases** > **+ Database**
2. Use the following connection parameters:
   - **Host**: `postgres`
   - **Port**: `5432`
   - **Database Name**: `Submissions`
   - **Username**: `postgres`
   - **Password**: `postgres`
   - **Display Name**: `SubmissionsDB` (or any name you prefer)
   - **SSL**: Off

Alternatively, you can use the SQLAlchemy URI:
```
postgresql://postgres:postgres@postgres:5432/Submissions
```

## Creating Dashboards

1. **Connect to the PostgreSQL Database**:
   - Go to Data > Databases
   - Click + Database
   - Select PostgreSQL
   - Enter the connection details:
     - Host: `postgres` (use the container name, not localhost)
     - Port: `5432`
     - Database Name: `Submissions`
     - Username: `postgres`
     - Password: `postgres` (or whatever you set in your .env file)
   - Click Test Connection to verify
   - Click Connect

## Troubleshooting

### Database Connection Issues

If you encounter connection issues between Superset and PostgreSQL:

1. Ensure all containers are running:
   ```bash
   docker-compose ps
   ```

2. Check the logs for any errors:
   ```bash
   docker-compose logs superset_app
   docker-compose logs postgres
   ```

3. Verify that the PostgreSQL container is accessible from the Superset container:
   ```bash
   docker exec -it superset_app bash -c "ping postgres"
   ```

### ODK Sync Issues

If data is not being synchronized from ODK Central:

1. Check the ODK sync service logs:
   ```bash
   docker-compose logs okd_sync
   ```

2. Verify your ODK Central credentials and URL in the `okd_sync/.env` file

3. Manually trigger a sync to test:
   ```bash
   docker-compose run --rm okd_sync python main.py
   ```

## Maintenance

### Updating Superset

To update to a newer version of Superset:

1. Update the version in the Dockerfile
2. Rebuild and restart the containers:
   ```bash
   docker-compose down
   docker-compose build --no-cache superset
   docker-compose up -d
   ```

### Backing Up Data

To back up the PostgreSQL database:

```bash
docker exec -t superset_postgres pg_dump -U postgres Submissions > submissions_backup.sql
```

## Additional Information

For more details about the ODK sync service, see the [okd_sync/README.md](okd_sync/README.md) file.

For more information about Apache Superset, visit the [official documentation](https://superset.apache.org/docs/intro).
