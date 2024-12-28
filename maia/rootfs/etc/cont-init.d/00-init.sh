#!/usr/bin/with-contenv bashio
# ==============================================================================
# Home Assistant Add-on: MAIA
# Initializes MAIA
# ==============================================================================

# Create required directories if they don't exist
for dir in /data /config /app/models; do
    if ! bashio::fs.directory_exists "${dir}"; then
        bashio::log.debug "Creating directory ${dir}"
        mkdir -p "${dir}"
    fi
done

# Check if config file exists, create default if not
if ! bashio::fs.file_exists '/config/maia.yaml'; then
    bashio::log.info "Creating default configuration..."
    cp /app/config.yaml.example /config/maia.yaml
fi

# Set permissions
bashio::log.info "Setting permissions..."
chown -R abc:abc \
    /data \
    /config \
    /app

# Initialize database if needed
if bashio::config.true 'init_db'; then
    bashio::log.info "Initializing database..."
    python3 /app/init_db.py
fi

# Check required configuration
if ! bashio::config.exists 'mqtt.broker'; then
    bashio::exit.nok "MQTT broker configuration is required!"
fi

# Verify Home Assistant connection
bashio::log.info "Verifying Home Assistant connection..."
token=$(bashio::config 'ha_token')
if ! curl -sSL -H "Authorization: Bearer ${token}" "${SUPERVISOR_URL}/_ping"; then
    bashio::exit.nok "Unable to connect to Home Assistant!"
fi

bashio::log.info "Initialization completed" 