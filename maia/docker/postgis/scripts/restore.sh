#!/bin/bash

# Database restore script for MAIA PostGIS

# Configuration
BACKUP_DIR="/data/backups"
POSTGRES_DB="${POSTGRES_DB:-maia}"
POSTGRES_USER="${POSTGRES_USER:-maia}"

# Check if backup file is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo -e "\nAvailable backups:"
    ls -lh "${BACKUP_DIR}"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    # Try with backup directory prefix
    BACKUP_FILE="${BACKUP_DIR}/${1}"
    if [ ! -f "${BACKUP_FILE}" ]; then
        echo "Backup file not found: $1"
        echo -e "\nAvailable backups:"
        ls -lh "${BACKUP_DIR}"
        exit 1
    fi
fi

# Check if file is compressed
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo "Decompressing backup file..."
    gunzip -c "${BACKUP_FILE}" > "${BACKUP_FILE%.gz}"
    BACKUP_FILE="${BACKUP_FILE%.gz}"
fi

# Confirm restore
echo "WARNING: This will overwrite the current database!"
echo "Database: ${POSTGRES_DB}"
echo "Backup file: ${BACKUP_FILE}"
read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled"
    exit 1
fi

# Drop existing connections
echo "Dropping existing connections..."
psql -U "${POSTGRES_USER}" -d postgres -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '${POSTGRES_DB}'
    AND pid <> pg_backend_pid();"

# Drop and recreate database
echo "Recreating database..."
dropdb -U "${POSTGRES_USER}" "${POSTGRES_DB}" || true
createdb -U "${POSTGRES_USER}" "${POSTGRES_DB}"

# Restore database
echo "Restoring from backup..."
pg_restore -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "Restore completed successfully"
    
    # Clean up decompressed file if original was compressed
    if [[ "$1" == *.gz ]]; then
        rm "${BACKUP_FILE}"
    fi
else
    echo "Restore failed!"
    exit 1
fi

# Verify restore
echo -e "\nVerifying restore..."
psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "
    SELECT COUNT(*) as scanner_count FROM scanner_locations;
    SELECT COUNT(*) as readings_count FROM ble_readings;
    SELECT COUNT(*) as positions_count FROM device_positions;
    SELECT version, applied_at, description 
    FROM schema_version 
    ORDER BY version DESC 
    LIMIT 1;" 