#!/bin/bash
set -e

# Wait for Valkey replica to be ready
until curl -s "${VALKEY_URL}/health" > /dev/null; do
    echo "Waiting for Valkey replica..."
    sleep 5
done

# Wait for PostGIS replica to be ready
until pg_isready -h postgis-replica -U "${POSTGRES_USER}"; do
    echo "Waiting for PostGIS replica..."
    sleep 5
done

# Initialize CUDA and TensorRT
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python3 -c "import torch_tensorrt; print('TensorRT initialized')"

# Start the application
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 