"""
Companion service detector for MAIA.
Handles auto-detection and initialization of companion GPU services.
"""
import logging
import asyncio
import aiohttp
import uuid
from typing import Dict, Optional, Any, List, Callable
from datetime import datetime
from urllib.parse import urljoin
from dataclasses import dataclass, asdict
import json

from .logging import get_logger

_LOGGER = logging.getLogger(__name__)

@dataclass
class StreamConfig:
    url: str
    type: str
    auth_type: str = "none"
    auth_data: Optional[Dict[str, str]] = None

@dataclass
class CompanionDevice:
    id: str
    name: str
    type: str
    status: str = "unknown"
    room: Optional[str] = None
    capabilities: List[str] = None
    last_seen: Optional[datetime] = None
    stream_config: Optional[StreamConfig] = None
    data: Dict[str, Any] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.data is None:
            self.data = {}

class CompanionManager:
    def __init__(self):
        self.devices: Dict[str, CompanionDevice] = {}
        self.logger = get_logger(__name__)
        self._discovery_task = None
        self._health_check_task = None

    async def start(self):
        """Start the companion manager."""
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop(self):
        """Stop the companion manager."""
        if self._discovery_task:
            self._discovery_task.cancel()
        if self._health_check_task:
            self._health_check_task.cancel()
        try:
            await asyncio.gather(self._discovery_task, self._health_check_task)
        except asyncio.CancelledError:
            pass

    async def register_external_stream(
        self, 
        name: str, 
        url: str, 
        stream_type: str,
        auth_type: str = "none",
        auth_data: Optional[Dict[str, str]] = None
    ) -> CompanionDevice:
        """Register a new external stream."""
        device_id = str(uuid.uuid4())
        stream_config = StreamConfig(
            url=url,
            type=stream_type,
            auth_type=auth_type,
            auth_data=auth_data
        )
        
        device = CompanionDevice(
            id=device_id,
            name=name,
            type="external",
            capabilities=[stream_type],
            stream_config=stream_config
        )
        
        # Check stream health before adding
        health = await self._check_stream_health(device)
        device.status = health["status"]
        device.last_seen = datetime.now() if health["status"] == "online" else None
        
        self.devices[device_id] = device
        self.logger.info(f"Registered external stream {name} with ID {device_id}")
        return device

    async def update_external_stream(
        self,
        stream_id: str,
        name: Optional[str] = None,
        url: Optional[str] = None,
        stream_type: Optional[str] = None,
        auth_type: Optional[str] = None,
        auth_data: Optional[Dict[str, str]] = None
    ) -> CompanionDevice:
        """Update an external stream's configuration."""
        if stream_id not in self.devices:
            raise ValueError(f"Stream {stream_id} not found")
        
        device = self.devices[stream_id]
        if device.type != "external":
            raise ValueError(f"Device {stream_id} is not an external stream")
        
        if name:
            device.name = name
        if url:
            device.stream_config.url = url
        if stream_type:
            device.stream_config.type = stream_type
            device.capabilities = [stream_type]
        if auth_type:
            device.stream_config.auth_type = auth_type
        if auth_data:
            device.stream_config.auth_data = auth_data
        
        # Check stream health after update
        health = await self._check_stream_health(device)
        device.status = health["status"]
        device.last_seen = datetime.now() if health["status"] == "online" else None
        
        self.logger.info(f"Updated external stream {stream_id}")
        return device

    async def remove_external_stream(self, stream_id: str):
        """Remove an external stream."""
        if stream_id not in self.devices:
            raise ValueError(f"Stream {stream_id} not found")
        
        device = self.devices[stream_id]
        if device.type != "external":
            raise ValueError(f"Device {stream_id} is not an external stream")
        
        del self.devices[stream_id]
        self.logger.info(f"Removed external stream {stream_id}")

    async def get_external_streams(self) -> List[CompanionDevice]:
        """Get all registered external streams."""
        return [d for d in self.devices.values() if d.type == "external"]

    async def get_external_stream(self, stream_id: str) -> Optional[CompanionDevice]:
        """Get a specific external stream."""
        device = self.devices.get(stream_id)
        if device and device.type == "external":
            return device
        return None

    async def check_external_stream_health(self, stream_id: str) -> Dict[str, Any]:
        """Check the health of an external stream."""
        if stream_id not in self.devices:
            raise ValueError(f"Stream {stream_id} not found")
        
        device = self.devices[stream_id]
        if device.type != "external":
            raise ValueError(f"Device {stream_id} is not an external stream")
        
        health = await self._check_stream_health(device)
        device.status = health["status"]
        device.last_seen = datetime.now() if health["status"] == "online" else None
        
        return health

    async def _check_stream_health(self, device: CompanionDevice) -> Dict[str, Any]:
        """Check the health of a stream."""
        if not device.stream_config:
            return {
                "status": "error",
                "error_message": "No stream configuration"
            }
        
        headers = {}
        if device.stream_config.auth_type == "basic":
            auth = aiohttp.BasicAuth(
                login=device.stream_config.auth_data.get("username", ""),
                password=device.stream_config.auth_data.get("password", "")
            )
        elif device.stream_config.auth_type == "token":
            headers["Authorization"] = f"Bearer {device.stream_config.auth_data.get('token', '')}"
        
        try:
            start_time = datetime.now()
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    device.stream_config.url,
                    headers=headers,
                    auth=auth if device.stream_config.auth_type == "basic" else None,
                    timeout=5
                ) as response:
                    end_time = datetime.now()
                    response_time = (end_time - start_time).total_seconds()
                    
                    if response.status == 200:
                        return {
                            "status": "online",
                            "response_time": response_time,
                            "last_checked": end_time
                        }
                    else:
                        return {
                            "status": "error",
                            "error_message": f"HTTP {response.status}",
                            "response_time": response_time,
                            "last_checked": end_time
                        }
        except Exception as e:
            return {
                "status": "error",
                "error_message": str(e),
                "last_checked": datetime.now()
            }

    async def _discovery_loop(self):
        """Main discovery loop for companion devices."""
        while True:
            try:
                # Discover ESP32 devices via BLE and WiFi
                await self._discover_devices()
                # Update device status
                await self._update_device_status()
            except Exception as e:
                self.logger.error(f"Error in discovery loop: {e}")
            await asyncio.sleep(30)  # Run discovery every 30 seconds

    async def _health_check_loop(self):
        """Health check loop for external streams."""
        while True:
            try:
                for device in self.get_external_streams():
                    health = await self._check_stream_health(device)
                    device.status = health["status"]
                    device.last_seen = datetime.now() if health["status"] == "online" else None
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
            await asyncio.sleep(60)  # Check health every minute

    async def _discover_devices(self):
        """Discover ESP32 devices."""
        # Implementation for discovering ESP32 devices via BLE and WiFi
        pass

    async def _update_device_status(self):
        """Update status of all devices."""
        # Implementation for updating device status
        pass 