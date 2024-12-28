"""
Calibration handler for MAIA.
Handles calibration of BLE scanners using high-precision GPS data.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import numpy as np
from scipy.optimize import minimize
from dataclasses import dataclass
import json
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

@dataclass
class CalibrationPoint:
    """Calibration point data."""
    timestamp: datetime
    scanner_mac: str
    device_mac: str
    rssi: float
    distance: float  # meters
    latitude: float
    longitude: float
    accuracy: float
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ScannerCalibration:
    """Scanner calibration data."""
    scanner_mac: str
    reference_rssi: float  # RSSI at 1 meter
    path_loss_exponent: float
    last_calibrated: datetime
    calibration_points: List[CalibrationPoint]
    metadata: Optional[Dict[str, Any]] = None

class CalibrationHandler:
    """Handles BLE scanner calibration."""
    
    def __init__(self, config_dir: str = "/config"):
        """Initialize calibration handler."""
        self._config_dir = Path(config_dir)
        self._calibration_file = self._config_dir / "scanner_calibration.json"
        self._calibrations: Dict[str, ScannerCalibration] = {}
        self._load_calibrations()
        
    def _load_calibrations(self):
        """Load calibrations from file."""
        try:
            if self._calibration_file.exists():
                with open(self._calibration_file, 'r') as f:
                    data = json.load(f)
                    for scanner_mac, cal_data in data.items():
                        self._calibrations[scanner_mac] = ScannerCalibration(
                            scanner_mac=scanner_mac,
                            reference_rssi=cal_data["reference_rssi"],
                            path_loss_exponent=cal_data["path_loss_exponent"],
                            last_calibrated=datetime.fromisoformat(cal_data["last_calibrated"]),
                            calibration_points=[
                                CalibrationPoint(
                                    timestamp=datetime.fromisoformat(p["timestamp"]),
                                    scanner_mac=p["scanner_mac"],
                                    device_mac=p["device_mac"],
                                    rssi=p["rssi"],
                                    distance=p["distance"],
                                    latitude=p["latitude"],
                                    longitude=p["longitude"],
                                    accuracy=p["accuracy"],
                                    metadata=p.get("metadata")
                                )
                                for p in cal_data["calibration_points"]
                            ],
                            metadata=cal_data.get("metadata")
                        )
                _LOGGER.info(f"Loaded calibrations for {len(self._calibrations)} scanners")
        except Exception as e:
            _LOGGER.error(f"Failed to load calibrations: {str(e)}")
            
    def _save_calibrations(self):
        """Save calibrations to file."""
        try:
            data = {
                scanner_mac: {
                    "reference_rssi": cal.reference_rssi,
                    "path_loss_exponent": cal.path_loss_exponent,
                    "last_calibrated": cal.last_calibrated.isoformat(),
                    "calibration_points": [
                        {
                            "timestamp": p.timestamp.isoformat(),
                            "scanner_mac": p.scanner_mac,
                            "device_mac": p.device_mac,
                            "rssi": p.rssi,
                            "distance": p.distance,
                            "latitude": p.latitude,
                            "longitude": p.longitude,
                            "accuracy": p.accuracy,
                            "metadata": p.metadata
                        }
                        for p in cal.calibration_points
                    ],
                    "metadata": cal.metadata
                }
                for scanner_mac, cal in self._calibrations.items()
            }
            with open(self._calibration_file, 'w') as f:
                json.dump(data, f, indent=2)
            _LOGGER.info("Saved calibrations")
        except Exception as e:
            _LOGGER.error(f"Failed to save calibrations: {str(e)}")
            
    def add_calibration_point(
        self,
        scanner_mac: str,
        device_mac: str,
        rssi: float,
        latitude: float,
        longitude: float,
        accuracy: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add calibration point."""
        try:
            # Calculate distance using Haversine formula
            scanner_location = metadata.get("scanner_location", {})
            scanner_lat = scanner_location.get("latitude")
            scanner_lon = scanner_location.get("longitude")
            
            if not (scanner_lat and scanner_lon):
                _LOGGER.error("Scanner location not available")
                return False
                
            distance = self._haversine_distance(
                lat1=scanner_lat,
                lon1=scanner_lon,
                lat2=latitude,
                lon2=longitude
            )
            
            # Create calibration point
            point = CalibrationPoint(
                timestamp=datetime.now(),
                scanner_mac=scanner_mac,
                device_mac=device_mac,
                rssi=rssi,
                distance=distance,
                latitude=latitude,
                longitude=longitude,
                accuracy=accuracy,
                metadata=metadata
            )
            
            # Add to calibration data
            if scanner_mac not in self._calibrations:
                self._calibrations[scanner_mac] = ScannerCalibration(
                    scanner_mac=scanner_mac,
                    reference_rssi=-59.0,  # Default value
                    path_loss_exponent=2.0,  # Default value
                    last_calibrated=datetime.now(),
                    calibration_points=[],
                    metadata={}
                )
                
            self._calibrations[scanner_mac].calibration_points.append(point)
            
            # Recalibrate if we have enough points
            if len(self._calibrations[scanner_mac].calibration_points) >= 5:
                self._calibrate_scanner(scanner_mac)
                
            self._save_calibrations()
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to add calibration point: {str(e)}")
            return False
            
    def _calibrate_scanner(self, scanner_mac: str):
        """Calibrate scanner using collected points."""
        try:
            cal = self._calibrations[scanner_mac]
            points = cal.calibration_points
            
            if len(points) < 5:
                _LOGGER.warning(f"Not enough calibration points for {scanner_mac}")
                return
                
            # Prepare data for optimization
            distances = np.array([p.distance for p in points])
            rssis = np.array([p.rssi for p in points])
            
            # Define error function
            def error_func(params):
                ref_rssi, path_loss = params
                predicted_rssis = ref_rssi - 10 * path_loss * np.log10(distances)
                return np.sum((predicted_rssis - rssis) ** 2)
                
            # Initial guess
            initial_guess = [cal.reference_rssi, cal.path_loss_exponent]
            
            # Optimize parameters
            result = minimize(
                error_func,
                initial_guess,
                method='Nelder-Mead',
                bounds=[(-100, -20), (1.5, 4.0)]
            )
            
            if result.success:
                cal.reference_rssi = result.x[0]
                cal.path_loss_exponent = result.x[1]
                cal.last_calibrated = datetime.now()
                _LOGGER.info(f"Calibrated scanner {scanner_mac}: "
                           f"ref_rssi={cal.reference_rssi:.1f}, "
                           f"path_loss={cal.path_loss_exponent:.2f}")
            else:
                _LOGGER.error(f"Calibration failed for {scanner_mac}")
                
        except Exception as e:
            _LOGGER.error(f"Error during calibration: {str(e)}")
            
    def get_calibration(self, scanner_mac: str) -> Optional[ScannerCalibration]:
        """Get calibration for scanner."""
        return self._calibrations.get(scanner_mac)
        
    def get_all_calibrations(self) -> Dict[str, ScannerCalibration]:
        """Get all scanner calibrations."""
        return self._calibrations.copy()
        
    def estimate_distance(
        self,
        scanner_mac: str,
        rssi: float,
        fallback: bool = True
    ) -> Optional[float]:
        """Estimate distance from RSSI using calibration."""
        try:
            cal = self._calibrations.get(scanner_mac)
            if not cal and not fallback:
                return None
                
            # Use default values if no calibration
            ref_rssi = cal.reference_rssi if cal else -59.0
            path_loss = cal.path_loss_exponent if cal else 2.0
            
            # Calculate distance
            distance = 10 ** ((ref_rssi - rssi) / (10 * path_loss))
            return distance
            
        except Exception as e:
            _LOGGER.error(f"Failed to estimate distance: {str(e)}")
            return None
            
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371000  # Earth radius in meters
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        
        # Differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c  # Distance in meters 