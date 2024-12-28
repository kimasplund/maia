"""
Geofencing module for MAIA.
Handles spatial events and triggers based on device positions.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime
import json
from dataclasses import dataclass
from shapely.geometry import Point, Polygon, mapping, shape
from .postgis_handler import PostGISHandler, SpatialPoint

_LOGGER = logging.getLogger(__name__)

@dataclass
class GeofenceZone:
    """Geofence zone definition."""
    zone_id: str
    polygon: Polygon
    name: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
@dataclass
class GeofenceEvent:
    """Geofence event."""
    event_type: str  # 'enter', 'exit', 'dwell'
    zone_id: str
    device_mac: str
    timestamp: datetime
    position: SpatialPoint
    metadata: Optional[Dict[str, Any]] = None

class GeofenceHandler:
    """Handler for geofencing operations."""
    
    def __init__(self, postgis: PostGISHandler):
        """Initialize geofence handler."""
        self.postgis = postgis
        self.event_callbacks: List[Callable[[GeofenceEvent], None]] = []
        self._monitoring_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start geofence monitoring."""
        try:
            # Create geofence tables
            async with self.postgis.pool.acquire() as conn:
                # Create zones table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS geofence_zones (
                        zone_id VARCHAR(50) PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        description TEXT,
                        polygon GEOMETRY(POLYGON, 4326) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                ''')
                
                # Create events table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS geofence_events (
                        id SERIAL PRIMARY KEY,
                        event_type VARCHAR(20) NOT NULL,
                        zone_id VARCHAR(50) REFERENCES geofence_zones(zone_id),
                        device_mac VARCHAR(17) NOT NULL,
                        position GEOMETRY(POINT, 4326) NOT NULL,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    )
                ''')
                
                # Create spatial index on zones
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_geofence_zones_geom 
                    ON geofence_zones USING GIST (polygon)
                ''')
                
                # Create index for recent events
                await conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_geofence_events_recent
                    ON geofence_events(device_mac, timestamp DESC)
                ''')
                
            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitor_positions())
            _LOGGER.info("Geofence monitoring started")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start geofence handler: {str(e)}")
            raise
            
    async def stop(self):
        """Stop geofence monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
                
    def add_event_callback(self, callback: Callable[[GeofenceEvent], None]):
        """Add callback for geofence events."""
        self.event_callbacks.append(callback)
        
    async def create_zone(
        self,
        zone_id: str,
        name: str,
        coordinates: List[Tuple[float, float]],
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create or update geofence zone."""
        try:
            # Create polygon from coordinates
            polygon = Polygon(coordinates)
            if not polygon.is_valid:
                _LOGGER.error(f"Invalid polygon coordinates for zone {zone_id}")
                return False
                
            async with self.postgis.pool.acquire() as conn:
                # Convert polygon to PostGIS format
                points_str = ", ".join(f"{x} {y}" for x, y in coordinates)
                polygon_str = f"SRID=4326;POLYGON(({points_str}))"
                
                await conn.execute('''
                    INSERT INTO geofence_zones 
                    (zone_id, name, description, polygon, metadata)
                    VALUES ($1, $2, $3, ST_GeomFromEWKT($4), $5)
                    ON CONFLICT (zone_id) 
                    DO UPDATE SET 
                        name = $2,
                        description = $3,
                        polygon = ST_GeomFromEWKT($4),
                        metadata = $5
                ''', zone_id, name, description, polygon_str, 
                    json.dumps(metadata) if metadata else None)
                    
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to create geofence zone: {str(e)}")
            return False
            
    async def delete_zone(self, zone_id: str) -> bool:
        """Delete geofence zone."""
        try:
            async with self.postgis.pool.acquire() as conn:
                await conn.execute('''
                    DELETE FROM geofence_zones
                    WHERE zone_id = $1
                ''', zone_id)
                return True
                
        except Exception as e:
            _LOGGER.error(f"Failed to delete geofence zone: {str(e)}")
            return False
            
    async def get_zones(self) -> List[GeofenceZone]:
        """Get all geofence zones."""
        try:
            async with self.postgis.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT 
                        zone_id,
                        name,
                        description,
                        ST_AsGeoJSON(polygon)::jsonb as polygon,
                        metadata
                    FROM geofence_zones
                ''')
                
                zones = []
                for row in rows:
                    try:
                        # Convert GeoJSON to shapely polygon
                        polygon = shape(row['polygon'])
                        zones.append(GeofenceZone(
                            zone_id=row['zone_id'],
                            name=row['name'],
                            description=row['description'],
                            polygon=polygon,
                            metadata=row['metadata']
                        ))
                    except Exception as e:
                        _LOGGER.error(f"Failed to parse zone {row['zone_id']}: {str(e)}")
                        continue
                        
                return zones
                
        except Exception as e:
            _LOGGER.error(f"Failed to get geofence zones: {str(e)}")
            return []
            
    async def get_device_zones(
        self,
        device_mac: str
    ) -> List[str]:
        """Get zones that device is currently in."""
        try:
            async with self.postgis.pool.acquire() as conn:
                rows = await conn.fetch('''
                    WITH device_pos AS (
                        SELECT position
                        FROM device_positions
                        WHERE device_mac = $1
                        ORDER BY time DESC
                        LIMIT 1
                    )
                    SELECT zone_id
                    FROM geofence_zones, device_pos
                    WHERE ST_Contains(polygon, device_pos.position)
                ''', device_mac)
                
                return [row['zone_id'] for row in rows]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get device zones: {str(e)}")
            return []
            
    async def get_zone_devices(
        self,
        zone_id: str
    ) -> List[str]:
        """Get devices currently in zone."""
        try:
            async with self.postgis.pool.acquire() as conn:
                rows = await conn.fetch('''
                    WITH recent_positions AS (
                        SELECT DISTINCT ON (device_mac)
                            device_mac,
                            position
                        FROM device_positions
                        WHERE time > NOW() - INTERVAL '5 minutes'
                        ORDER BY device_mac, time DESC
                    )
                    SELECT device_mac
                    FROM recent_positions, geofence_zones
                    WHERE zone_id = $1
                    AND ST_Contains(polygon, position)
                ''', zone_id)
                
                return [row['device_mac'] for row in rows]
                
        except Exception as e:
            _LOGGER.error(f"Failed to get zone devices: {str(e)}")
            return []
            
    async def get_device_events(
        self,
        device_mac: str,
        limit: int = 100
    ) -> List[GeofenceEvent]:
        """Get recent geofence events for device."""
        try:
            async with self.postgis.pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT 
                        event_type,
                        zone_id,
                        device_mac,
                        ST_X(position::geometry) as longitude,
                        ST_Y(position::geometry) as latitude,
                        timestamp,
                        metadata
                    FROM geofence_events
                    WHERE device_mac = $1
                    ORDER BY timestamp DESC
                    LIMIT $2
                ''', device_mac, limit)
                
                events = []
                for row in rows:
                    events.append(GeofenceEvent(
                        event_type=row['event_type'],
                        zone_id=row['zone_id'],
                        device_mac=row['device_mac'],
                        timestamp=row['timestamp'],
                        position=SpatialPoint(
                            latitude=row['latitude'],
                            longitude=row['longitude']
                        ),
                        metadata=row['metadata']
                    ))
                    
                return events
                
        except Exception as e:
            _LOGGER.error(f"Failed to get device events: {str(e)}")
            return []
            
    async def _monitor_positions(self):
        """Monitor device positions for geofence events."""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                
                async with self.postgis.pool.acquire() as conn:
                    # Get recent position updates
                    rows = await conn.fetch('''
                        WITH recent_positions AS (
                            SELECT DISTINCT ON (device_mac)
                                device_mac,
                                position,
                                time
                            FROM device_positions
                            WHERE time > NOW() - INTERVAL '5 seconds'
                            ORDER BY device_mac, time DESC
                        )
                        SELECT 
                            p.device_mac,
                            ST_X(p.position::geometry) as longitude,
                            ST_Y(p.position::geometry) as latitude,
                            p.time as timestamp,
                            array_agg(DISTINCT z.zone_id) as current_zones,
                            array_agg(DISTINCT e.zone_id) as previous_zones
                        FROM recent_positions p
                        LEFT JOIN geofence_zones z 
                            ON ST_Contains(z.polygon, p.position)
                        LEFT JOIN LATERAL (
                            SELECT DISTINCT zone_id
                            FROM geofence_events
                            WHERE device_mac = p.device_mac
                            AND event_type IN ('enter', 'dwell')
                            AND timestamp > NOW() - INTERVAL '1 minute'
                        ) e ON true
                        GROUP BY p.device_mac, p.position, p.time
                    ''')
                    
                    for row in rows:
                        device_mac = row['device_mac']
                        position = SpatialPoint(
                            latitude=row['latitude'],
                            longitude=row['longitude'],
                            timestamp=row['timestamp']
                        )
                        
                        current_zones = set(row['current_zones'] or [])
                        previous_zones = set(row['previous_zones'] or [])
                        
                        # Generate events
                        for zone_id in current_zones - previous_zones:
                            # Zone enter event
                            event = GeofenceEvent(
                                event_type='enter',
                                zone_id=zone_id,
                                device_mac=device_mac,
                                timestamp=position.timestamp,
                                position=position
                            )
                            await self._handle_event(event)
                            
                        for zone_id in previous_zones - current_zones:
                            # Zone exit event
                            event = GeofenceEvent(
                                event_type='exit',
                                zone_id=zone_id,
                                device_mac=device_mac,
                                timestamp=position.timestamp,
                                position=position
                            )
                            await self._handle_event(event)
                            
                        for zone_id in current_zones & previous_zones:
                            # Zone dwell event
                            event = GeofenceEvent(
                                event_type='dwell',
                                zone_id=zone_id,
                                device_mac=device_mac,
                                timestamp=position.timestamp,
                                position=position
                            )
                            await self._handle_event(event)
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"Error in position monitor: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
                
    async def _handle_event(self, event: GeofenceEvent):
        """Handle geofence event."""
        try:
            # Store event
            async with self.postgis.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO geofence_events 
                    (event_type, zone_id, device_mac, position, timestamp, metadata)
                    VALUES (
                        $1, $2, $3, 
                        ST_SetSRID(ST_MakePoint($4, $5), 4326),
                        $6, $7
                    )
                ''', event.event_type, event.zone_id, event.device_mac,
                    event.position.longitude, event.position.latitude,
                    event.timestamp, json.dumps(event.metadata) if event.metadata else None)
                    
            # Notify callbacks
            for callback in self.event_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    _LOGGER.error(f"Error in event callback: {str(e)}")
                    
        except Exception as e:
            _LOGGER.error(f"Failed to handle geofence event: {str(e)}") 