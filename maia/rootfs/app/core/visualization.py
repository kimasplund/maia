"""
Visualization module for MAIA.
Generates heatmaps, coverage maps, and movement traces.
"""
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import folium
from folium import plugins
import io
import base64
from datetime import datetime, timedelta
from dataclasses import dataclass
from shapely.geometry import Point, Polygon
import json

_LOGGER = logging.getLogger(__name__)

@dataclass
class MapBounds:
    """Map boundary coordinates."""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get center coordinates."""
        return (
            (self.min_lat + self.max_lat) / 2,
            (self.min_lon + self.max_lon) / 2
        )
        
    @property
    def dimensions(self) -> Tuple[float, float]:
        """Get dimensions in degrees."""
        return (
            self.max_lat - self.min_lat,
            self.max_lon - self.min_lon
        )

class VisualizationGenerator:
    """Generates visualizations for positioning data."""
    
    def __init__(
        self,
        grid_size: int = 50,
        default_zoom: int = 18,
        tile_provider: str = "OpenStreetMap",
        dark_mode: bool = False
    ):
        """Initialize visualization generator."""
        self.grid_size = grid_size
        self.default_zoom = default_zoom
        self.tile_provider = (
            "CartoDB dark_matter" if dark_mode else tile_provider
        )
        self.dark_mode = dark_mode
        
    def _get_bounds(
        self,
        points: List[Tuple[float, float]],
        padding: float = 0.001  # degrees
    ) -> MapBounds:
        """Calculate map bounds from points."""
        if not points:
            return MapBounds(0, 0, 0, 0)
            
        lats, lons = zip(*points)
        return MapBounds(
            min_lat=min(lats) - padding,
            max_lat=max(lats) + padding,
            min_lon=min(lons) - padding,
            max_lon=max(lons) + padding
        )
        
    def generate_coverage_map(
        self,
        scanners: List[Dict[str, Any]],
        readings: List[Dict[str, Any]],
        interactive: bool = True
    ) -> str:
        """Generate coverage map with scanner locations and signal strength."""
        try:
            # Extract scanner locations
            scanner_points = [
                (s["latitude"], s["longitude"])
                for s in scanners
            ]
            bounds = self._get_bounds(scanner_points)
            
            # Create base map
            m = folium.Map(
                location=bounds.center,
                zoom_start=self.default_zoom,
                tiles=self.tile_provider
            )
            
            # Create layer control
            folium.LayerControl().add_to(m)
            
            # Add scanner layer
            scanner_layer = folium.FeatureGroup(name="Scanners")
            for scanner in scanners:
                # Create detailed popup
                popup_html = f"""
                    <div style="font-family: Arial; min-width: 200px;">
                        <h4>Scanner: {scanner['scanner_id']}</h4>
                        <p>Location: {scanner['latitude']:.6f}, {scanner['longitude']:.6f}</p>
                        <p>Altitude: {scanner.get('altitude', 'N/A')}</p>
                        <p>Last Update: {scanner.get('updated_at', 'N/A')}</p>
                    </div>
                """
                
                # Add scanner marker
                folium.CircleMarker(
                    location=(scanner["latitude"], scanner["longitude"]),
                    radius=8,
                    color="red",
                    fill=True,
                    popup=folium.Popup(popup_html, max_width=300)
                ).add_to(scanner_layer)
            
            scanner_layer.add_to(m)
            
            # Create signal strength heatmap layer
            if readings:
                heatmap_data = []
                device_readings = {}
                
                for reading in readings:
                    # Weight by RSSI value
                    weight = (reading["rssi"] + 100) / 60
                    weight = max(0, min(1, weight))
                    
                    heatmap_data.append([
                        reading["latitude"],
                        reading["longitude"],
                        weight
                    ])
                    
                    # Group readings by device
                    device = reading["device_mac"]
                    if device not in device_readings:
                        device_readings[device] = []
                    device_readings[device].append(reading)
                
                # Add heatmap layer
                heatmap_layer = folium.FeatureGroup(name="Signal Strength")
                plugins.HeatMap(heatmap_data).add_to(heatmap_layer)
                heatmap_layer.add_to(m)
                
                # Add device layers
                for device, device_data in device_readings.items():
                    device_layer = folium.FeatureGroup(name=f"Device {device}")
                    
                    # Create device path
                    points = [(d["latitude"], d["longitude"]) for d in device_data]
                    if len(points) > 1:
                        folium.PolyLine(
                            points,
                            weight=2,
                            color="blue",
                            opacity=0.6
                        ).add_to(device_layer)
                    
                    # Add reading points
                    for reading in device_data:
                        popup_html = f"""
                            <div style="font-family: Arial; min-width: 200px;">
                                <h4>Device: {device}</h4>
                                <p>RSSI: {reading['rssi']} dBm</p>
                                <p>Scanner: {reading['scanner_id']}</p>
                                <p>Time: {reading.get('timestamp', 'N/A')}</p>
                            </div>
                        """
                        
                        folium.CircleMarker(
                            location=(reading["latitude"], reading["longitude"]),
                            radius=3,
                            color="blue",
                            fill=True,
                            popup=folium.Popup(popup_html, max_width=300)
                        ).add_to(device_layer)
                    
                    device_layer.add_to(m)
            
            if interactive:
                # Add draw control
                plugins.Draw(
                    export=True,
                    position='topleft',
                    draw_options={
                        'polyline': True,
                        'polygon': True,
                        'circle': True,
                        'marker': True
                    }
                ).add_to(m)
                
                # Add fullscreen control
                plugins.Fullscreen().add_to(m)
                
                # Add measurement control
                plugins.MeasureControl(
                    position='bottomleft',
                    primary_length_unit='meters',
                    secondary_length_unit='kilometers'
                ).add_to(m)
                
                # Add minimap
                minimap = plugins.MiniMap(toggle_display=True)
                m.add_child(minimap)
                
            return m._repr_html_()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate coverage map: {str(e)}")
            return ""
            
    def generate_movement_trace(
        self,
        positions: List[Dict[str, Any]],
        time_window: Optional[timedelta] = None
    ) -> str:
        """Generate movement trace visualization."""
        try:
            if not positions:
                return ""
                
            # Filter positions by time window
            if time_window:
                cutoff = datetime.now() - time_window
                positions = [
                    p for p in positions
                    if datetime.fromisoformat(p["timestamp"]) > cutoff
                ]
                
            # Extract position points
            points = [(p["latitude"], p["longitude"]) for p in positions]
            bounds = self._get_bounds(points)
            
            # Create base map
            m = folium.Map(
                location=bounds.center,
                zoom_start=self.default_zoom,
                tiles=self.tile_provider
            )
            
            # Add movement path
            folium.PolyLine(
                points,
                weight=2,
                color="blue",
                opacity=0.8
            ).add_to(m)
            
            # Add points with timestamps
            for pos in positions:
                folium.CircleMarker(
                    location=(pos["latitude"], pos["longitude"]),
                    radius=3,
                    color="blue",
                    fill=True,
                    popup=f"Time: {pos['timestamp']}<br>Accuracy: {pos['accuracy']:.1f}m"
                ).add_to(m)
                
            # Add accuracy circles
            for pos in positions:
                folium.Circle(
                    location=(pos["latitude"], pos["longitude"]),
                    radius=pos["accuracy"],
                    color="blue",
                    fill=False,
                    opacity=0.3
                ).add_to(m)
                
            return m._repr_html_()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate movement trace: {str(e)}")
            return ""
            
    def generate_rssi_heatmap(
        self,
        calibration_data: List[Dict[str, Any]],
        scanner_id: Optional[str] = None
    ) -> str:
        """Generate RSSI vs distance heatmap."""
        try:
            if not calibration_data:
                return ""
                
            # Filter by scanner if specified
            if scanner_id:
                calibration_data = [
                    d for d in calibration_data
                    if d["scanner_id"] == scanner_id
                ]
                
            # Create figure
            fig = Figure(figsize=(10, 6))
            ax = fig.add_subplot(111)
            
            # Extract data
            distances = [d["distance"] for d in calibration_data]
            rssi_values = [d["rssi_value"] for d in calibration_data]
            
            # Create 2D histogram
            hist, xedges, yedges = np.histogram2d(
                distances,
                rssi_values,
                bins=(20, 20)
            )
            
            # Plot heatmap
            im = ax.imshow(
                hist.T,
                origin="lower",
                aspect="auto",
                extent=[
                    xedges[0], xedges[-1],
                    yedges[0], yedges[-1]
                ],
                cmap="viridis"
            )
            
            # Add colorbar
            fig.colorbar(im, ax=ax, label="Count")
            
            # Set labels
            ax.set_xlabel("Distance (m)")
            ax.set_ylabel("RSSI (dBm)")
            ax.set_title("RSSI vs Distance Distribution")
            
            # Convert to base64 image
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate RSSI heatmap: {str(e)}")
            return ""
            
    def generate_position_accuracy(
        self,
        positions: List[Dict[str, Any]],
        time_window: Optional[timedelta] = None,
        bin_size: timedelta = timedelta(minutes=5)
    ) -> str:
        """Generate position accuracy over time visualization."""
        try:
            if not positions:
                return ""
                
            # Filter positions by time window
            if time_window:
                cutoff = datetime.now() - time_window
                positions = [
                    p for p in positions
                    if datetime.fromisoformat(p["timestamp"]) > cutoff
                ]
                
            # Create figure
            fig = Figure(figsize=(12, 6))
            ax = fig.add_subplot(111)
            
            # Extract timestamps and accuracies
            timestamps = [
                datetime.fromisoformat(p["timestamp"])
                for p in positions
            ]
            accuracies = [p["accuracy"] for p in positions]
            
            # Plot accuracy points
            ax.scatter(timestamps, accuracies, alpha=0.5, s=20)
            
            # Add trend line
            ax.plot(timestamps, accuracies, alpha=0.3)
            
            # Set labels
            ax.set_xlabel("Time")
            ax.set_ylabel("Accuracy (m)")
            ax.set_title("Position Accuracy Over Time")
            
            # Rotate x-axis labels
            plt.setp(ax.get_xticklabels(), rotation=45)
            
            # Add grid
            ax.grid(True, alpha=0.3)
            
            # Adjust layout
            fig.tight_layout()
            
            # Convert to base64 image
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate accuracy plot: {str(e)}")
            return ""
            
    def generate_3d_movement_trace(
        self,
        positions: List[Dict[str, Any]],
        time_window: Optional[timedelta] = None
    ) -> str:
        """Generate 3D movement trace visualization."""
        try:
            if not positions:
                return ""
                
            # Filter positions by time window
            if time_window:
                cutoff = datetime.now() - time_window
                positions = [
                    p for p in positions
                    if datetime.fromisoformat(p["timestamp"]) > cutoff
                ]
                
            # Create figure
            fig = Figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
            
            # Extract coordinates
            lats = [p["latitude"] for p in positions]
            lons = [p["longitude"] for p in positions]
            times = [
                (datetime.fromisoformat(p["timestamp"]) - datetime.now()).total_seconds() / 3600
                for p in positions
            ]
            
            # Plot 3D trace
            scatter = ax.scatter(
                lons, lats, times,
                c=times,
                cmap='viridis',
                alpha=0.6
            )
            
            # Add path
            ax.plot(lons, lats, times, 'b-', alpha=0.3)
            
            # Set labels
            ax.set_xlabel('Longitude')
            ax.set_ylabel('Latitude')
            ax.set_zlabel('Time (hours)')
            ax.set_title('3D Movement Trace')
            
            # Add colorbar
            fig.colorbar(scatter, label='Time (hours)')
            
            # Convert to base64 image
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate 3D trace: {str(e)}")
            return ""
            
    def generate_device_density_map(
        self,
        readings: List[Dict[str, Any]],
        grid_resolution: float = 0.0001  # degrees
    ) -> str:
        """Generate device density heatmap."""
        try:
            if not readings:
                return ""
                
            # Extract points
            points = [(r["latitude"], r["longitude"]) for r in readings]
            bounds = self._get_bounds(points)
            
            # Create base map
            m = folium.Map(
                location=bounds.center,
                zoom_start=self.default_zoom,
                tiles=self.tile_provider
            )
            
            # Create density grid
            lat_bins = np.arange(
                bounds.min_lat,
                bounds.max_lat + grid_resolution,
                grid_resolution
            )
            lon_bins = np.arange(
                bounds.min_lon,
                bounds.max_lon + grid_resolution,
                grid_resolution
            )
            
            # Calculate density
            density, _, _ = np.histogram2d(
                [p[0] for p in points],
                [p[1] for p in points],
                bins=[lat_bins, lon_bins]
            )
            
            # Create heatmap data
            heatmap_data = []
            for i in range(len(lat_bins)-1):
                for j in range(len(lon_bins)-1):
                    if density[i,j] > 0:
                        heatmap_data.append([
                            lat_bins[i],
                            lon_bins[j],
                            density[i,j]
                        ])
            
            # Add heatmap layer
            plugins.HeatMap(
                heatmap_data,
                name="Device Density",
                min_opacity=0.3,
                radius=15
            ).add_to(m)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            return m._repr_html_()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate density map: {str(e)}")
            return ""
            
    def generate_signal_quality_chart(
        self,
        readings: List[Dict[str, Any]],
        time_bins: int = 24
    ) -> str:
        """Generate signal quality over time chart."""
        try:
            if not readings:
                return ""
                
            # Create figure
            fig = Figure(figsize=(12, 6))
            ax = fig.add_subplot(111)
            
            # Extract timestamps and RSSI values
            timestamps = [
                datetime.fromisoformat(r["timestamp"])
                for r in readings
            ]
            rssi_values = [r["rssi"] for r in readings]
            
            # Calculate time bins
            time_range = max(timestamps) - min(timestamps)
            bin_size = time_range / time_bins
            
            # Create histogram
            hist, bins, _ = ax.hist(
                timestamps,
                bins=time_bins,
                weights=rssi_values,
                alpha=0.6,
                color='blue'
            )
            
            # Add trend line
            bin_centers = (bins[:-1] + bins[1:]) / 2
            ax.plot(bin_centers, hist, 'r-', linewidth=2)
            
            # Set labels
            ax.set_xlabel('Time')
            ax.set_ylabel('Average RSSI (dBm)')
            ax.set_title('Signal Quality Over Time')
            
            # Rotate x-axis labels
            plt.setp(ax.get_xticklabels(), rotation=45)
            
            # Add grid
            ax.grid(True, alpha=0.3)
            
            # Adjust layout
            fig.tight_layout()
            
            # Convert to base64 image
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()
            
        except Exception as e:
            _LOGGER.error(f"Failed to generate signal quality chart: {str(e)}")
            return "" 