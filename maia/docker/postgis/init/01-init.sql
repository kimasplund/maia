-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create scanner locations table
CREATE TABLE scanner_locations (
    id TEXT PRIMARY KEY,
    location geometry(POINTZ, 4326),
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    metadata JSONB
);

-- Create BLE readings table
CREATE TABLE ble_readings (
    time TIMESTAMPTZ NOT NULL,
    scanner_id TEXT REFERENCES scanner_locations(id),
    device_mac TEXT NOT NULL,
    rssi INTEGER NOT NULL,
    device_name TEXT,
    metadata JSONB
);

-- Create hypertable for BLE readings with 1 day chunks
SELECT create_hypertable('ble_readings', 'time', 
    chunk_time_interval => INTERVAL '1 day');

-- Create index for device lookups
CREATE INDEX idx_ble_readings_device 
    ON ble_readings(device_mac, time DESC);

-- Create calibration points table
CREATE TABLE calibration_points (
    id SERIAL PRIMARY KEY,
    location geometry(POINTZ, 4326),
    reference_device TEXT,
    measured_at TIMESTAMPTZ DEFAULT NOW(),
    readings JSONB
);

-- Create device positions table
CREATE TABLE device_positions (
    time TIMESTAMPTZ NOT NULL,
    device_mac TEXT NOT NULL,
    position geometry(POINTZ, 4326),
    accuracy FLOAT,
    source_readings JSONB
);

-- Create hypertable for device positions with 1 hour chunks
SELECT create_hypertable('device_positions', 'time',
    chunk_time_interval => INTERVAL '1 hour');

-- Create geofence zones table
CREATE TABLE geofence_zones (
    zone_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    polygon geometry(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Create geofence events table
CREATE TABLE geofence_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    zone_id TEXT REFERENCES geofence_zones(zone_id),
    device_mac TEXT NOT NULL,
    position geometry(POINT, 4326) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Create hypertable for geofence events with 1 hour chunks
SELECT create_hypertable('geofence_events', 'timestamp',
    chunk_time_interval => INTERVAL '1 hour');

-- Create spatial indexes
CREATE INDEX idx_scanner_locations_geom 
    ON scanner_locations USING GIST (location);
CREATE INDEX idx_calibration_points_geom 
    ON calibration_points USING GIST (location);
CREATE INDEX idx_device_positions_geom 
    ON device_positions USING GIST (position);
CREATE INDEX idx_geofence_zones_geom
    ON geofence_zones USING GIST (polygon);
CREATE INDEX idx_geofence_events_geom
    ON geofence_events USING GIST (position);

-- Create index for recent positions
CREATE INDEX idx_device_positions_recent
    ON device_positions(device_mac, time DESC);

-- Create index for recent events
CREATE INDEX idx_geofence_events_recent
    ON geofence_events(device_mac, timestamp DESC);

-- Create views for common queries
CREATE VIEW active_scanners AS
SELECT 
    id,
    ST_AsGeoJSON(location)::jsonb as location,
    installed_at,
    last_seen,
    metadata,
    NOW() - last_seen as last_seen_age
FROM scanner_locations
WHERE last_seen > NOW() - INTERVAL '5 minutes'
ORDER BY last_seen DESC;

CREATE VIEW recent_device_positions AS
SELECT DISTINCT ON (device_mac)
    time,
    device_mac,
    ST_AsGeoJSON(position)::jsonb as position,
    accuracy,
    source_readings
FROM device_positions
WHERE time > NOW() - INTERVAL '5 minutes'
ORDER BY device_mac, time DESC;

CREATE VIEW active_zone_devices AS
SELECT DISTINCT
    z.zone_id,
    z.name as zone_name,
    dp.device_mac,
    dp.time as last_seen,
    ST_AsGeoJSON(dp.position)::jsonb as position
FROM geofence_zones z
JOIN device_positions dp ON ST_Contains(z.polygon, dp.position)
WHERE dp.time > NOW() - INTERVAL '5 minutes'
ORDER BY z.zone_id, dp.device_mac;

-- Create functions for common operations
CREATE OR REPLACE FUNCTION update_scanner_location(
    _id TEXT,
    _x FLOAT,
    _y FLOAT,
    _z FLOAT,
    _metadata JSONB DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    INSERT INTO scanner_locations (id, location, metadata, last_seen)
    VALUES (
        _id,
        ST_SetSRID(ST_MakePoint(_x, _y, _z), 4326),
        COALESCE(_metadata, '{}'::jsonb),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE
    SET location = ST_SetSRID(ST_MakePoint(_x, _y, _z), 4326),
        metadata = COALESCE(_metadata, scanner_locations.metadata),
        last_seen = NOW();
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_device_history(
    _device_mac TEXT,
    _start_time TIMESTAMPTZ,
    _end_time TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
    time TIMESTAMPTZ,
    position JSONB,
    accuracy FLOAT,
    source_readings JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        dp.time,
        ST_AsGeoJSON(dp.position)::jsonb,
        dp.accuracy,
        dp.source_readings
    FROM device_positions dp
    WHERE dp.device_mac = _device_mac
    AND dp.time >= _start_time
    AND (_end_time IS NULL OR dp.time <= _end_time)
    ORDER BY dp.time ASC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_zone_history(
    _zone_id TEXT,
    _start_time TIMESTAMPTZ,
    _end_time TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
    event_type TEXT,
    device_mac TEXT,
    timestamp TIMESTAMPTZ,
    position JSONB,
    metadata JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ge.event_type,
        ge.device_mac,
        ge.timestamp,
        ST_AsGeoJSON(ge.position)::jsonb,
        ge.metadata
    FROM geofence_events ge
    WHERE ge.zone_id = _zone_id
    AND ge.timestamp >= _start_time
    AND (_end_time IS NULL OR ge.timestamp <= _end_time)
    ORDER BY ge.timestamp ASC;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_device_zones(
    _device_mac TEXT
) RETURNS TABLE (
    zone_id TEXT,
    zone_name TEXT,
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    total_time INTERVAL,
    visit_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH zone_visits AS (
        SELECT 
            ge.zone_id,
            gz.name as zone_name,
            MIN(ge.timestamp) as first_seen,
            MAX(ge.timestamp) as last_seen,
            COUNT(DISTINCT (
                CASE 
                    WHEN ge.event_type = 'enter' 
                    THEN date_trunc('hour', ge.timestamp)
                    ELSE NULL 
                END
            )) as visit_count
        FROM geofence_events ge
        JOIN geofence_zones gz ON ge.zone_id = gz.zone_id
        WHERE ge.device_mac = _device_mac
        GROUP BY ge.zone_id, gz.name
    )
    SELECT 
        zv.zone_id,
        zv.zone_name,
        zv.first_seen,
        zv.last_seen,
        zv.last_seen - zv.first_seen as total_time,
        zv.visit_count
    FROM zone_visits zv
    ORDER BY zv.last_seen DESC;
END;
$$ LANGUAGE plpgsql; 