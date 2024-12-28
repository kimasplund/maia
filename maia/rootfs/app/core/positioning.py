"""
Positioning module for MAIA.
Handles trilateration, RSSI processing, and position estimation.
"""
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import logging
from scipy.optimize import minimize
from filterpy.kalman import KalmanFilter
import json

_LOGGER = logging.getLogger(__name__)

@dataclass
class RSSIReading:
    """BLE RSSI reading with metadata."""
    scanner_id: str
    rssi: float
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    timestamp: Optional[float] = None

@dataclass
class DevicePosition:
    """Estimated device position."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: float = 0.0
    confidence: float = 0.0

class PositionEstimator:
    """Position estimation using trilateration and Kalman filtering."""
    
    def __init__(
        self,
        rssi_ref: float = -59.0,  # Reference RSSI at 1 meter
        path_loss: float = 2.0,    # Path loss exponent
        noise_floor: float = -100,  # Minimum RSSI value
        min_readings: int = 3,      # Minimum readings for trilateration
        max_distance: float = 50.0  # Maximum reliable distance in meters
    ):
        """Initialize position estimator."""
        self.rssi_ref = rssi_ref
        self.path_loss = path_loss
        self.noise_floor = noise_floor
        self.min_readings = min_readings
        self.max_distance = max_distance
        
        # Initialize Kalman filter for 3D position tracking
        self.kf = KalmanFilter(dim_x=6, dim_z=3)  # [x, y, z, vx, vy, vz]
        self._init_kalman_filter()
        
    def _init_kalman_filter(self):
        """Initialize Kalman filter parameters."""
        # State transition matrix
        self.kf.F = np.array([
            [1, 0, 0, 1, 0, 0],  # x = x + vx
            [0, 1, 0, 0, 1, 0],  # y = y + vy
            [0, 0, 1, 0, 0, 1],  # z = z + vz
            [0, 0, 0, 1, 0, 0],  # vx = vx
            [0, 0, 0, 0, 1, 0],  # vy = vy
            [0, 0, 0, 0, 0, 1]   # vz = vz
        ])
        
        # Measurement matrix
        self.kf.H = np.array([
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0]
        ])
        
        # Measurement noise
        self.kf.R = np.eye(3) * 2.0
        
        # Process noise
        self.kf.Q = np.eye(6) * 0.1
        
        # Initial state uncertainty
        self.kf.P = np.eye(6) * 500.0
        
    def rssi_to_distance(self, rssi: float) -> float:
        """Convert RSSI to estimated distance in meters."""
        if rssi < self.noise_floor:
            return self.max_distance
            
        # Use log-distance path loss model
        distance = 10 ** ((self.rssi_ref - rssi) / (10 * self.path_loss))
        return min(distance, self.max_distance)
        
    def _trilateration_error(
        self,
        pos: np.ndarray,
        points: List[Tuple[float, float, float]],
        distances: List[float]
    ) -> float:
        """Calculate error for trilateration optimization."""
        error = 0
        for (x, y, z), d in zip(points, distances):
            predicted_d = np.sqrt(
                (pos[0] - x)**2 + (pos[1] - y)**2 + (pos[2] - z)**2
            )
            error += (predicted_d - d)**2
        return error
        
    def estimate_position(
        self,
        readings: List[RSSIReading],
        last_position: Optional[DevicePosition] = None
    ) -> Optional[DevicePosition]:
        """Estimate device position from RSSI readings."""
        try:
            if len(readings) < self.min_readings:
                return None
                
            # Convert RSSI to distances
            points = []
            distances = []
            weights = []
            
            for reading in readings:
                distance = self.rssi_to_distance(reading.rssi)
                if distance >= self.max_distance:
                    continue
                    
                # Convert lat/lon to meters (approximate)
                x = reading.longitude * 111320.0  # meters per degree
                y = reading.latitude * 110540.0   # meters per degree
                z = reading.altitude if reading.altitude is not None else 0.0
                
                points.append((x, y, z))
                distances.append(distance)
                weights.append(1.0 / (distance + 1.0))  # Weight by inverse distance
                
            if len(points) < self.min_readings:
                return None
                
            # Initial guess: weighted centroid
            weights = np.array(weights)
            weights /= np.sum(weights)
            initial_guess = np.average(points, weights=weights, axis=0)
            
            # Optimize position using least squares
            result = minimize(
                self._trilateration_error,
                initial_guess,
                args=(points, distances),
                method='Nelder-Mead'
            )
            
            if not result.success:
                return None
                
            # Convert back to lat/lon
            position = result.x
            latitude = position[1] / 110540.0    # degrees
            longitude = position[0] / 111320.0   # degrees
            altitude = position[2] if abs(position[2]) < 1000 else None
            
            # Calculate accuracy estimate
            residual_error = np.sqrt(result.fun / len(points))
            accuracy = residual_error * 2.0  # 95% confidence interval
            
            # Apply Kalman filter if we have previous position
            if last_position:
                # Update state with new measurement
                self.kf.predict()
                measurement = np.array([longitude, latitude, altitude or 0.0])
                self.kf.update(measurement)
                
                # Get filtered position
                filtered_state = self.kf.x
                longitude = filtered_state[0]
                latitude = filtered_state[1]
                altitude = filtered_state[2] if altitude is not None else None
                
                # Update accuracy based on Kalman uncertainty
                position_uncertainty = np.sqrt(np.diag(self.kf.P)[:3])
                accuracy = np.mean(position_uncertainty) * 2.0
                
            return DevicePosition(
                latitude=latitude,
                longitude=longitude,
                altitude=altitude,
                accuracy=accuracy,
                confidence=1.0 / (1.0 + residual_error)  # Convert error to confidence score
            )
            
        except Exception as e:
            _LOGGER.error(f"Failed to estimate position: {str(e)}")
            return None
            
    def calibrate(
        self,
        calibration_data: List[Dict[str, Any]]
    ) -> bool:
        """Calibrate RSSI model using known positions."""
        try:
            if not calibration_data:
                return False
                
            # Extract RSSI and distance pairs
            rssi_values = []
            distances = []
            
            for point in calibration_data:
                rssi_values.append(point['rssi_value'])
                distances.append(point['distance'])
                
            rssi_values = np.array(rssi_values)
            distances = np.array(distances)
            
            # Fit log-distance path loss model
            valid_idx = (rssi_values > self.noise_floor) & (distances > 0)
            if not np.any(valid_idx):
                return False
                
            rssi_values = rssi_values[valid_idx]
            distances = distances[valid_idx]
            
            # Calculate path loss exponent
            log_distances = np.log10(distances)
            self.path_loss = -np.polyfit(
                log_distances,
                rssi_values - self.rssi_ref,
                1
            )[0] / 10.0
            
            _LOGGER.info(f"Calibrated path loss exponent: {self.path_loss}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to calibrate RSSI model: {str(e)}")
            return False 