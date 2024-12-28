"""
Automation rules system for MAIA.
Handles complex automation scenarios based on geofencing and other events.
"""
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, time, timedelta
from dataclasses import dataclass
import json
import asyncio
from ..database.geofencing import GeofenceEvent

_LOGGER = logging.getLogger(__name__)

@dataclass
class TimeCondition:
    """Time-based condition."""
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[List[int]] = None  # 0=Monday, 6=Sunday
    
    def check(self, current_time: datetime) -> bool:
        """Check if condition is met."""
        # Check day of week
        if self.days_of_week is not None:
            if current_time.weekday() not in self.days_of_week:
                return False
                
        # Check time range
        if self.start_time and self.end_time:
            current_time_only = current_time.time()
            if self.start_time <= self.end_time:
                # Normal time range (e.g., 9:00-17:00)
                return self.start_time <= current_time_only <= self.end_time
            else:
                # Overnight time range (e.g., 22:00-06:00)
                return current_time_only >= self.start_time or current_time_only <= self.end_time
                
        return True

@dataclass
class DeviceCondition:
    """Device-based condition."""
    required_zones: Optional[List[str]] = None  # Must be in these zones
    excluded_zones: Optional[List[str]] = None  # Must not be in these zones
    min_dwell_time: Optional[timedelta] = None  # Must have been in zone for this long
    
    def check(self, current_zones: List[str], zone_history: List[GeofenceEvent]) -> bool:
        """Check if condition is met."""
        # Check required zones
        if self.required_zones:
            if not all(zone in current_zones for zone in self.required_zones):
                return False
                
        # Check excluded zones
        if self.excluded_zones:
            if any(zone in current_zones for zone in self.excluded_zones):
                return False
                
        # Check dwell time
        if self.min_dwell_time and current_zones:
            latest_enter = None
            for event in reversed(zone_history):
                if event.event_type == 'enter' and event.zone_id in current_zones:
                    latest_enter = event.timestamp
                    break
                    
            if not latest_enter or (datetime.now() - latest_enter) < self.min_dwell_time:
                return False
                
        return True

@dataclass
class CountCondition:
    """Count-based condition."""
    event_type: str
    zone_id: Optional[str] = None
    device_mac: Optional[str] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    time_window: Optional[timedelta] = None
    
    def check(self, event_history: List[GeofenceEvent]) -> bool:
        """Check if condition is met."""
        # Filter events
        filtered_events = event_history
        if self.zone_id:
            filtered_events = [e for e in filtered_events if e.zone_id == self.zone_id]
        if self.device_mac:
            filtered_events = [e for e in filtered_events if e.device_mac == self.device_mac]
        if self.event_type:
            filtered_events = [e for e in filtered_events if e.event_type == self.event_type]
            
        # Apply time window
        if self.time_window:
            cutoff = datetime.now() - self.time_window
            filtered_events = [e for e in filtered_events if e.timestamp >= cutoff]
            
        # Check count
        count = len(filtered_events)
        if self.min_count is not None and count < self.min_count:
            return False
        if self.max_count is not None and count > self.max_count:
            return False
            
        return True

@dataclass
class Action:
    """Automation action."""
    action_type: str
    target: str
    parameters: Optional[Dict[str, Any]] = None
    delay: Optional[timedelta] = None
    
    async def execute(self, event_context: Dict[str, Any]):
        """Execute action with optional delay."""
        if self.delay:
            await asyncio.sleep(self.delay.total_seconds())
            
        try:
            # Get action handler
            handler = ACTION_HANDLERS.get(self.action_type)
            if not handler:
                _LOGGER.error(f"Unknown action type: {self.action_type}")
                return
                
            # Execute action
            await handler(self.target, self.parameters or {}, event_context)
            
        except Exception as e:
            _LOGGER.error(f"Failed to execute action: {str(e)}")

