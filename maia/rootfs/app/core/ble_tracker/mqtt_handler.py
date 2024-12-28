"""
MQTT handler for BLE tracking.
Receives and processes BLE scan data from ESP32 devices.
"""
from typing import Dict, List, Optional, Any, Callable
import logging
import json
import asyncio
from datetime import datetime
import aiomqtt
from .database import BLEDatabase
from .position_calculator import PositionCalculator

_LOGGER = logging.getLogger(__name__)

class BLEMQTTHandler:
    """MQTT handler for BLE tracking."""
    
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        database: BLEDatabase,
        position_calculator: PositionCalculator,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """Initialize MQTT handler."""
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.database = database
        self.position_calculator = position_calculator
        self.client: Optional[aiomqtt.Client] = None
        self.running = False
        self.message_handlers: Dict[str, Callable] = {
            "ble_scanner/+/data": self._handle_scanner_data,
            "ble_scanner/+/status": self._handle_scanner_status,
            "ble_scanner/+/calibration": self._handle_calibration_data
        }
        
    async def start(self):
        """Start MQTT handler."""
        try:
            # Create MQTT client
            self.client = aiomqtt.Client(
                hostname=self.broker_host,
                port=self.broker_port,
                username=self.username,
                password=self.password,
                keepalive=60
            )
            
            # Set up callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Connect to broker
            await self.client.connect()
            self.running = True
            
            # Start processing loop
            asyncio.create_task(self._process_loop())
            _LOGGER.info("MQTT handler started")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start MQTT handler: {str(e)}")
            raise
            
    async def stop(self):
        """Stop MQTT handler."""
        self.running = False
        if self.client:
            await self.client.disconnect()
            
    async def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                await asyncio.sleep(0.1)  # Prevent CPU hogging
            except Exception as e:
                _LOGGER.error(f"Error in process loop: {str(e)}")
                await asyncio.sleep(1)
                
    async def _on_connect(self, client, userdata, flags, rc):
        """Handle connection established."""
        try:
            # Subscribe to all relevant topics
            for topic in self.message_handlers.keys():
                await self.client.subscribe(topic)
                
            _LOGGER.info("Connected to MQTT broker")
            
        except Exception as e:
            _LOGGER.error(f"Error in on_connect: {str(e)}")
            
    async def _on_disconnect(self, client, userdata, rc):
        """Handle disconnection."""
        _LOGGER.warning(f"Disconnected from MQTT broker with code: {rc}")
        
    async def _on_message(self, client, userdata, message):
        """Handle incoming MQTT message."""
        try:
            # Get topic handler
            for pattern, handler in self.message_handlers.items():
                if aiomqtt.topic_matches_sub(pattern, message.topic):
                    await handler(message)
                    break
                    
        except Exception as e:
            _LOGGER.error(f"Error processing message: {str(e)}")
            
    async def _handle_scanner_data(self, message):
        """Handle BLE scan data from ESP32."""
        try:
            # Parse message
            payload = json.loads(message.payload)
            scanner_id = message.topic.split('/')[1]
            
            # Store reading
            await self.database.store_ble_reading(
                scanner_id=scanner_id,
                device_mac=payload["device_mac"],
                rssi=payload["rssi"],
                device_name=payload.get("device_name"),
                metadata=payload.get("metadata")
            )
            
            # Get recent readings for position calculation
            readings = await self.database.get_recent_readings(
                device_mac=payload["device_mac"]
            )
            
            if len(readings) >= 3:  # Need at least 3 points for trilateration
                # Calculate position
                position = await self.position_calculator.calculate_position(readings)
                
                if position:
                    # Store calculated position
                    await self.database.store_device_position(
                        device_mac=payload["device_mac"],
                        x=position["x"],
                        y=position["y"],
                        z=position["z"],
                        accuracy=position["accuracy"],
                        source_readings={
                            "readings": readings,
                            "calculation_method": position["method"]
                        }
                    )
                    
        except Exception as e:
            _LOGGER.error(f"Error handling scanner data: {str(e)}")
            
    async def _handle_scanner_status(self, message):
        """Handle scanner status updates."""
        try:
            # Parse message
            payload = json.loads(message.payload)
            scanner_id = message.topic.split('/')[1]
            
            # Update scanner location if provided
            if "location" in payload:
                loc = payload["location"]
                await self.database.store_scanner_location(
                    scanner_id=scanner_id,
                    x=loc["x"],
                    y=loc["y"],
                    z=loc["z"],
                    metadata={
                        "status": payload.get("status"),
                        "version": payload.get("version"),
                        "uptime": payload.get("uptime"),
                        "last_update": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            _LOGGER.error(f"Error handling scanner status: {str(e)}")
            
    async def _handle_calibration_data(self, message):
        """Handle calibration data."""
        try:
            # Parse message
            payload = json.loads(message.payload)
            scanner_id = message.topic.split('/')[1]
            
            if "reference_point" in payload:
                point = payload["reference_point"]
                await self.database.store_calibration_point(
                    x=point["x"],
                    y=point["y"],
                    z=point["z"],
                    reference_device=payload["reference_device"],
                    readings=payload["readings"]
                )
                
                # Recalibrate position calculator
                calibration_points = await self.database.get_calibration_points(
                    reference_device=payload["reference_device"]
                )
                await self.position_calculator.calibrate(calibration_points)
                
        except Exception as e:
            _LOGGER.error(f"Error handling calibration data: {str(e)}")
            
    async def publish_scanner_config(
        self,
        scanner_id: str,
        config: Dict[str, Any]
    ) -> bool:
        """Publish configuration to scanner."""
        try:
            if not self.client:
                return False
                
            # Publish config
            await self.client.publish(
                f"ble_scanner/{scanner_id}/config",
                json.dumps(config),
                qos=1,
                retain=True
            )
            return True
            
        except Exception as e:
            _LOGGER.error(f"Error publishing scanner config: {str(e)}")
            return False 