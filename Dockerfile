FROM apache/superset:latest

USER root

# Install postgresql-client for pg_isready command and psycopg2-binary for PostgreSQL connections
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    postgresql-client \
    && pip install psycopg2-binary \
    && rm -rf /var/lib/apt/lists/*

USER superset

