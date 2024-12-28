"""
Base scanner class for MAIA.
Handles common functionality for BLE and WiFi scanners.
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass
import json
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

@dataclass
class ScannerLocation:
    """Scanner location data."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None
    source: Optional[str] = None  # 'fixed', 'gps', 'manual', etc.

@dataclass
class ScannerInfo:
    """Scanner information."""
    scanner_id: str
    scanner_type: str  # 'ble', 'wifi'
    is_mobile: bool
    location: Optional[ScannerLocation] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ScanResult:
    """Base scan result."""
    timestamp: datetime
    scanner_id: str
    device_id: str  # MAC address or other identifier
    rssi: float
    scanner_location: Optional[ScannerLocation] = None
    device_location: Optional[ScannerLocation] = None
    metadata: Optional[Dict[str, Any]] = None

class ScannerRegistry:
    """Registry for all scanners."""
    
    def __init__(self, config_dir: str = "/config"):
        """Initialize scanner registry."""
        self._config_dir = Path(config_dir)
        self._scanners_file = self._config_dir / "scanners.json"
        self._scanners: Dict[str, ScannerInfo] = {}
        self._callbacks: List[Callable] = []
        self._load_scanners()
        
    def _load_scanners(self):
        """Load scanner configurations."""
        try:
            if self._scanners_file.exists():
                with open(self._scanners_file, 'r') as f:
                    data = json.load(f)
                    for scanner_id, info in data.items():
                        location = info.get("location")
                        self._scanners[scanner_id] = ScannerInfo(
                            scanner_id=scanner_id,
                            scanner_type=info["scanner_type"],
                            is_mobile=info["is_mobile"],
                            location=ScannerLocation(
                                latitude=location["latitude"],
                                longitude=location["longitude"],
                                altitude=location.get("altitude"),
                                accuracy=location.get("accuracy"),
                                timestamp=datetime.fromisoformat(location["timestamp"]) if location.get("timestamp") else None,
                                source=location.get("source")
                            ) if location else None,
                            metadata=info.get("metadata")
                        )
                _LOGGER.info(f"Loaded {len(self._scanners)} scanners")
        except Exception as e:
            _LOGGER.error(f"Failed to load scanners: {str(e)}")
            
    def _save_scanners(self):
        """Save scanner configurations."""
        try:
            data = {
                scanner_id: {
                    "scanner_type": scanner.scanner_type,
                    "is_mobile": scanner.is_mobile,
                    "location": {
                        "latitude": scanner.location.latitude,
                        "longitude": scanner.location.longitude,
                        "altitude": scanner.location.altitude,
                        "accuracy": scanner.location.accuracy,
                        "timestamp": scanner.location.timestamp.isoformat() if scanner.location.timestamp else None,
                        "source": scanner.location.source
                    } if scanner.location else None,
                    "metadata": scanner.metadata
                }
                for scanner_id, scanner in self._scanners.items()
            }
            with open(self._scanners_file, 'w') as f:
                json.dump(data, f, indent=2)
            _LOGGER.info("Saved scanner configurations")
        except Exception as e:
            _LOGGER.error(f"Failed to save scanners: {str(e)}")
            
    def register_scanner(
        self,
        scanner_id: str,
        scanner_type: str,
        is_mobile: bool,
        location: Optional[ScannerLocation] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new scanner."""
        try:
            self._scanners[scanner_id] = ScannerInfo(
                scanner_id=scanner_id,
                scanner_type=scanner_type,
                is_mobile=is_mobile,
                location=location,
                metadata=metadata
            )
            self._save_scanners()
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to register scanner: {str(e)}")
            return False
            
    def update_scanner_location(
        self,
        scanner_id: str,
        location: ScannerLocation
    ) -> bool:
        """Update scanner location."""
        try:
            if scanner_id not in self._scanners:
                return False
                
            scanner = self._scanners[scanner_id]
            if not scanner.is_mobile and scanner.location:
                _LOGGER.warning(f"Attempting to update location of fixed scanner {scanner_id}")
                return False
                
            scanner.location = location
            self._save_scanners()
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to update scanner location: {str(e)}")
            return False
            
    def get_scanner(self, scanner_id: str) -> Optional[ScannerInfo]:
        """Get scanner information."""
        return self._scanners.get(scanner_id)
        
    def get_all_scanners(self) -> Dict[str, ScannerInfo]:
        """Get all registered scanners."""
        return self._scanners.copy()
        
    def add_callback(self, callback: Callable):
        """Add callback for scan results."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            
    def remove_callback(self, callback: Callable):
        """Remove callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    async def handle_scan_result(self, result: ScanResult):
        """Process scan result."""
        try:
            # Add scanner location if available
            scanner = self._scanners.get(result.scanner_id)
            if scanner and scanner.location:
                result.scanner_location = scanner.location
                
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    await callback(result)
                except Exception as e:
                    _LOGGER.error(f"Error in callback: {str(e)}")
                    
        except Exception as e:
            _LOGGER.error(f"Failed to handle scan result: {str(e)}")

class BaseScanner:
    """Base class for BLE and WiFi scanners."""
    
    def __init__(
        self,
        scanner_id: str,
        scanner_type: str,
        is_mobile: bool,
        registry: ScannerRegistry,
        location: Optional[ScannerLocation] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize scanner."""
        self._scanner_id = scanner_id
        self._scanner_type = scanner_type
        self._is_mobile = is_mobile
        self._registry = registry
        self._callbacks: List[Callable] = []
        
        # Register with registry
        self._registry.register_scanner(
            scanner_id=scanner_id,
            scanner_type=scanner_type,
            is_mobile=is_mobile,
            location=location,
            metadata=metadata
        )
        
    async def start(self):
        """Start scanner."""
        raise NotImplementedError
        
    async def stop(self):
        """Stop scanner."""
        raise NotImplementedError
        
    def add_callback(self, callback: Callable):
        """Add callback for scan results."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            
    def remove_callback(self, callback: Callable):
        """Remove callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    async def update_location(self, location: ScannerLocation) -> bool:
        """Update scanner location."""
        if not self._is_mobile:
            _LOGGER.warning(f"Attempting to update location of fixed scanner {self._scanner_id}")
            return False
            
        return self._registry.update_scanner_location(self._scanner_id, location)
        
    async def _handle_detection(self, result: ScanResult):
        """Handle device detection."""
        try:
            # Add to registry
            await self._registry.handle_scan_result(result)
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    await callback(result)
                except Exception as e:
                    _LOGGER.error(f"Error in callback: {str(e)}")
                    
        except Exception as e:
            _LOGGER.error(f"Failed to handle detection: {str(e)}") 