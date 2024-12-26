#!/usr/bin/with-contenv bashio

# Start Redis server
redis-server --daemonize yes

# Wait for Redis to be ready
bashio::log.info "Waiting for Redis to start..."
while ! redis-cli ping > /dev/null 2>&1; do
    sleep 1
done
bashio::log.info "Redis is ready"

# Start MAIA
python3 -m api.main 