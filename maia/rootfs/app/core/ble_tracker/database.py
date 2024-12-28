"""
Database interaction module for BLE tracking.
Handles all PostgreSQL/PostGIS operations.
"""
from typing import Dict, List, Optional, Any, Tuple
import logging
from datetime import datetime, timedelta
import asyncpg
from asyncpg import Pool
from geoalchemy2 import Geometry
from shapely.geometry import Point
import json

_LOGGER = logging.getLogger(__name__)

class BLEDatabase:
    """Database handler for BLE tracking."""
    
    def __init__(self, dsn: str):
        """Initialize database connection."""
        self.dsn = dsn
        self.pool: Optional[Pool] = None
        
    async def connect(self):
        """Create connection pool."""
        try:
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=5,
                max_size=20,
                command_timeout=60,
                server_settings={
                    'jit': 'off',  # Disable JIT for PostGIS
                    'timezone': 'UTC'
                }
            )
            _LOGGER.info("Database connection pool created")
            
        except Exception as e:
            _LOGGER.error(f"Failed to create database pool: {str(e)}")
            raise
            
    async def close(self):
        """Close all connections."""
        if self.pool:
            await self.pool.close()
            
    async def store_scanner_location(
        self,
        scanner_id: str,
        x: float,
        y: float,
        z: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store or update scanner location."""
        try:
            async with self.pool.acquire() as conn:
                # Create PostGIS point
                point = f"SRID=4326;POINT Z({x} {y} {z})"
                
                # Upsert scanner location
                await conn.execute("""
                    INSERT INTO scanner_locations (id, location, metadata)
                    VALUES ($1, ST_GeomFromEWKT($2), $3)
                    ON CONFLICT (id) DO UPDATE
                    SET location = ST_GeomFromEWKT($2),
                        metadata = $3,
                        last_seen = NOW()
                """, scanner_id, point, json.dumps(metadata or {}))
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to store scanner location: {str(e)}")
            return False
            
    async def store_ble_reading(
        self,
        scanner_id: str,
        device_mac: str,
        rssi: int,
        device_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store BLE reading."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO ble_readings 
                    (time, scanner_id, device_mac, rssi, device_name, metadata)
                    VALUES (NOW(), $1, $2, $3, $4, $5)
                """, scanner_id, device_mac, rssi, device_name, json.dumps(metadata or {}))
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to store BLE reading: {str(e)}")
            return False
            
    async def store_calibration_point(
        self,
        x: float,
        y: float,
        z: float,
        reference_device: str,
        readings: Dict[str, Any]
    ) -> bool:
        """Store calibration point with readings."""
        try:
            async with self.pool.acquire() as conn:
                # Create PostGIS point
                point = f"SRID=4326;POINT Z({x} {y} {z})"
                
                await conn.execute("""
                    INSERT INTO calibration_points 
                    (location, reference_device, readings)
                    VALUES (ST_GeomFromEWKT($1), $2, $3)
                """, point, reference_device, json.dumps(readings))
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to store calibration point: {str(e)}")
            return False
            
    async def store_device_position(
        self,
        device_mac: str,
        x: float,
        y: float,
        z: float,
        accuracy: float,
        source_readings: Dict[str, Any]
    ) -> bool:
        """Store calculated device position."""
        try:
            async with self.pool.acquire() as conn:
                # Create PostGIS point
                point = f"SRID=4326;POINT Z({x} {y} {z})"
                
                await conn.execute("""
                    INSERT INTO device_positions 
                    (time, device_mac, position, accuracy, source_readings)
                    VALUES (NOW(), $1, ST_GeomFromEWKT($2), $3, $4)
                """, device_mac, point, accuracy, json.dumps(source_readings))
                
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to store device position: {str(e)}")
            return False
            
    async def get_recent_readings(
        self,
        device_mac: str,
        minutes: int = 1
    ) -> List[Dict[str, Any]]:
        """Get recent readings for a device."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        time,
                        scanner_id,
                        rssi,
                        device_name,
                        metadata,
                        ST_AsGeoJSON(s.location) as scanner_location
                    FROM ble_readings r
                    JOIN scanner_locations s ON r.scanner_id = s.id
                    WHERE device_mac = $1
                    AND time > NOW() - $2::interval
                    ORDER BY time DESC
                """, device_mac, timedelta(minutes=minutes))
                
                return [
                    {
                        "time": row["time"],
                        "scanner_id": row["scanner_id"],
                        "rssi": row["rssi"],
                        "device_name": row["device_name"],
                        "metadata": json.loads(row["metadata"]),
                        "scanner_location": json.loads(row["scanner_location"])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get recent readings: {str(e)}")
            return []
            
    async def get_device_history(
        self,
        device_mac: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get device position history."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        time,
                        ST_AsGeoJSON(position) as position,
                        accuracy,
                        source_readings
                    FROM device_positions
                    WHERE device_mac = $1
                    AND time >= $2
                    AND ($3::timestamptz IS NULL OR time <= $3)
                    ORDER BY time ASC
                """, device_mac, start_time, end_time)
                
                return [
                    {
                        "time": row["time"],
                        "position": json.loads(row["position"]),
                        "accuracy": row["accuracy"],
                        "source_readings": json.loads(row["source_readings"])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get device history: {str(e)}")
            return []
            
    async def get_calibration_points(
        self,
        reference_device: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get calibration points."""
        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT 
                        id,
                        ST_AsGeoJSON(location) as location,
                        reference_device,
                        measured_at,
                        readings
                    FROM calibration_points
                """
                
                if reference_device:
                    query += " WHERE reference_device = $1"
                    rows = await conn.fetch(query, reference_device)
                else:
                    rows = await conn.fetch(query)
                
                return [
                    {
                        "id": row["id"],
                        "location": json.loads(row["location"]),
                        "reference_device": row["reference_device"],
                        "measured_at": row["measured_at"],
                        "readings": json.loads(row["readings"])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get calibration points: {str(e)}")
            return []
            
    async def get_active_scanners(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """Get recently active scanners."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        id,
                        ST_AsGeoJSON(location) as location,
                        installed_at,
                        last_seen,
                        metadata
                    FROM scanner_locations
                    WHERE last_seen > NOW() - $1::interval
                    ORDER BY last_seen DESC
                """, timedelta(minutes=minutes))
                
                return [
                    {
                        "id": row["id"],
                        "location": json.loads(row["location"]),
                        "installed_at": row["installed_at"],
                        "last_seen": row["last_seen"],
                        "metadata": json.loads(row["metadata"])
                    }
                    for row in rows
                ]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get active scanners: {str(e)}")
            return [] 