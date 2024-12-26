"""
ESP32 client module for MAIA.
Handles communication with ESP32 devices for audio streaming and device management.
"""
import asyncio
import websockets
import json
import numpy as np
from typing import Dict, List, Optional, Any, Callable
import logging
from datetime import datetime
import aiohttp
from ..utils.audio_utils import AudioPreprocessor
from ..utils.logging_utils import AsyncLogger

_LOGGER = logging.getLogger(__name__)

class ESP32Device:
    def __init__(self, device_id: str, ip_address: str, capabilities: List[str]):
        self.device_id = device_id
        self.ip_address = ip_address
        self.capabilities = capabilities
        self.last_seen = datetime.now()
        self.status = "offline"
        self.audio_stream = None
        self.websocket = None

class ESP32Client:
    def __init__(self):
        self.devices: Dict[str, ESP32Device] = {}
        self.logger = AsyncLogger(__name__)
        self.audio_preprocessor = AudioPreprocessor()
        
        # Connection settings
        self.reconnect_interval = 5  # seconds
        self.ping_interval = 30  # seconds
        self.stream_chunk_size = 1024
        
        # Callbacks
        self.audio_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []

    async def register_device(self, device_id: str, ip_address: str,
                            capabilities: List[str]) -> bool:
        """
        Register a new ESP32 device.
        
        Args:
            device_id: Unique device identifier
            ip_address: Device IP address
            capabilities: List of device capabilities
            
        Returns:
            bool indicating success
        """
        try:
            device = ESP32Device(device_id, ip_address, capabilities)
            self.devices[device_id] = device
            
            # Log registration
            await self.logger.async_log_interaction(
                component="ESP32Client",
                action="register_device",
                input_data={
                    "device_id": device_id,
                    "ip_address": ip_address,
                    "capabilities": capabilities
                },
                output_data={"status": "registered"}
            )
            
            # Start device management tasks
            asyncio.create_task(self._manage_device_connection(device))
            
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error registering device: {str(e)}")
            return False

    async def start_audio_stream(self, device_id: str) -> bool:
        """
        Start audio streaming from a device.
        
        Args:
            device_id: Device to stream from
            
        Returns:
            bool indicating success
        """
        try:
            device = self.devices.get(device_id)
            if not device:
                _LOGGER.error(f"Device {device_id} not found")
                return False
                
            if "audio" not in device.capabilities:
                _LOGGER.error(f"Device {device_id} does not support audio")
                return False
                
            # Send stream start command
            if device.websocket:
                await device.websocket.send(json.dumps({
                    "command": "start_audio_stream",
                    "params": {
                        "sample_rate": self.audio_preprocessor.sample_rate,
                        "chunk_size": self.stream_chunk_size
                    }
                }))
                
                device.audio_stream = True
                return True
                
            return False
            
        except Exception as e:
            _LOGGER.error(f"Error starting audio stream: {str(e)}")
            return False

    async def stop_audio_stream(self, device_id: str) -> bool:
        """Stop audio streaming from a device."""
        try:
            device = self.devices.get(device_id)
            if not device or not device.websocket:
                return False
                
            await device.websocket.send(json.dumps({
                "command": "stop_audio_stream"
            }))
            
            device.audio_stream = False
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error stopping audio stream: {str(e)}")
            return False

    def register_audio_callback(self, callback: Callable[[str, np.ndarray], None]) -> None:
        """Register callback for audio data."""
        self.audio_callbacks.append(callback)

    def register_status_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for device status changes."""
        self.status_callbacks.append(callback)

    async def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a device."""
        try:
            device = self.devices.get(device_id)
            if not device:
                return None
                
            return {
                "device_id": device.device_id,
                "ip_address": device.ip_address,
                "status": device.status,
                "capabilities": device.capabilities,
                "last_seen": device.last_seen.isoformat(),
                "streaming": bool(device.audio_stream)
            }
            
        except Exception as e:
            _LOGGER.error(f"Error getting device status: {str(e)}")
            return None

    async def _manage_device_connection(self, device: ESP32Device) -> None:
        """Manage connection to a device."""
        while True:
            try:
                uri = f"ws://{device.ip_address}/ws"
                async with websockets.connect(uri) as websocket:
                    device.websocket = websocket
                    device.status = "online"
                    self._notify_status_change(device.device_id, "online")
                    
                    # Start ping task
                    ping_task = asyncio.create_task(
                        self._ping_device(device)
                    )
                    
                    try:
                        await self._handle_device_messages(device)
                    finally:
                        ping_task.cancel()
                        
            except Exception as e:
                _LOGGER.error(f"Device connection error: {str(e)}")
                device.status = "offline"
                device.websocket = None
                self._notify_status_change(device.device_id, "offline")
                
            # Wait before reconnecting
            await asyncio.sleep(self.reconnect_interval)

    async def _handle_device_messages(self, device: ESP32Device) -> None:
        """Handle incoming messages from device."""
        try:
            while True:
                message = await device.websocket.recv()
                
                try:
                    # Try to parse as JSON first
                    data = json.loads(message)
                    await self._handle_json_message(device, data)
                except json.JSONDecodeError:
                    # Handle as binary audio data
                    if device.audio_stream:
                        await self._handle_audio_data(device, message)
                        
        except websockets.ConnectionClosed:
            _LOGGER.info(f"Device {device.device_id} connection closed")
            
        except Exception as e:
            _LOGGER.error(f"Error handling device messages: {str(e)}")

    async def _handle_json_message(self, device: ESP32Device,
                                 data: Dict[str, Any]) -> None:
        """Handle JSON message from device."""
        try:
            message_type = data.get("type")
            
            if message_type == "status":
                device.status = data.get("status", "unknown")
                self._notify_status_change(device.device_id, device.status)
                
            elif message_type == "error":
                await self.logger.async_log_error(
                    component="ESP32Client",
                    action="device_error",
                    error=data.get("error", "Unknown error"),
                    context={"device_id": device.device_id}
                )
                
        except Exception as e:
            _LOGGER.error(f"Error handling JSON message: {str(e)}")

    async def _handle_audio_data(self, device: ESP32Device,
                               audio_data: bytes) -> None:
        """Handle audio data from device."""
        try:
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            
            # Notify callbacks
            for callback in self.audio_callbacks:
                try:
                    callback(device.device_id, audio_array)
                except Exception as e:
                    _LOGGER.error(f"Error in audio callback: {str(e)}")
                    
        except Exception as e:
            _LOGGER.error(f"Error handling audio data: {str(e)}")

    async def _ping_device(self, device: ESP32Device) -> None:
        """Send periodic pings to keep connection alive."""
        try:
            while True:
                if device.websocket:
                    await device.websocket.ping()
                    device.last_seen = datetime.now()
                await asyncio.sleep(self.ping_interval)
                
        except Exception as e:
            _LOGGER.error(f"Error pinging device: {str(e)}")

    def _notify_status_change(self, device_id: str, status: str) -> None:
        """Notify status callbacks of device status change."""
        for callback in self.status_callbacks:
            try:
                callback(device_id, status)
            except Exception as e:
                _LOGGER.error(f"Error in status callback: {str(e)}")

    async def close(self) -> None:
        """Close all device connections."""
        for device in self.devices.values():
            if device.websocket:
                await device.websocket.close()
                device.status = "offline"
                device.websocket = None 