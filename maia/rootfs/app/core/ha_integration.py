"""
Home Assistant integration for MAIA.
"""
import asyncio
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urljoin

class HomeAssistantIntegration:
    """Integration with Home Assistant for device control and state management."""
    
    def __init__(
        self,
        host: str,
        token: str,
        port: int = 8123,
        use_ssl: bool = False,
        verify_ssl: bool = True
    ):
        """Initialize Home Assistant integration."""
        self.host = host
        self.token = token
        self.port = port
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self.logger = logging.getLogger(__name__)
        
        # Build base URL
        protocol = "https" if use_ssl else "http"
        self.base_url = f"{protocol}://{host}:{port}"
        
        # WebSocket connection
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.ws_task: Optional[asyncio.Task] = None
        self.message_id = 0
        self.message_callbacks: Dict[int, asyncio.Future] = {}
        
        # Session for REST API calls
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self) -> None:
        """Start the integration."""
        try:
            # Create HTTP session
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                }
            )
            
            # Connect WebSocket
            await self._connect_websocket()
            
            self.logger.info("Home Assistant integration started")
            
        except Exception as e:
            self.logger.error(f"Failed to start Home Assistant integration: {str(e)}")
            raise
            
    async def stop(self) -> None:
        """Stop the integration."""
        try:
            # Close WebSocket
            if self.ws:
                await self.ws.close()
                
            if self.ws_task:
                self.ws_task.cancel()
                try:
                    await self.ws_task
                except asyncio.CancelledError:
                    pass
                    
            # Close HTTP session
            if self.session:
                await self.session.close()
                
            self.logger.info("Home Assistant integration stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping Home Assistant integration: {str(e)}")
            
    async def _connect_websocket(self) -> None:
        """Connect to Home Assistant WebSocket API."""
        try:
            protocol = "wss" if self.use_ssl else "ws"
            ws_url = f"{protocol}://{self.host}:{self.port}/api/websocket"
            
            self.ws = await aiohttp.ClientSession().ws_connect(
                ws_url,
                ssl=self.verify_ssl if self.use_ssl else None
            )
            
            # Authenticate
            auth_msg = {
                "type": "auth",
                "access_token": self.token
            }
            await self.ws.send_json(auth_msg)
            
            # Start message handler
            self.ws_task = asyncio.create_task(self._handle_messages())
            
            self.logger.info("Connected to Home Assistant WebSocket API")
            
        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {str(e)}")
            raise
            
    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    
                    if msg_type == "auth_required":
                        continue
                        
                    if msg_type == "auth_ok":
                        self.logger.info("WebSocket authentication successful")
                        continue
                        
                    if msg_type == "auth_invalid":
                        self.logger.error("WebSocket authentication failed")
                        return
                        
                    # Handle response messages
                    msg_id = data.get("id")
                    if msg_id in self.message_callbacks:
                        future = self.message_callbacks.pop(msg_id)
                        if not future.done():
                            future.set_result(data)
                            
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket error: {msg.data}")
                    break
                    
        except asyncio.CancelledError:
            return
            
        except Exception as e:
            self.logger.error(f"Error handling WebSocket messages: {str(e)}")
            
        finally:
            # Reconnect if connection was lost
            if not self.ws.closed:
                await self.ws.close()
            await asyncio.sleep(5)
            await self._connect_websocket()
            
    async def _send_websocket_command(
        self,
        command: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send command through WebSocket API."""
        if not self.ws or self.ws.closed:
            await self._connect_websocket()
            
        self.message_id += 1
        msg = {
            "id": self.message_id,
            "type": command,
            **(data or {})
        }
        
        # Create future for response
        future = asyncio.Future()
        self.message_callbacks[self.message_id] = future
        
        # Send command
        await self.ws.send_json(msg)
        
        try:
            # Wait for response
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for command response: {command}")
            self.message_callbacks.pop(self.message_id, None)
            raise
            
    async def call_service(
        self,
        domain: str,
        service: str,
        target: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Call a Home Assistant service."""
        try:
            command_data = {
                "domain": domain,
                "service": service,
                "target": target or {},
                "service_data": data or {}
            }
            
            response = await self._send_websocket_command(
                "call_service",
                command_data
            )
            
            return response.get("success", False)
            
        except Exception as e:
            self.logger.error(f"Error calling service: {str(e)}")
            return False
            
    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity state."""
        try:
            if not self.session:
                return None
                
            url = urljoin(self.base_url, f"/api/states/{entity_id}")
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting state: {str(e)}")
            return None
            
    async def get_states(self) -> List[Dict[str, Any]]:
        """Get all entity states."""
        try:
            if not self.session:
                return []
                
            url = urljoin(self.base_url, "/api/states")
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return []
                
        except Exception as e:
            self.logger.error(f"Error getting states: {str(e)}")
            return []
            
    async def turn_on(
        self,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Turn on a device."""
        domain = entity_id.split(".")[0]
        return await self.call_service(
            domain,
            "turn_on",
            {"entity_id": entity_id},
            data
        )
        
    async def turn_off(
        self,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Turn off a device."""
        domain = entity_id.split(".")[0]
        return await self.call_service(
            domain,
            "turn_off",
            {"entity_id": entity_id},
            data
        )
        
    async def toggle(
        self,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Toggle a device."""
        domain = entity_id.split(".")[0]
        return await self.call_service(
            domain,
            "toggle",
            {"entity_id": entity_id},
            data
        )
        
    async def activate_scene(
        self,
        scene_id: str,
        transition: Optional[float] = None
    ) -> bool:
        """Activate a scene."""
        data = {"transition": transition} if transition is not None else None
        return await self.call_service(
            "scene",
            "turn_on",
            {"entity_id": scene_id},
            data
        )
        
    async def set_value(
        self,
        entity_id: str,
        value: Any,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Set entity value."""
        domain = entity_id.split(".")[0]
        service_data = {"value": value, **(data or {})}
        return await self.call_service(
            domain,
            "set_value",
            {"entity_id": entity_id},
            service_data
        )
        
    async def play_media(
        self,
        entity_id: str,
        media_id: str,
        media_type: str,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Play media on a media player."""
        service_data = {
            "media_content_id": media_id,
            "media_content_type": media_type,
            **(data or {})
        }
        return await self.call_service(
            "media_player",
            "play_media",
            {"entity_id": entity_id},
            service_data
        ) 