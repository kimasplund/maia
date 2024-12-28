"""
Position calculator for BLE tracking.
Handles trilateration and position estimation from BLE RSSI readings.
"""
from typing import Dict, List, Optional, Any, Tuple
import logging
import numpy as np
from scipy.optimize import minimize
from filterpy.kalman import KalmanFilter
from dataclasses import dataclass
import json

_LOGGER = logging.getLogger(__name__)

@dataclass
class RSSICalibration:
    """RSSI calibration parameters."""
    reference_power: float  # RSSI at 1 meter
    path_loss_exponent: float  # Signal propagation constant
    std_dev: float  # Standard deviation of measurements

class PositionCalculator:
    """Position calculator for BLE tracking."""
    
    def __init__(self):
        """Initialize position calculator."""
        # Default calibration values
        self.calibration = RSSICalibration(
            reference_power=-59.0,  # Typical value for BLE
            path_loss_exponent=2.0,  # Free space path loss
            std_dev=2.0
        )
        
        # Initialize Kalman filter for each tracked device
        self.kalman_filters: Dict[str, KalmanFilter] = {}
        
        # Cache for recent positions
        self.position_cache: Dict[str, Dict[str, Any]] = {}
        
    async def calibrate(self, calibration_points: List[Dict[str, Any]]):
        """Calibrate using reference measurements."""
        try:
            if not calibration_points:
                return
                
            # Extract distances and RSSI values
            distances = []
            rssi_values = []
            
            for point in calibration_points:
                location = point["location"]["coordinates"]
                readings = point["readings"]
                
                for scanner_id, reading in readings.items():
                    # Calculate true distance to scanner
                    scanner_loc = np.array(reading["scanner_location"])
                    point_loc = np.array(location)
                    distance = np.linalg.norm(scanner_loc - point_loc)
                    
                    distances.append(distance)
                    rssi_values.append(reading["rssi"])
                    
            # Convert to numpy arrays
            distances = np.array(distances)
            rssi_values = np.array(rssi_values)
            
            # Fit path loss model
            def path_loss_error(params):
                ref_power, path_loss = params
                predicted_rssi = ref_power - 10 * path_loss * np.log10(distances)
                return np.sum((predicted_rssi - rssi_values) ** 2)
                
            # Optimize parameters
            result = minimize(
                path_loss_error,
                [self.calibration.reference_power, self.calibration.path_loss_exponent],
                method='nelder-mead'
            )
            
            if result.success:
                ref_power, path_loss = result.x
                
                # Calculate standard deviation of residuals
                predicted_rssi = ref_power - 10 * path_loss * np.log10(distances)
                residuals = predicted_rssi - rssi_values
                std_dev = np.std(residuals)
                
                # Update calibration
                self.calibration = RSSICalibration(
                    reference_power=ref_power,
                    path_loss_exponent=path_loss,
                    std_dev=std_dev
                )
                
                _LOGGER.info(
                    f"Calibration updated: ref_power={ref_power:.1f}, "
                    f"path_loss={path_loss:.2f}, std_dev={std_dev:.2f}"
                )
                
        except Exception as e:
            _LOGGER.error(f"Calibration failed: {str(e)}")
            
    def _rssi_to_distance(self, rssi: float) -> float:
        """Convert RSSI to distance using calibrated path loss model."""
        try:
            return 10 ** ((self.calibration.reference_power - rssi) / 
                         (10 * self.calibration.path_loss_exponent))
        except Exception:
            return 0.0
            
    def _get_kalman_filter(self, device_mac: str) -> KalmanFilter:
        """Get or create Kalman filter for device."""
        if device_mac not in self.kalman_filters:
            # Initialize filter
            kf = KalmanFilter(dim_x=6, dim_z=3)  # State: [x, y, z, vx, vy, vz]
            
            # State transition matrix
            dt = 0.1  # Time step
            kf.F = np.array([
                [1, 0, 0, dt, 0, 0],
                [0, 1, 0, 0, dt, 0],
                [0, 0, 1, 0, 0, dt],
                [0, 0, 0, 1, 0, 0],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 1]
            ])
            
            # Measurement matrix
            kf.H = np.array([
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 1, 0, 0, 0]
            ])
            
            # Measurement noise
            kf.R = np.eye(3) * self.calibration.std_dev ** 2
            
            # Process noise
            q = 0.1  # Process noise magnitude
            kf.Q = np.eye(6) * q
            
            # Initial state uncertainty
            kf.P *= 1000
            
            self.kalman_filters[device_mac] = kf
            
        return self.kalman_filters[device_mac]
        
    async def calculate_position(
        self,
        readings: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Calculate device position from RSSI readings."""
        try:
            if len(readings) < 3:
                return None
                
            # Extract scanner positions and distances
            scanner_positions = []
            distances = []
            
            for reading in readings:
                # Get scanner position
                scanner_loc = json.loads(reading["scanner_location"])
                scanner_pos = np.array([
                    scanner_loc["coordinates"][0],
                    scanner_loc["coordinates"][1],
                    scanner_loc["coordinates"][2]
                ])
                scanner_positions.append(scanner_pos)
                
                # Convert RSSI to distance
                distance = self._rssi_to_distance(reading["rssi"])
                distances.append(distance)
                
            # Convert to numpy arrays
            scanner_positions = np.array(scanner_positions)
            distances = np.array(distances)
            
            # Define error function for minimization
            def mse(point):
                calculated_distances = np.linalg.norm(
                    scanner_positions - point.reshape(1, 3),
                    axis=1
                )
                return np.mean((calculated_distances - distances) ** 2)
                
            # Initial guess at centroid of scanners
            initial_guess = np.mean(scanner_positions, axis=0)
            
            # Minimize error
            result = minimize(
                mse,
                initial_guess,
                method='nelder-mead',
                options={'maxiter': 100}
            )
            
            if not result.success:
                return None
                
            # Get device MAC from readings
            device_mac = readings[0]["device_mac"]
            
            # Apply Kalman filter
            kf = self._get_kalman_filter(device_mac)
            
            # If this is first reading, initialize state
            if kf.x is None:
                kf.x = np.array([
                    result.x[0], result.x[1], result.x[2],
                    0, 0, 0
                ])
            
            # Update filter
            kf.predict()
            kf.update(result.x)
            
            # Get filtered position
            filtered_pos = kf.x[:3]
            
            # Calculate accuracy estimate
            accuracy = np.sqrt(np.mean(kf.P[:3, :3].diagonal()))
            
            # Cache position
            self.position_cache[device_mac] = {
                "x": float(filtered_pos[0]),
                "y": float(filtered_pos[1]),
                "z": float(filtered_pos[2]),
                "accuracy": float(accuracy),
                "method": "trilateration_kalman",
                "timestamp": readings[0]["time"].isoformat()
            }
            
            return self.position_cache[device_mac]
            
        except Exception as e:
            _LOGGER.error(f"Position calculation failed: {str(e)}")
            return None
            
    def get_last_position(self, device_mac: str) -> Optional[Dict[str, Any]]:
        """Get last calculated position for device."""
        return self.position_cache.get(device_mac)
        
    def clear_device_data(self, device_mac: str):
        """Clear cached data for device."""
        if device_mac in self.kalman_filters:
            del self.kalman_filters[device_mac]
        if device_mac in self.position_cache:
            del self.position_cache[device_mac] 