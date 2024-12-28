"""
BLE scanner for MAIA.
Handles Bluetooth Low Energy scanning.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import bleak
from .scanner_base import BaseScanner, ScannerRegistry, ScanResult, ScannerLocation

_LOGGER = logging.getLogger(__name__)

class BLEScanner(BaseScanner):
    """Handles BLE scanning."""
    
    def __init__(
        self,
        scanner_id: str,
        registry: ScannerRegistry,
        is_mobile: bool = False,
        location: Optional[ScannerLocation] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize BLE scanner."""
        super().__init__(
            scanner_id=scanner_id,
            scanner_type="ble",
            is_mobile=is_mobile,
            registry=registry,
            location=location,
            metadata=metadata
        )
        self._scanner = None
        self._scanning = False
        
    async def start(self):
        """Start BLE scanning."""
        try:
            if self._scanning:
                return True
                
            # Check if Bluetooth adapter is available
            adapters = await bleak.discover_bluetooth_adapters()
            if not adapters:
                _LOGGER.warning("No Bluetooth adapters found")
                return False
                
            self._scanner = bleak.BleakScanner()
            self._scanner.register_detection_callback(self._device_detected)
            
            # Start scanning
            await self._scanner.start()
            self._scanning = True
            _LOGGER.info(f"BLE scanner {self._scanner_id} started")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to start BLE scanner: {str(e)}")
            return False
            
    async def stop(self):
        """Stop BLE scanning."""
        try:
            if self._scanner and self._scanning:
                await self._scanner.stop()
                self._scanning = False
                _LOGGER.info(f"BLE scanner {self._scanner_id} stopped")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to stop BLE scanner: {str(e)}")
            return False
            
    async def _device_detected(self, device, advertisement_data):
        """Handle detected BLE device."""
        try:
            # Create scan result
            result = ScanResult(
                timestamp=datetime.now(),
                scanner_id=self._scanner_id,
                device_id=device.address,
                rssi=advertisement_data.rssi,
                metadata={
                    "name": advertisement_data.local_name or device.name or "Unknown",
                    "manufacturer_data": advertisement_data.manufacturer_data,
                    "service_data": advertisement_data.service_data,
                    "service_uuids": advertisement_data.service_uuids
                }
            )
            
            # Process result
            await self._handle_detection(result)
            
        except Exception as e:
            _LOGGER.error(f"Error processing device detection: {str(e)}") 