@dataclass
class AutomationRule:
    """Automation rule definition."""
    rule_id: str
    name: str
    description: Optional[str] = None
    trigger_events: List[str]  # List of event types to trigger on
    trigger_zones: Optional[List[str]] = None  # Only trigger for these zones
    trigger_devices: Optional[List[str]] = None  # Only trigger for these devices
    time_conditions: Optional[List[TimeCondition]] = None
    device_conditions: Optional[List[DeviceCondition]] = None
    count_conditions: Optional[List[CountCondition]] = None
    actions: List[Action]
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    def check_trigger(self, event: GeofenceEvent) -> bool:
        """Check if rule should trigger for event."""
        if not self.enabled:
            return False
            
        # Check event type
        if event.event_type not in self.trigger_events:
            return False
            
        # Check zone
        if self.trigger_zones and event.zone_id not in self.trigger_zones:
            return False
            
        # Check device
        if self.trigger_devices and event.device_mac not in self.trigger_devices:
            return False
            
        return True
        
    def check_conditions(
        self,
        event: GeofenceEvent,
        current_zones: List[str],
        zone_history: List[GeofenceEvent]
    ) -> bool:
        """Check if all conditions are met."""
        # Check time conditions
        if self.time_conditions:
            if not all(cond.check(event.timestamp) for cond in self.time_conditions):
                return False
                
        # Check device conditions
        if self.device_conditions:
            if not all(cond.check(current_zones, zone_history) for cond in self.device_conditions):
                return False
                
        # Check count conditions
        if self.count_conditions:
            if not all(cond.check(zone_history) for cond in self.count_conditions):
                return False
                
        return True
        
    async def execute_actions(self, event: GeofenceEvent, context: Dict[str, Any]):
        """Execute all actions for this rule."""
        event_context = {
            "event": event,
            "rule": self,
            **context
        }
        
        for action in self.actions:
            try:
                await action.execute(event_context)
            except Exception as e:
                _LOGGER.error(f"Failed to execute action for rule {self.rule_id}: {str(e)}")

class AutomationEngine:
    """Engine for processing automation rules."""
    
    def __init__(self):
        """Initialize automation engine."""
        self.rules: Dict[str, AutomationRule] = {}
        self._event_history: List[GeofenceEvent] = []
        self._history_limit = 1000  # Keep last 1000 events
        
    def add_rule(self, rule: AutomationRule) -> bool:
        """Add or update automation rule."""
        try:
            self.rules[rule.rule_id] = rule
            _LOGGER.info(f"Added automation rule: {rule.name} ({rule.rule_id})")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to add rule: {str(e)}")
            return False
            
    def remove_rule(self, rule_id: str) -> bool:
        """Remove automation rule."""
        try:
            if rule_id in self.rules:
                del self.rules[rule_id]
                _LOGGER.info(f"Removed automation rule: {rule_id}")
                return True
            return False
        except Exception as e:
            _LOGGER.error(f"Failed to remove rule: {str(e)}")
            return False
            
    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        """Get automation rule by ID."""
        return self.rules.get(rule_id)
        
    def get_rules(self) -> List[AutomationRule]:
        """Get all automation rules."""
        return list(self.rules.values())
        
    async def handle_event(self, event: GeofenceEvent, context: Dict[str, Any]):
        """Handle geofence event."""
        try:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._history_limit:
                self._event_history = self._event_history[-self._history_limit:]
                
            # Get current zones for device
            current_zones = [
                e.zone_id for e in self._event_history
                if e.device_mac == event.device_mac
                and e.event_type in ('enter', 'dwell')
                and e.timestamp > datetime.now() - timedelta(minutes=5)
            ]
            
            # Get device history
            device_history = [
                e for e in self._event_history
                if e.device_mac == event.device_mac
            ]
            
            # Process rules
            for rule in self.rules.values():
                try:
                    # Check trigger
                    if not rule.check_trigger(event):
                        continue
                        
                    # Check conditions
                    if not rule.check_conditions(event, current_zones, device_history):
                        continue
                        
                    # Execute actions
                    await rule.execute_actions(event, context)
                    
                except Exception as e:
                    _LOGGER.error(f"Error processing rule {rule.rule_id}: {str(e)}")
                    
        except Exception as e:
            _LOGGER.error(f"Error handling event: {str(e)}")

# Action Handlers
ACTION_HANDLERS: Dict[str, Callable] = {}

def register_action_handler(action_type: str):
    """Decorator to register action handler."""
    def decorator(func):
        ACTION_HANDLERS[action_type] = func
        return func
    return decorator

