-- Create schema version table
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    description TEXT
);

-- Insert initial version
INSERT INTO schema_version (version, description)
VALUES (1, 'Initial schema with PostGIS and TimescaleDB setup');

-- Function to check and update schema version
CREATE OR REPLACE FUNCTION check_schema_version(
    required_version INTEGER
) RETURNS BOOLEAN AS $$
DECLARE
    current_version INTEGER;
BEGIN
    -- Get current version
    SELECT MAX(version) INTO current_version
    FROM schema_version;
    
    -- Return version check result
    RETURN COALESCE(current_version >= required_version, FALSE);
END;
$$ LANGUAGE plpgsql;

-- Function to update schema version
CREATE OR REPLACE FUNCTION update_schema_version(
    new_version INTEGER,
    version_description TEXT
) RETURNS VOID AS $$
BEGIN
    INSERT INTO schema_version (version, description)
    VALUES (new_version, version_description);
END;
$$ LANGUAGE plpgsql;

-- Example migration (can be uncommented and modified for future updates):
/*
DO $$ 
BEGIN
    -- Check if migration is needed
    IF NOT check_schema_version(2) THEN
        -- Add new columns/tables here
        ALTER TABLE device_positions
        ADD COLUMN IF NOT EXISTS confidence FLOAT;
        
        -- Update schema version
        PERFORM update_schema_version(2, 'Added confidence score to positions');
    END IF;
END $$;
*/

-- Create maintenance functions
CREATE OR REPLACE FUNCTION cleanup_old_readings(
    retention_days INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    -- Delete old BLE readings
    DELETE FROM ble_readings
    WHERE time < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_positions(
    retention_days INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    -- Delete old device positions
    DELETE FROM device_positions
    WHERE time < NOW() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    RETURN rows_deleted;
END;
$$ LANGUAGE plpgsql;

-- Create maintenance trigger
CREATE OR REPLACE FUNCTION trigger_cleanup_old_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Run cleanup if too much data accumulated
    IF (
        SELECT count(*) FROM ble_readings
        WHERE time < NOW() - INTERVAL '30 days'
    ) > 1000000 THEN
        PERFORM cleanup_old_readings(30);
    END IF;
    
    IF (
        SELECT count(*) FROM device_positions
        WHERE time < NOW() - INTERVAL '30 days'
    ) > 100000 THEN
        PERFORM cleanup_old_positions(30);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER cleanup_old_data_trigger
    AFTER INSERT ON ble_readings
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_cleanup_old_data(); 