"""
Automation engine for MAIA.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from ..database.storage import CommandStorage
from ..core.openai_integration import OpenAIIntegration

@dataclass
class AutomationRule:
    """Automation rule definition."""
    id: str
    name: str
    description: str
    trigger: Dict[str, Any]
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class AutomationEvent:
    """Event that can trigger automations."""
    source: str
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime

class AutomationEngine:
    """Engine for handling automation rules and execution."""
    
    def __init__(
        self,
        command_storage: CommandStorage,
        openai_integration: OpenAIIntegration,
        rules_file: str = "automation_rules.json"
    ):
        """Initialize automation engine."""
        self.command_storage = command_storage
        self.openai_integration = openai_integration
        self.rules_file = rules_file
        self.logger = logging.getLogger(__name__)
        
        # Initialize storage
        self.rules: Dict[str, AutomationRule] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.action_handlers: Dict[str, Callable] = {}
        self.condition_handlers: Dict[str, Callable] = {}
        
        # Event processing
        self.event_queue: asyncio.Queue[AutomationEvent] = asyncio.Queue()
        self.processing_task: Optional[asyncio.Task] = None
        self.is_running = False
        
    async def start(self) -> None:
        """Start the automation engine."""
        try:
            # Load rules
            await self.load_rules()
            
            # Start event processing
            self.is_running = True
            self.processing_task = asyncio.create_task(self._process_events())
            
            self.logger.info("Automation engine started")
            
        except Exception as e:
            self.logger.error(f"Failed to start automation engine: {str(e)}")
            raise
            
    async def stop(self) -> None:
        """Stop the automation engine."""
        try:
            self.is_running = False
            
            if self.processing_task:
                self.processing_task.cancel()
                try:
                    await self.processing_task
                except asyncio.CancelledError:
                    pass
                
            self.logger.info("Automation engine stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping automation engine: {str(e)}")
            
    async def load_rules(self) -> None:
        """Load automation rules from file."""
        try:
            with open(self.rules_file, "r") as f:
                rules_data = json.load(f)
                
            self.rules.clear()
            for rule_data in rules_data:
                rule = AutomationRule(**rule_data)
                self.rules[rule.id] = rule
                
            self.logger.info(f"Loaded {len(self.rules)} automation rules")
            
        except FileNotFoundError:
            self.logger.warning(f"Rules file not found: {self.rules_file}")
            
        except Exception as e:
            self.logger.error(f"Error loading rules: {str(e)}")
            
    async def save_rules(self) -> None:
        """Save automation rules to file."""
        try:
            rules_data = [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "description": rule.description,
                    "trigger": rule.trigger,
                    "conditions": rule.conditions,
                    "actions": rule.actions,
                    "enabled": rule.enabled,
                    "metadata": rule.metadata
                }
                for rule in self.rules.values()
            ]
            
            with open(self.rules_file, "w") as f:
                json.dump(rules_data, f, indent=2)
                
            self.logger.info(f"Saved {len(self.rules)} automation rules")
            
        except Exception as e:
            self.logger.error(f"Error saving rules: {str(e)}")
            
    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[[AutomationEvent], None]
    ) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        
    def register_action_handler(
        self,
        action_type: str,
        handler: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register a handler for a specific action type."""
        self.action_handlers[action_type] = handler
        
    def register_condition_handler(
        self,
        condition_type: str,
        handler: Callable[[Dict[str, Any]], bool]
    ) -> None:
        """Register a handler for a specific condition type."""
        self.condition_handlers[condition_type] = handler
        
    async def add_rule(self, rule: AutomationRule) -> bool:
        """Add a new automation rule."""
        try:
            if rule.id in self.rules:
                self.logger.warning(f"Rule already exists: {rule.id}")
                return False
                
            self.rules[rule.id] = rule
            await self.save_rules()
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding rule: {str(e)}")
            return False
            
    async def update_rule(self, rule: AutomationRule) -> bool:
        """Update an existing automation rule."""
        try:
            if rule.id not in self.rules:
                self.logger.warning(f"Rule not found: {rule.id}")
                return False
                
            self.rules[rule.id] = rule
            await self.save_rules()
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating rule: {str(e)}")
            return False
            
    async def delete_rule(self, rule_id: str) -> bool:
        """Delete an automation rule."""
        try:
            if rule_id not in self.rules:
                self.logger.warning(f"Rule not found: {rule_id}")
                return False
                
            del self.rules[rule_id]
            await self.save_rules()
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting rule: {str(e)}")
            return False
            
    async def process_event(self, event: AutomationEvent) -> None:
        """Process an automation event."""
        try:
            # Add event to queue
            await self.event_queue.put(event)
            
            # Notify event handlers
            if event.event_type in self.event_handlers:
                for handler in self.event_handlers[event.event_type]:
                    try:
                        await handler(event)
                    except Exception as e:
                        self.logger.error(
                            f"Error in event handler: {str(e)}",
                            extra={"event": event}
                        )
                        
        except Exception as e:
            self.logger.error(f"Error processing event: {str(e)}")
            
    async def _process_events(self) -> None:
        """Background task for processing events."""
        while self.is_running:
            try:
                # Get next event
                event = await self.event_queue.get()
                
                # Check each rule
                for rule in self.rules.values():
                    if not rule.enabled:
                        continue
                        
                    # Check if event matches trigger
                    if not self._matches_trigger(event, rule.trigger):
                        continue
                        
                    # Check conditions
                    if not await self._check_conditions(rule.conditions, event):
                        continue
                        
                    # Execute actions
                    await self._execute_actions(rule.actions, event)
                    
            except asyncio.CancelledError:
                break
                
            except Exception as e:
                self.logger.error(f"Error in event processing loop: {str(e)}")
                await asyncio.sleep(1)
                
    def _matches_trigger(self, event: AutomationEvent, trigger: Dict[str, Any]) -> bool:
        """Check if event matches trigger configuration."""
        try:
            # Check source
            if "source" in trigger and trigger["source"] != event.source:
                return False
                
            # Check event type
            if "event_type" in trigger and trigger["event_type"] != event.event_type:
                return False
                
            # Check data conditions
            if "data" in trigger:
                for key, value in trigger["data"].items():
                    if key not in event.data or event.data[key] != value:
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"Error matching trigger: {str(e)}")
            return False
            
    async def _check_conditions(
        self,
        conditions: List[Dict[str, Any]],
        event: AutomationEvent
    ) -> bool:
        """Check if all conditions are met."""
        try:
            for condition in conditions:
                condition_type = condition.get("type")
                if not condition_type:
                    continue
                    
                if condition_type not in self.condition_handlers:
                    self.logger.warning(f"No handler for condition type: {condition_type}")
                    return False
                    
                handler = self.condition_handlers[condition_type]
                if not await handler(condition):
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking conditions: {str(e)}")
            return False
            
    async def _execute_actions(
        self,
        actions: List[Dict[str, Any]],
        event: AutomationEvent
    ) -> None:
        """Execute automation actions."""
        for action in actions:
            try:
                action_type = action.get("type")
                if not action_type:
                    continue
                    
                if action_type not in self.action_handlers:
                    self.logger.warning(f"No handler for action type: {action_type}")
                    continue
                    
                handler = self.action_handlers[action_type]
                await handler(action)
                
            except Exception as e:
                self.logger.error(
                    f"Error executing action: {str(e)}",
                    extra={"action": action}
                ) 