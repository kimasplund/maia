"""
PostGIS database handler for MAIA.
Handles spatial data storage and queries.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import asyncpg
from asyncpg import Pool
from dataclasses import dataclass
from geoalchemy2 import Geometry
from shapely.geometry import Point, Polygon
import json
from ..core.positioning import PositionEstimator, RSSIReading, DevicePosition

_LOGGER = logging.getLogger(__name__)

@dataclass
class SpatialPoint:
    """Spatial point with metadata."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class PostGISHandler:
    """PostGIS database handler with connection pooling."""
    
    def __init__(
        self,
        host: str = "postgis",
        port: int = 5432,
        database: str = "maia",
        user: str = "maia",
        password: str = None,
        min_size: int = 2,
        max_size: int = 10
    ):
        """Initialize PostGIS handler."""
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[Pool] = None
        self.position_estimator = PositionEstimator()
        
    async def start(self):
        """Start database connection pool."""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=60
            )
            
            # Initialize PostGIS extension
            async with self.pool.acquire() as conn:
                await conn.execute('CREATE EXTENSION IF NOT EXISTS postgis')
                await conn.execute('CREATE EXTENSION IF NOT EXISTS postgis_topology')
                
            # Create tables
            await self._create_tables()
            
            _LOGGER.info("PostGIS handler started successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start PostGIS handler: {str(e)}")
            raise
            
    async def stop(self):
        """Stop database connection pool."""
        if self.pool:
            await self.pool.close()
            
    async def _create_tables(self):
        """Create necessary database tables."""
        async with self.pool.acquire() as conn:
            # Create scanner locations table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS scanner_locations (
                    id SERIAL PRIMARY KEY,
                    scanner_id VARCHAR(50) UNIQUE NOT NULL,
                    location GEOMETRY(POINT, 4326) NOT NULL,
                    altitude FLOAT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            ''')
            
            # Create BLE readings table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS ble_readings (
                    id SERIAL PRIMARY KEY,
                    scanner_id VARCHAR(50) REFERENCES scanner_locations(scanner_id),
                    device_mac VARCHAR(17) NOT NULL,
                    rssi INTEGER NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            ''')
            
            # Create device positions table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS device_positions (
                    id SERIAL PRIMARY KEY,
                    device_mac VARCHAR(17) NOT NULL,
                    position GEOMETRY(POINT, 4326) NOT NULL,
                    accuracy FLOAT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            ''')
            
            # Create calibration points table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS calibration_points (
                    id SERIAL PRIMARY KEY,
                    location GEOMETRY(POINT, 4326) NOT NULL,
                    rssi_value INTEGER NOT NULL,
                    distance FLOAT NOT NULL,
                    device_mac VARCHAR(17) NOT NULL,
                    scanner_id VARCHAR(50) REFERENCES scanner_locations(scanner_id),
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB
                )
            ''')
            
            # Create spatial indexes
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_scanner_locations_geom 
                ON scanner_locations USING GIST (location)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_device_positions_geom 
                ON device_positions USING GIST (position)
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_calibration_points_geom 
                ON calibration_points USING GIST (location)
            ''')
            
    async def add_scanner_location(
        self,
        scanner_id: str,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add or update scanner location."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO scanner_locations 
                    (scanner_id, location, altitude, metadata)
                    VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5)
                    ON CONFLICT (scanner_id) 
                    DO UPDATE SET 
                        location = ST_SetSRID(ST_MakePoint($2, $3), 4326),
                        altitude = $4,
                        metadata = $5,
                        updated_at = CURRENT_TIMESTAMP
                ''', scanner_id, longitude, latitude, altitude, json.dumps(metadata) if metadata else None)
                return True
        except Exception as e:
            _LOGGER.error(f"Failed to add scanner location: {str(e)}")
            return False
            
    async def add_ble_reading(
        self,
        scanner_id: str,
        device_mac: str,
        rssi: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add BLE reading."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO ble_readings 
                    (scanner_id, device_mac, rssi, metadata)
                    VALUES ($1, $2, $3, $4)
                ''', scanner_id, device_mac, rssi, json.dumps(metadata) if metadata else None)
                return True
        except Exception as e:
            _LOGGER.error(f"Failed to add BLE reading: {str(e)}")
            return False
            
    async def update_device_position(
        self,
        device_mac: str,
        latitude: float,
        longitude: float,
        accuracy: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update device position."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO device_positions 
                    (device_mac, position, accuracy, metadata)
                    VALUES ($1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $4, $5)
                ''', device_mac, longitude, latitude, accuracy, json.dumps(metadata) if metadata else None)
                return True
        except Exception as e:
            _LOGGER.error(f"Failed to update device position: {str(e)}")
            return False
            
    async def add_calibration_point(
        self,
        scanner_id: str,
        device_mac: str,
        latitude: float,
        longitude: float,
        rssi: int,
        distance: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add calibration point."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO calibration_points 
                    (scanner_id, device_mac, location, rssi_value, distance, metadata)
                    VALUES ($1, $2, ST_SetSRID(ST_MakePoint($3, $4), 4326), $5, $6, $7)
                ''', scanner_id, device_mac, longitude, latitude, rssi, distance, 
                    json.dumps(metadata) if metadata else None)
                return True
        except Exception as e:
            _LOGGER.error(f"Failed to add calibration point: {str(e)}")
            return False
            
    async def get_nearby_scanners(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 100
    ) -> List[Dict[str, Any]]:
        """Get scanners within radius."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT 
                        scanner_id,
                        ST_X(location::geometry) as longitude,
                        ST_Y(location::geometry) as latitude,
                        altitude,
                        metadata,
                        ST_Distance(
                            location::geometry,
                            ST_SetSRID(ST_MakePoint($1, $2), 4326)::geometry
                        ) as distance
                    FROM scanner_locations
                    WHERE ST_DWithin(
                        location::geometry,
                        ST_SetSRID(ST_MakePoint($1, $2), 4326)::geometry,
                        $3
                    )
                    ORDER BY distance
                ''', longitude, latitude, radius_meters)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get nearby scanners: {str(e)}")
            return []
            
    async def get_device_history(
        self,
        device_mac: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get device position history."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT 
                        ST_X(position::geometry) as longitude,
                        ST_Y(position::geometry) as latitude,
                        accuracy,
                        timestamp,
                        metadata
                    FROM device_positions
                    WHERE device_mac = $1
                    ORDER BY timestamp DESC
                    LIMIT $2
                ''', device_mac, limit)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get device history: {str(e)}")
            return []
            
    async def get_calibration_data(
        self,
        scanner_id: Optional[str] = None,
        device_mac: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get calibration data for scanner or device."""
        try:
            async with self.pool.acquire() as conn:
                query = '''
                    SELECT 
                        scanner_id,
                        device_mac,
                        ST_X(location::geometry) as longitude,
                        ST_Y(location::geometry) as latitude,
                        rssi_value,
                        distance,
                        timestamp,
                        metadata
                    FROM calibration_points
                    WHERE 1=1
                '''
                params = []
                
                if scanner_id:
                    query += " AND scanner_id = $1"
                    params.append(scanner_id)
                if device_mac:
                    query += f" AND device_mac = ${len(params) + 1}"
                    params.append(device_mac)
                    
                query += " ORDER BY timestamp DESC"
                
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get calibration data: {str(e)}")
            return []
            
    async def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data."""
        try:
            async with self.pool.acquire() as conn:
                # Delete old BLE readings
                await conn.execute('''
                    DELETE FROM ble_readings
                    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
                ''', days)
                
                # Delete old device positions
                await conn.execute('''
                    DELETE FROM device_positions
                    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '1 day' * $1
                ''', days)
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to cleanup old data: {str(e)}")
            return False 
            
    async def estimate_device_position(
        self,
        device_mac: str,
        time_window: float = 10.0  # seconds
    ) -> Optional[DevicePosition]:
        """Estimate device position from recent readings."""
        try:
            async with self.pool.acquire() as conn:
                # Get recent BLE readings
                rows = await conn.fetch('''
                    WITH recent_readings AS (
                        SELECT 
                            r.scanner_id,
                            r.rssi,
                            r.timestamp,
                            s.location,
                            s.altitude
                        FROM ble_readings r
                        JOIN scanner_locations s ON r.scanner_id = s.scanner_id
                        WHERE r.device_mac = $1
                        AND r.timestamp > CURRENT_TIMESTAMP - interval '1 second' * $2
                        ORDER BY r.timestamp DESC
                    )
                    SELECT DISTINCT ON (scanner_id)
                        scanner_id,
                        rssi,
                        ST_X(location::geometry) as longitude,
                        ST_Y(location::geometry) as latitude,
                        altitude,
                        EXTRACT(EPOCH FROM timestamp) as timestamp
                    FROM recent_readings
                ''', device_mac, time_window)
                
                if not rows:
                    return None
                    
                # Convert to RSSI readings
                readings = [
                    RSSIReading(
                        scanner_id=row['scanner_id'],
                        rssi=row['rssi'],
                        latitude=row['latitude'],
                        longitude=row['longitude'],
                        altitude=row['altitude'],
                        timestamp=row['timestamp']
                    )
                    for row in rows
                ]
                
                # Get last known position
                last_pos = await conn.fetchrow('''
                    SELECT 
                        ST_Y(position::geometry) as latitude,
                        ST_X(position::geometry) as longitude,
                        accuracy
                    FROM device_positions
                    WHERE device_mac = $1
                    ORDER BY timestamp DESC
                    LIMIT 1
                ''', device_mac)
                
                last_position = None
                if last_pos:
                    last_position = DevicePosition(
                        latitude=last_pos['latitude'],
                        longitude=last_pos['longitude'],
                        accuracy=last_pos['accuracy']
                    )
                    
                # Estimate position
                position = self.position_estimator.estimate_position(
                    readings,
                    last_position
                )
                
                if position:
                    # Store estimated position
                    await self.update_device_position(
                        device_mac=device_mac,
                        latitude=position.latitude,
                        longitude=position.longitude,
                        accuracy=position.accuracy,
                        metadata={
                            "confidence": position.confidence,
                            "num_readings": len(readings)
                        }
                    )
                    
                return position
                
        except Exception as e:
            _LOGGER.error(f"Failed to estimate device position: {str(e)}")
            return None
            
    async def calibrate_position_estimator(
        self,
        scanner_id: Optional[str] = None,
        device_mac: Optional[str] = None,
        min_points: int = 10
    ) -> bool:
        """Calibrate position estimator using stored calibration data."""
        try:
            # Get calibration data
            calibration_data = await self.get_calibration_data(
                scanner_id=scanner_id,
                device_mac=device_mac
            )
            
            if len(calibration_data) < min_points:
                _LOGGER.warning(
                    f"Insufficient calibration data: {len(calibration_data)} points"
                )
                return False
                
            # Calibrate estimator
            return self.position_estimator.calibrate(calibration_data)
            
        except Exception as e:
            _LOGGER.error(f"Failed to calibrate position estimator: {str(e)}")
            return False
            
    async def get_device_coverage(
        self,
        device_mac: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get device coverage statistics."""
        try:
            async with self.pool.acquire() as conn:
                # Build query conditions
                conditions = ["device_mac = $1"]
                params = [device_mac]
                param_idx = 2
                
                if start_time:
                    conditions.append(f"timestamp >= ${param_idx}")
                    params.append(start_time)
                    param_idx += 1
                    
                if end_time:
                    conditions.append(f"timestamp <= ${param_idx}")
                    params.append(end_time)
                    
                where_clause = " AND ".join(conditions)
                
                # Get coverage statistics
                stats = await conn.fetchrow(f'''
                    WITH stats AS (
                        SELECT 
                            COUNT(DISTINCT scanner_id) as num_scanners,
                            COUNT(*) as num_readings,
                            AVG(rssi) as avg_rssi,
                            MIN(rssi) as min_rssi,
                            MAX(rssi) as max_rssi,
                            MIN(timestamp) as first_seen,
                            MAX(timestamp) as last_seen
                        FROM ble_readings
                        WHERE {where_clause}
                    ),
                    positions AS (
                        SELECT 
                            COUNT(*) as num_positions,
                            AVG(accuracy) as avg_accuracy,
                            MIN(accuracy) as min_accuracy,
                            MAX(accuracy) as max_accuracy
                        FROM device_positions
                        WHERE {where_clause}
                    )
                    SELECT * FROM stats, positions
                ''', *params)
                
                if not stats:
                    return {}
                    
                return dict(stats)
                
        except Exception as e:
            _LOGGER.error(f"Failed to get device coverage: {str(e)}")
            return {} 