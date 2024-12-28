"""
Home Assistant location handler for MAIA.
Handles high-precision GPS data from HA mobile app.
"""
import logging
from typing import Dict, Optional, Any, Callable, List
import json
import asyncio
from datetime import datetime
import aiohttp
from urllib.parse import urljoin

_LOGGER = logging.getLogger(__name__)

class HALocation:
    """Handles location data from Home Assistant."""
    
    def __init__(self, ha_url: str, ha_token: str):
        """Initialize HA location handler."""
        self._ha_url = ha_url.rstrip('/')
        self._ha_token = ha_token
        self._headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json",
        }
        self._ws_client = None
        self._ws_task = None
        self._callbacks: List[Callable] = []
        self._user_locations: Dict[str, Dict[str, Any]] = {}
        
    async def start(self):
        """Start location handler."""
        try:
            # Start WebSocket connection
            self._ws_task = asyncio.create_task(self._websocket_listener())
            _LOGGER.info("HA location handler started")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to start HA location handler: {str(e)}")
            return False
            
    async def stop(self):
        """Stop location handler."""
        try:
            if self._ws_task:
                self._ws_task.cancel()
                try:
                    await self._ws_task
                except asyncio.CancelledError:
                    pass
            if self._ws_client:
                await self._ws_client.close()
            _LOGGER.info("HA location handler stopped")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to stop HA location handler: {str(e)}")
            return False
            
    def add_callback(self, callback: Callable):
        """Add callback for location updates."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
            
    def remove_callback(self, callback: Callable):
        """Remove callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            
    async def _websocket_listener(self):
        """Listen for WebSocket messages."""
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    ws_url = urljoin(self._ha_url, "api/websocket")
                    async with session.ws_connect(ws_url) as ws:
                        self._ws_client = ws
                        
                        # Authenticate
                        auth_msg = {
                            "type": "auth",
                            "access_token": self._ha_token
                        }
                        await ws.send_json(auth_msg)
                        
                        # Subscribe to location updates
                        sub_msg = {
                            "id": 1,
                            "type": "subscribe_events",
                            "event_type": "mobile_app_location_update"
                        }
                        await ws.send_json(sub_msg)
                        
                        # Handle messages
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await self._handle_message(msg.json())
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
                                
            except asyncio.CancelledError:
                break
            except Exception as e:
                _LOGGER.error(f"WebSocket error: {str(e)}")
                await asyncio.sleep(5)  # Retry delay
                
    async def _handle_message(self, msg: Dict[str, Any]):
        """Handle WebSocket message."""
        try:
            if msg.get("type") == "event" and msg.get("event", {}).get("event_type") == "mobile_app_location_update":
                data = msg["event"]["data"]
                
                # Extract location data
                location_info = {
                    "user_id": data.get("user_id"),
                    "device_id": data.get("device_id"),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "accuracy": data.get("gps_accuracy"),
                    "altitude": data.get("altitude"),
                    "speed": data.get("speed"),
                    "bearing": data.get("bearing"),
                    "timestamp": datetime.now(),
                    "source": "ha_mobile_app"
                }
                
                # Update user locations
                user_id = data.get("user_id")
                if user_id:
                    self._user_locations[user_id] = location_info
                    
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        await callback(location_info)
                    except Exception as e:
                        _LOGGER.error(f"Error in callback: {str(e)}")
                        
        except Exception as e:
            _LOGGER.error(f"Error handling message: {str(e)}")
            
    def get_user_location(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get latest location for user."""
        return self._user_locations.get(user_id)
        
    def get_all_locations(self) -> Dict[str, Dict[str, Any]]:
        """Get all user locations."""
        return self._user_locations.copy()
        
    async def request_location_update(self, user_id: str) -> bool:
        """Request immediate location update from user's device."""
        try:
            async with aiohttp.ClientSession(headers=self._headers) as session:
                url = urljoin(self._ha_url, f"api/services/mobile_app/request_location_update")
                data = {"user_id": user_id}
                async with session.post(url, json=data) as response:
                    return response.status == 200
        except Exception as e:
            _LOGGER.error(f"Failed to request location update: {str(e)}")
            return False 