"""
WebSocket handler module for MAIA.
Handles real-time communication with web clients and ESP32 devices.
"""
import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Set, Deque
from collections import deque
import websockets
from datetime import datetime, timedelta
from ..utils.logging_utils import AsyncLogger
from ..core.voice_processor import VoiceProcessor
from ..core.camera_processor import CameraProcessor

_LOGGER = logging.getLogger(__name__)

class WebSocketHandler:
    def __init__(self, hass, config: Dict[str, Any]):
        self.hass = hass
        self.config = config
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.devices: Dict[str, 'ESP32Device'] = {}
        self.voice_processor = VoiceProcessor(config.get('voice', {}))
        self.camera_processor = CameraProcessor(config.get('camera', {}))
        self.message_queue: Dict[str, Deque[Dict[str, Any]]] = {}
        self.reconnect_attempts: Dict[str, int] = {}
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # seconds
        self.message_timeout = 30  # seconds
        self._cleanup_task = None
        self._logger = AsyncLogger(__name__)

    async def start(self):
        """Start the WebSocket server and background tasks."""
        try:
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            await self._start_server()
        except Exception as e:
            self._logger.error(f"Failed to start WebSocket handler: {e}")
            raise

    async def stop(self):
        """Stop the WebSocket server and cleanup."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        await self._disconnect_all_clients()
        await self._cleanup_resources()

    async def _start_server(self):
        """Start the WebSocket server."""
        try:
            server = await websockets.serve(
                self._handle_client,
                self.config.get('host', '0.0.0.0'),
                self.config.get('port', 8765),
                ping_interval=30,
                ping_timeout=10
            )
            self._logger.info("WebSocket server started successfully")
            return server
        except Exception as e:
            self._logger.error(f"Failed to start WebSocket server: {e}")
            raise

    async def _handle_client(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle new client connections."""
        client_id = None
        try:
            # Perform authentication
            auth_message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_data = json.loads(auth_message)
            
            if not await self._authenticate_client(auth_data):
                await websocket.close(1008, "Authentication failed")
                return

            client_id = auth_data.get('client_id')
            self.clients[client_id] = websocket
            self.message_queue[client_id] = deque(maxlen=100)
            
            self._logger.info(f"Client {client_id} connected")
            
            # Process any queued messages
            await self._process_queued_messages(client_id)
            
            # Handle incoming messages
            async for message in websocket:
                await self._process_message(client_id, message)
                
        except asyncio.TimeoutError:
            self._logger.warning(f"Client {client_id} authentication timeout")
        except websockets.exceptions.ConnectionClosed:
            self._logger.info(f"Client {client_id} connection closed")
        except Exception as e:
            self._logger.error(f"Error handling client {client_id}: {e}")
        finally:
            if client_id:
                await self._handle_client_disconnect(client_id)

    async def _authenticate_client(self, auth_data: Dict[str, Any]) -> bool:
        """Authenticate a client connection."""
        try:
            client_type = auth_data.get('type')
            auth_token = auth_data.get('token')
            
            if client_type == 'device':
                return await self._authenticate_device(auth_data)
            elif client_type == 'web':
                return await self._authenticate_web_client(auth_token)
            else:
                self._logger.warning(f"Unknown client type: {client_type}")
                return False
                
        except Exception as e:
            self._logger.error(f"Authentication error: {e}")
            return False

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        """Send a message to a client with queuing and retry logic."""
        try:
            if client_id not in self.clients:
                self.message_queue[client_id].append(message)
                return

            websocket = self.clients[client_id]
            try:
                await websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                self.message_queue[client_id].append(message)
                await self._handle_client_disconnect(client_id)
                await self._attempt_reconnect(client_id)
                
        except Exception as e:
            self._logger.error(f"Error sending message to {client_id}: {e}")
            self.message_queue[client_id].append(message)

    async def broadcast_message(self, message: Dict[str, Any], exclude: Optional[Set[str]] = None):
        """Broadcast a message to all connected clients except excluded ones."""
        exclude = exclude or set()
        tasks = []
        
        for client_id, websocket in self.clients.items():
            if client_id not in exclude:
                tasks.append(self.send_message(client_id, message))
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_message(self, client_id: str, message: str):
        """Process incoming messages from clients."""
        try:
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type == 'face_detection':
                await self.camera_processor.handle_face_detection(data)
            elif message_type == 'voice_command':
                await self.voice_processor.handle_voice_command(data)
            elif message_type == 'device_status':
                await self._handle_device_status(client_id, data)
            else:
                self._logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            self._logger.error(f"Invalid JSON from client {client_id}")
        except Exception as e:
            self._logger.error(f"Error processing message from {client_id}: {e}")

    async def _handle_client_disconnect(self, client_id: str):
        """Handle client disconnection."""
        try:
            if client_id in self.clients:
                await self.clients[client_id].close()
                del self.clients[client_id]
                
            if client_id in self.devices:
                self.devices[client_id].status = "offline"
                await self._notify_device_status_change(client_id)
                
        except Exception as e:
            self._logger.error(f"Error handling disconnect for {client_id}: {e}")

    async def _attempt_reconnect(self, client_id: str):
        """Attempt to reconnect to a client."""
        if client_id not in self.reconnect_attempts:
            self.reconnect_attempts[client_id] = 0
            
        while self.reconnect_attempts[client_id] < self.max_reconnect_attempts:
            try:
                self.reconnect_attempts[client_id] += 1
                await asyncio.sleep(self.reconnect_delay)
                
                if client_id in self.devices:
                    await self._reconnect_device(client_id)
                    
                self.reconnect_attempts[client_id] = 0
                break
                
            except Exception as e:
                self._logger.error(f"Reconnection attempt {self.reconnect_attempts[client_id]} failed for {client_id}: {e}")
                
        if self.reconnect_attempts[client_id] >= self.max_reconnect_attempts:
            self._logger.warning(f"Max reconnection attempts reached for {client_id}")
            del self.reconnect_attempts[client_id]

    async def _periodic_cleanup(self):
        """Periodically clean up resources and check client health."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_stale_messages()
                await self._check_client_health()
                await self._cleanup_disconnected_clients()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in periodic cleanup: {e}")

    async def _cleanup_stale_messages(self):
        """Clean up stale messages from the message queues."""
        now = datetime.now()
        timeout = timedelta(seconds=self.message_timeout)
        
        for client_id, queue in self.message_queue.items():
            while queue and queue[0].get('timestamp', now) + timeout < now:
                queue.popleft()

    async def _check_client_health(self):
        """Check the health of connected clients."""
        for client_id, websocket in list(self.clients.items()):
            try:
                pong_waiter = await websocket.ping()
                await asyncio.wait_for(pong_waiter, timeout=5)
            except Exception:
                await self._handle_client_disconnect(client_id)
                await self._attempt_reconnect(client_id)

    async def _cleanup_disconnected_clients(self):
        """Clean up resources for disconnected clients."""
        for client_id in list(self.clients.keys()):
            if not self.clients[client_id].open:
                await self._handle_client_disconnect(client_id)

    async def _cleanup_resources(self):
        """Clean up all resources when stopping the handler."""
        try:
            await self._disconnect_all_clients()
            self.message_queue.clear()
            self.reconnect_attempts.clear()
            self.devices.clear()
            
        except Exception as e:
            self._logger.error(f"Error cleaning up resources: {e}")

    async def _disconnect_all_clients(self):
        """Disconnect all connected clients."""
        disconnect_tasks = []
        for client_id in list(self.clients.keys()):
            disconnect_tasks.append(self._handle_client_disconnect(client_id))
            
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True) 