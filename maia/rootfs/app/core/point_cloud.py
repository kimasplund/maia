"""
Point cloud handler for MAIA.
Builds and maintains a 3D map of the environment using BLE and GPS data.
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass
import json
from pathlib import Path
from scipy.spatial import ConvexHull
from scipy.interpolate import griddata

_LOGGER = logging.getLogger(__name__)

@dataclass
class SpatialPoint:
    """3D point in space with metadata."""
    timestamp: datetime
    x: float  # meters from reference point
    y: float  # meters from reference point
    z: float  # meters from ground level
    rssi: float
    accuracy: float
    source: str  # 'ble', 'gps', etc.
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class PointCloud:
    """Collection of spatial points forming a 3D map."""
    points: List[SpatialPoint]
    reference_lat: float
    reference_lon: float
    last_updated: datetime
    metadata: Optional[Dict[str, Any]] = None

class PointCloudHandler:
    """Handles 3D point cloud mapping."""
    
    def __init__(self, config_dir: str = "/config"):
        """Initialize point cloud handler."""
        self._config_dir = Path(config_dir)
        self._cloud_file = self._config_dir / "point_cloud.json"
        self._clouds: Dict[str, PointCloud] = {}  # zone_id -> PointCloud
        self._max_age = timedelta(days=30)  # Keep points for 30 days
        self._min_points = 100  # Minimum points for surface generation
        self._load_clouds()
        
    def _load_clouds(self):
        """Load point clouds from file."""
        try:
            if self._cloud_file.exists():
                with open(self._cloud_file, 'r') as f:
                    data = json.load(f)
                    for zone_id, cloud_data in data.items():
                        self._clouds[zone_id] = PointCloud(
                            points=[
                                SpatialPoint(
                                    timestamp=datetime.fromisoformat(p["timestamp"]),
                                    x=p["x"],
                                    y=p["y"],
                                    z=p["z"],
                                    rssi=p["rssi"],
                                    accuracy=p["accuracy"],
                                    source=p["source"],
                                    metadata=p.get("metadata")
                                )
                                for p in cloud_data["points"]
                            ],
                            reference_lat=cloud_data["reference_lat"],
                            reference_lon=cloud_data["reference_lon"],
                            last_updated=datetime.fromisoformat(cloud_data["last_updated"]),
                            metadata=cloud_data.get("metadata")
                        )
                _LOGGER.info(f"Loaded point clouds for {len(self._clouds)} zones")
        except Exception as e:
            _LOGGER.error(f"Failed to load point clouds: {str(e)}")
            
    def _save_clouds(self):
        """Save point clouds to file."""
        try:
            data = {
                zone_id: {
                    "points": [
                        {
                            "timestamp": p.timestamp.isoformat(),
                            "x": p.x,
                            "y": p.y,
                            "z": p.z,
                            "rssi": p.rssi,
                            "accuracy": p.accuracy,
                            "source": p.source,
                            "metadata": p.metadata
                        }
                        for p in cloud.points
                    ],
                    "reference_lat": cloud.reference_lat,
                    "reference_lon": cloud.reference_lon,
                    "last_updated": cloud.last_updated.isoformat(),
                    "metadata": cloud.metadata
                }
                for zone_id, cloud in self._clouds.items()
            }
            with open(self._cloud_file, 'w') as f:
                json.dump(data, f, indent=2)
            _LOGGER.info("Saved point clouds")
        except Exception as e:
            _LOGGER.error(f"Failed to save point clouds: {str(e)}")
            
    def add_point(
        self,
        zone_id: str,
        latitude: float,
        longitude: float,
        altitude: Optional[float],
        rssi: float,
        accuracy: float,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add point to cloud."""
        try:
            # Get or create point cloud for zone
            if zone_id not in self._clouds:
                self._clouds[zone_id] = PointCloud(
                    points=[],
                    reference_lat=latitude,
                    reference_lon=longitude,
                    last_updated=datetime.now(),
                    metadata={}
                )
            cloud = self._clouds[zone_id]
            
            # Convert to local coordinates
            x, y = self._latlon_to_xy(
                latitude, longitude,
                cloud.reference_lat, cloud.reference_lon
            )
            z = altitude if altitude is not None else 0.0
            
            # Create point
            point = SpatialPoint(
                timestamp=datetime.now(),
                x=x,
                y=y,
                z=z,
                rssi=rssi,
                accuracy=accuracy,
                source=source,
                metadata=metadata
            )
            
            # Add point and update timestamp
            cloud.points.append(point)
            cloud.last_updated = datetime.now()
            
            # Clean old points
            self._clean_old_points(zone_id)
            
            # Save changes
            self._save_clouds()
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to add point: {str(e)}")
            return False
            
    def _clean_old_points(self, zone_id: str):
        """Remove points older than max_age."""
        try:
            if zone_id in self._clouds:
                cutoff = datetime.now() - self._max_age
                cloud = self._clouds[zone_id]
                cloud.points = [
                    p for p in cloud.points
                    if p.timestamp >= cutoff
                ]
        except Exception as e:
            _LOGGER.error(f"Failed to clean old points: {str(e)}")
            
    def get_point_cloud(self, zone_id: str) -> Optional[PointCloud]:
        """Get point cloud for zone."""
        return self._clouds.get(zone_id)
        
    def get_all_clouds(self) -> Dict[str, PointCloud]:
        """Get all point clouds."""
        return self._clouds.copy()
        
    def generate_surface(
        self,
        zone_id: str,
        resolution: float = 1.0  # meters
    ) -> Optional[Dict[str, Any]]:
        """Generate 3D surface from point cloud."""
        try:
            cloud = self._clouds.get(zone_id)
            if not cloud or len(cloud.points) < self._min_points:
                return None
                
            # Extract point coordinates
            points = np.array([
                [p.x, p.y, p.z]
                for p in cloud.points
            ])
            
            # Create grid
            x_min, x_max = points[:, 0].min(), points[:, 0].max()
            y_min, y_max = points[:, 1].min(), points[:, 1].max()
            
            x_grid = np.arange(x_min, x_max + resolution, resolution)
            y_grid = np.arange(y_min, y_max + resolution, resolution)
            X, Y = np.meshgrid(x_grid, y_grid)
            
            # Interpolate Z values
            Z = griddata(
                points=points[:, :2],
                values=points[:, 2],
                xi=(X, Y),
                method='cubic',
                fill_value=0
            )
            
            # Generate RSSI heatmap
            rssi_values = np.array([p.rssi for p in cloud.points])
            RSSI = griddata(
                points=points[:, :2],
                values=rssi_values,
                xi=(X, Y),
                method='cubic',
                fill_value=-100
            )
            
            # Calculate convex hull for boundary
            hull = ConvexHull(points[:, :2])
            boundary = points[hull.vertices, :2].tolist()
            
            return {
                "x_grid": x_grid.tolist(),
                "y_grid": y_grid.tolist(),
                "z_surface": Z.tolist(),
                "rssi_heatmap": RSSI.tolist(),
                "boundary": boundary,
                "reference": {
                    "latitude": cloud.reference_lat,
                    "longitude": cloud.reference_lon
                },
                "metadata": {
                    "num_points": len(cloud.points),
                    "last_updated": cloud.last_updated.isoformat(),
                    "resolution": resolution
                }
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate surface: {str(e)}")
            return None
            
    def get_point_density(
        self,
        zone_id: str,
        radius: float = 5.0  # meters
    ) -> Optional[Dict[str, Any]]:
        """Get point density map."""
        try:
            cloud = self._clouds.get(zone_id)
            if not cloud or len(cloud.points) < self._min_points:
                return None
                
            # Extract point coordinates
            points = np.array([
                [p.x, p.y]
                for p in cloud.points
            ])
            
            # Create grid
            x_min, x_max = points[:, 0].min(), points[:, 0].max()
            y_min, y_max = points[:, 1].min(), points[:, 1].max()
            
            resolution = radius / 2
            x_grid = np.arange(x_min, x_max + resolution, resolution)
            y_grid = np.arange(y_min, y_max + resolution, resolution)
            X, Y = np.meshgrid(x_grid, y_grid)
            
            # Calculate density
            density = np.zeros_like(X)
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    center = np.array([X[i, j], Y[i, j]])
                    distances = np.sqrt(np.sum((points - center) ** 2, axis=1))
                    density[i, j] = np.sum(distances < radius)
                    
            return {
                "x_grid": x_grid.tolist(),
                "y_grid": y_grid.tolist(),
                "density": density.tolist(),
                "metadata": {
                    "radius": radius,
                    "max_density": int(density.max()),
                    "total_points": len(points)
                }
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to calculate point density: {str(e)}")
            return None
            
    @staticmethod
    def _latlon_to_xy(
        lat: float,
        lon: float,
        ref_lat: float,
        ref_lon: float
    ) -> Tuple[float, float]:
        """Convert latitude/longitude to local X/Y coordinates."""
        # Earth's radius in meters
        R = 6371000
        
        # Convert to radians
        lat, lon = np.radians([lat, lon])
        ref_lat, ref_lon = np.radians([ref_lat, ref_lon])
        
        # Calculate differences
        dlat = lat - ref_lat
        dlon = lon - ref_lon
        
        # Convert to meters
        x = R * dlon * np.cos(ref_lat)
        y = R * dlat
        
        return x, y 