@register_action_handler("notify")
async def handle_notify(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle notification action."""
    try:
        # Get notification service
        service = parameters.get("service", "default")
        
        # Format message
        message = parameters.get("message", "")
        if isinstance(message, str):
            # Replace placeholders
            message = message.format(
                device=context["event"].device_mac,
                zone=context["event"].zone_id,
                event=context["event"].event_type,
                **parameters.get("variables", {})
            )
            
        # Send notification
        # TODO: Implement notification service integration
        _LOGGER.info(f"Would send notification via {service}: {message}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to send notification: {str(e)}")

@register_action_handler("scene")
async def handle_scene(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle scene activation action."""
    try:
        # Get scene parameters
        scene_id = target
        transition = parameters.get("transition", 1.0)
        
        # Activate scene
        # TODO: Implement scene activation
        _LOGGER.info(f"Would activate scene {scene_id} with transition {transition}s")
        
    except Exception as e:
        _LOGGER.error(f"Failed to activate scene: {str(e)}")

@register_action_handler("device")
async def handle_device(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle device control action."""
    try:
        # Get device parameters
        device_id = target
        command = parameters.get("command", "turn_on")
        command_params = parameters.get("parameters", {})
        
        # Control device
        # TODO: Implement device control
        _LOGGER.info(f"Would control device {device_id}: {command}({command_params})")
        
    except Exception as e:
        _LOGGER.error(f"Failed to control device: {str(e)}")

@register_action_handler("script")
async def handle_script(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle script execution action."""
    try:
        # Get script parameters
        script_id = target
        variables = parameters.get("variables", {})
        
        # Execute script
        # TODO: Implement script execution
        _LOGGER.info(f"Would execute script {script_id} with variables {variables}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to execute script: {str(e)}")

@register_action_handler("webhook")
async def handle_webhook(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle webhook action."""
    try:
        # Get webhook parameters
        url = target
        method = parameters.get("method", "POST")
        headers = parameters.get("headers", {})
        payload = parameters.get("payload", {})
        
        # Format payload
        if isinstance(payload, dict):
            payload = {
                k: v.format(
                    device=context["event"].device_mac,
                    zone=context["event"].zone_id,
                    event=context["event"].event_type,
                    **parameters.get("variables", {})
                ) if isinstance(v, str) else v
                for k, v in payload.items()
            }
            
        # Send webhook
        # TODO: Implement webhook sending
        _LOGGER.info(f"Would send webhook to {url}: {method} {payload}")
        
    except Exception as e:
        _LOGGER.error(f"Failed to send webhook: {str(e)}")

@register_action_handler("delay")
async def handle_delay(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle delay action."""
    try:
        # Get delay parameters
        duration = float(target)  # seconds
        
        # Execute delay
        await asyncio.sleep(duration)
        
    except Exception as e:
        _LOGGER.error(f"Failed to execute delay: {str(e)}")

@register_action_handler("condition")
async def handle_condition(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle conditional action."""
    try:
        # Get condition parameters
        condition_type = target
        condition_params = parameters.get("condition", {})
        then_actions = parameters.get("then", [])
        else_actions = parameters.get("else", [])
        
        # Check condition
        condition_met = False
        if condition_type == "time":
            condition = TimeCondition(**condition_params)
            condition_met = condition.check(datetime.now())
        elif condition_type == "device":
            condition = DeviceCondition(**condition_params)
            current_zones = parameters.get("current_zones", [])
            zone_history = parameters.get("zone_history", [])
            condition_met = condition.check(current_zones, zone_history)
        elif condition_type == "count":
            condition = CountCondition(**condition_params)
            event_history = parameters.get("event_history", [])
            condition_met = condition.check(event_history)
            
        # Execute appropriate actions
        actions = then_actions if condition_met else else_actions
        for action_data in actions:
            action = Action(**action_data)
            await action.execute(context)
            
    except Exception as e:
        _LOGGER.error(f"Failed to execute conditional action: {str(e)}")

@register_action_handler("sequence")
async def handle_sequence(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle action sequence."""
    try:
        # Get sequence parameters
        actions = parameters.get("actions", [])
        
        # Execute actions in sequence
        for action_data in actions:
            action = Action(**action_data)
            await action.execute(context)
            
    except Exception as e:
        _LOGGER.error(f"Failed to execute action sequence: {str(e)}")

@register_action_handler("parallel")
async def handle_parallel(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle parallel actions."""
    try:
        # Get parallel parameters
        actions = parameters.get("actions", [])
        
        # Execute actions in parallel
        tasks = []
        for action_data in actions:
            action = Action(**action_data)
            tasks.append(action.execute(context))
            
        await asyncio.gather(*tasks)
        
    except Exception as e:
        _LOGGER.error(f"Failed to execute parallel actions: {str(e)}")

@register_action_handler("repeat")
async def handle_repeat(
    target: str,
    parameters: Dict[str, Any],
    context: Dict[str, Any]
):
    """Handle action repetition."""
    try:
        # Get repeat parameters
        count = int(target)
        interval = parameters.get("interval", 0)  # seconds between repetitions
        action_data = parameters.get("action", {})
        
        # Create action
        action = Action(**action_data)
        
        # Execute repeated actions
        for _ in range(count):
            await action.execute(context)
            if interval > 0 and _ < count - 1:
                await asyncio.sleep(interval)
                
    except Exception as e:
        _LOGGER.error(f"Failed to execute repeated action: {str(e)}") 