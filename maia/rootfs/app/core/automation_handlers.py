"""
Event and action handlers for the automation engine.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime, time
import aiohttp
from .automation_engine import AutomationEvent
from .ha_integration import HomeAssistantIntegration

_LOGGER = logging.getLogger(__name__)

# Initialize Home Assistant integration
ha_integration: Optional[HomeAssistantIntegration] = None

def init_ha_integration(
    host: str,
    token: str,
    port: int = 8123,
    use_ssl: bool = False
) -> None:
    """Initialize Home Assistant integration."""
    global ha_integration
    ha_integration = HomeAssistantIntegration(
        host=host,
        token=token,
        port=port,
        use_ssl=use_ssl
    )

# Event handlers
async def handle_face_detection(event: AutomationEvent) -> None:
    """Handle face detection events."""
    try:
        face_data = event.data.get("face", {})
        _LOGGER.info(
            f"Face detected",
            extra={
                "bbox": face_data.get("bbox"),
                "confidence": face_data.get("confidence")
            }
        )
        
        # Update presence sensor if configured
        if ha_integration:
            await ha_integration.set_value(
                "binary_sensor.face_detected",
                True,
                {
                    "confidence": face_data.get("confidence", 0.0),
                    "bbox": face_data.get("bbox")
                }
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling face detection: {str(e)}")

async def handle_face_recognition(event: AutomationEvent) -> None:
    """Handle face recognition events."""
    try:
        face_data = event.data.get("face", {})
        name = face_data.get("name", "unknown")
        confidence = face_data.get("confidence", 0.0)
        
        _LOGGER.info(
            f"Face recognized: {name}",
            extra={
                "name": name,
                "confidence": confidence,
                "bbox": face_data.get("bbox")
            }
        )
        
        # Update presence sensors if configured
        if ha_integration:
            # Update person presence
            await ha_integration.set_value(
                f"binary_sensor.presence_{name.lower()}",
                True,
                {
                    "confidence": confidence,
                    "last_seen": datetime.now().isoformat()
                }
            )
            
            # Update last recognized face
            await ha_integration.set_value(
                "sensor.last_recognized_face",
                name,
                {
                    "confidence": confidence,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling face recognition: {str(e)}")

async def handle_voice_command(event: AutomationEvent) -> None:
    """Handle voice command events."""
    try:
        command_data = event.data.get("command", {})
        text = command_data.get("text", "")
        intent = command_data.get("intent", "")
        
        _LOGGER.info(
            f"Voice command received",
            extra={
                "text": text,
                "intent": intent,
                "slots": command_data.get("slots", {})
            }
        )
        
        # Update voice command sensor if configured
        if ha_integration:
            await ha_integration.set_value(
                "sensor.last_voice_command",
                text,
                {
                    "intent": intent,
                    "slots": command_data.get("slots", {}),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling voice command: {str(e)}")

async def handle_device_detection(event: AutomationEvent) -> None:
    """Handle device detection events."""
    try:
        device_data = event.data.get("device", {})
        device_id = device_data.get("id")
        rssi = device_data.get("rssi")
        
        _LOGGER.info(
            f"Device detected",
            extra={
                "device_id": device_id,
                "rssi": rssi,
                "scanner_id": device_data.get("scanner_id")
            }
        )
        
        # Update device tracker if configured
        if ha_integration and device_id:
            await ha_integration.set_value(
                f"device_tracker.{device_id}",
                "home",
                {
                    "rssi": rssi,
                    "scanner_id": device_data.get("scanner_id"),
                    "last_seen": datetime.now().isoformat()
                }
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling device detection: {str(e)}")

async def handle_position_update(event: AutomationEvent) -> None:
    """Handle device position update events."""
    try:
        position_data = event.data.get("position", {})
        device_id = position_data.get("device_id")
        
        _LOGGER.info(
            f"Device position updated",
            extra={
                "device_id": device_id,
                "latitude": position_data.get("latitude"),
                "longitude": position_data.get("longitude"),
                "accuracy": position_data.get("accuracy")
            }
        )
        
        # Update device tracker if configured
        if ha_integration and device_id:
            await ha_integration.set_value(
                f"device_tracker.{device_id}",
                "home",
                {
                    "latitude": position_data.get("latitude"),
                    "longitude": position_data.get("longitude"),
                    "accuracy": position_data.get("accuracy"),
                    "last_update": datetime.now().isoformat()
                }
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling position update: {str(e)}")

# Condition handlers
async def check_time_condition(condition: Dict[str, Any]) -> bool:
    """Check if time condition is met."""
    try:
        current_time = datetime.now().time()
        
        # Get time ranges
        start_time = time.fromisoformat(condition.get("start_time", "00:00:00"))
        end_time = time.fromisoformat(condition.get("end_time", "23:59:59"))
        
        # Check if current time is within range
        if start_time <= end_time:
            return start_time <= current_time <= end_time
        else:
            # Handle overnight ranges
            return current_time >= start_time or current_time <= end_time
            
    except Exception as e:
        _LOGGER.error(f"Error checking time condition: {str(e)}")
        return False

async def check_presence_condition(condition: Dict[str, Any]) -> bool:
    """Check if presence condition is met."""
    try:
        required_presence = condition.get("presence", True)
        person_name = condition.get("person")
        
        if not person_name or not ha_integration:
            return False
            
        # Check presence sensor
        sensor_id = f"binary_sensor.presence_{person_name.lower()}"
        state = await ha_integration.get_state(sensor_id)
        
        if not state:
            return False
            
        current_presence = state.get("state") == "on"
        return current_presence == required_presence
        
    except Exception as e:
        _LOGGER.error(f"Error checking presence condition: {str(e)}")
        return False

async def check_device_condition(condition: Dict[str, Any]) -> bool:
    """Check if device condition is met."""
    try:
        device_id = condition.get("device_id")
        required_state = condition.get("state")
        
        if not device_id or required_state is None or not ha_integration:
            return False
            
        # Get device state
        state = await ha_integration.get_state(device_id)
        if not state:
            return False
            
        return state.get("state") == required_state
        
    except Exception as e:
        _LOGGER.error(f"Error checking device condition: {str(e)}")
        return False

# Action handlers
async def handle_notification_action(action: Dict[str, Any]) -> None:
    """Handle notification actions."""
    try:
        message = action.get("message")
        target = action.get("target", "all")
        
        if not message or not ha_integration:
            return
            
        if target == "voice":
            # Use TTS service
            await ha_integration.call_service(
                "tts",
                "speak",
                {"entity_id": "media_player.maia_speaker"},
                {"message": message}
            )
        else:
            # Use notification service
            await ha_integration.call_service(
                "notify",
                "notify",
                {},
                {"message": message, "target": target}
            )
        
    except Exception as e:
        _LOGGER.error(f"Error handling notification action: {str(e)}")

async def handle_device_control_action(action: Dict[str, Any]) -> None:
    """Handle device control actions."""
    try:
        device_id = action.get("device_id")
        command = action.get("command")
        parameters = action.get("parameters", {})
        
        if not device_id or not command or not ha_integration:
            return
            
        # Execute command
        if command == "turn_on":
            await ha_integration.turn_on(device_id, parameters)
        elif command == "turn_off":
            await ha_integration.turn_off(device_id, parameters)
        elif command == "toggle":
            await ha_integration.toggle(device_id, parameters)
        elif command == "set_value":
            value = parameters.pop("value", None)
            if value is not None:
                await ha_integration.set_value(device_id, value, parameters)
        elif command == "play_media":
            media_id = parameters.pop("media_content_id", None)
            media_type = parameters.pop("media_content_type", None)
            if media_id and media_type:
                await ha_integration.play_media(
                    device_id,
                    media_id,
                    media_type,
                    parameters
                )
        
    except Exception as e:
        _LOGGER.error(f"Error handling device control action: {str(e)}")

async def handle_scene_activation_action(action: Dict[str, Any]) -> None:
    """Handle scene activation actions."""
    try:
        scene_id = action.get("scene_id")
        transition = action.get("transition", 0)
        
        if not scene_id or not ha_integration:
            return
            
        # Activate scene
        await ha_integration.activate_scene(scene_id, transition)
        
    except Exception as e:
        _LOGGER.error(f"Error handling scene activation action: {str(e)}")

# Helper functions
async def send_ha_command(
    command: str,
    entity_id: str,
    data: Dict[str, Any] = None
) -> bool:
    """Send command to Home Assistant."""
    try:
        if not ha_integration:
            return False
            
        domain = entity_id.split(".")[0]
        return await ha_integration.call_service(
            domain,
            command,
            {"entity_id": entity_id},
            data
        )
        
    except Exception as e:
        _LOGGER.error(f"Error sending Home Assistant command: {str(e)}")
        return False

async def get_ha_state(entity_id: str) -> Optional[Dict[str, Any]]:
    """Get entity state from Home Assistant."""
    try:
        if not ha_integration:
            return None
            
        return await ha_integration.get_state(entity_id)
        
    except Exception as e:
        _LOGGER.error(f"Error getting Home Assistant state: {str(e)}")
        return None 