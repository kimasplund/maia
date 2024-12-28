FROM nvcr.io/nvidia/pytorch:24.01-py3

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python packages not included in NGC container
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Create app directory
WORKDIR /app

# Copy application code
COPY . /app/

# Set up entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"] 