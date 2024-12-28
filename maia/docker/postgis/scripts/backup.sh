#!/bin/bash

# Database backup script for MAIA PostGIS

# Configuration
BACKUP_DIR="/data/backups"
POSTGRES_DB="${POSTGRES_DB:-maia}"
POSTGRES_USER="${POSTGRES_USER:-maia}"
BACKUP_RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${POSTGRES_DB}_${DATE}.backup"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Create backup
echo "Creating backup of ${POSTGRES_DB} database..."
pg_dump -Fc \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -f "${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    echo "Backup created successfully: ${BACKUP_FILE}"
    
    # Compress backup
    echo "Compressing backup..."
    gzip "${BACKUP_FILE}"
    
    # Clean up old backups
    echo "Cleaning up old backups..."
    find "${BACKUP_DIR}" -name "*.backup.gz" -mtime +${BACKUP_RETENTION_DAYS} -delete
    
    echo "Backup process completed"
else
    echo "Backup failed!"
    exit 1
fi

# List current backups
echo -e "\nCurrent backups:"
ls -lh "${BACKUP_DIR}" 