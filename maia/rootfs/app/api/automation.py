"""
Automation API endpoints for MAIA.
"""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, time, timedelta
from ..core.automation_rules import (
    AutomationRule, Action, TimeCondition,
    DeviceCondition, CountCondition
)

router = APIRouter(prefix="/automation", tags=["automation"])

# API Models
class TimeConditionModel(BaseModel):
    """Time condition model."""
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: Optional[List[int]] = None

class DeviceConditionModel(BaseModel):
    """Device condition model."""
    required_zones: Optional[List[str]] = None
    excluded_zones: Optional[List[str]] = None
    min_dwell_time: Optional[float] = None  # seconds

class CountConditionModel(BaseModel):
    """Count condition model."""
    event_type: str
    zone_id: Optional[str] = None
    device_mac: Optional[str] = None
    min_count: Optional[int] = None
    max_count: Optional[int] = None
    time_window: Optional[float] = None  # seconds

class ActionModel(BaseModel):
    """Action model."""
    action_type: str
    target: str
    parameters: Optional[Dict[str, Any]] = None
    delay: Optional[float] = None  # seconds

class AutomationRuleCreate(BaseModel):
    """Automation rule creation model."""
    name: str
    description: Optional[str] = None
    trigger_events: List[str]
    trigger_zones: Optional[List[str]] = None
    trigger_devices: Optional[List[str]] = None
    time_conditions: Optional[List[TimeConditionModel]] = None
    device_conditions: Optional[List[DeviceConditionModel]] = None
    count_conditions: Optional[List[CountConditionModel]] = None
    actions: List[ActionModel]
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = None

class AutomationRuleUpdate(BaseModel):
    """Automation rule update model."""
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_events: Optional[List[str]] = None
    trigger_zones: Optional[List[str]] = None
    trigger_devices: Optional[List[str]] = None
    time_conditions: Optional[List[TimeConditionModel]] = None
    device_conditions: Optional[List[DeviceConditionModel]] = None
    count_conditions: Optional[List[CountConditionModel]] = None
    actions: Optional[List[ActionModel]] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None

class AutomationRuleResponse(BaseModel):
    """Automation rule response model."""
    rule_id: str
    name: str
    description: Optional[str] = None
    trigger_events: List[str]
    trigger_zones: Optional[List[str]] = None
    trigger_devices: Optional[List[str]] = None
    time_conditions: Optional[List[TimeConditionModel]] = None
    device_conditions: Optional[List[DeviceConditionModel]] = None
    count_conditions: Optional[List[CountConditionModel]] = None
    actions: List[ActionModel]
    enabled: bool
    metadata: Optional[Dict[str, Any]] = None

def _convert_rule_to_response(rule: AutomationRule) -> AutomationRuleResponse:
    """Convert AutomationRule to response model."""
    return AutomationRuleResponse(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        trigger_events=rule.trigger_events,
        trigger_zones=rule.trigger_zones,
        trigger_devices=rule.trigger_devices,
        time_conditions=[
            TimeConditionModel(
                start_time=cond.start_time,
                end_time=cond.end_time,
                days_of_week=cond.days_of_week
            )
            for cond in (rule.time_conditions or [])
        ],
        device_conditions=[
            DeviceConditionModel(
                required_zones=cond.required_zones,
                excluded_zones=cond.excluded_zones,
                min_dwell_time=cond.min_dwell_time.total_seconds() if cond.min_dwell_time else None
            )
            for cond in (rule.device_conditions or [])
        ],
        count_conditions=[
            CountConditionModel(
                event_type=cond.event_type,
                zone_id=cond.zone_id,
                device_mac=cond.device_mac,
                min_count=cond.min_count,
                max_count=cond.max_count,
                time_window=cond.time_window.total_seconds() if cond.time_window else None
            )
            for cond in (rule.count_conditions or [])
        ],
        actions=[
            ActionModel(
                action_type=action.action_type,
                target=action.target,
                parameters=action.parameters,
                delay=action.delay.total_seconds() if action.delay else None
            )
            for action in rule.actions
        ],
        enabled=rule.enabled,
        metadata=rule.metadata
    )

def _convert_model_to_rule(model: AutomationRuleCreate, rule_id: str) -> AutomationRule:
    """Convert request model to AutomationRule."""
    return AutomationRule(
        rule_id=rule_id,
        name=model.name,
        description=model.description,
        trigger_events=model.trigger_events,
        trigger_zones=model.trigger_zones,
        trigger_devices=model.trigger_devices,
        time_conditions=[
            TimeCondition(
                start_time=cond.start_time,
                end_time=cond.end_time,
                days_of_week=cond.days_of_week
            )
            for cond in (model.time_conditions or [])
        ],
        device_conditions=[
            DeviceCondition(
                required_zones=cond.required_zones,
                excluded_zones=cond.excluded_zones,
                min_dwell_time=timedelta(seconds=cond.min_dwell_time) if cond.min_dwell_time else None
            )
            for cond in (model.device_conditions or [])
        ],
        count_conditions=[
            CountCondition(
                event_type=cond.event_type,
                zone_id=cond.zone_id,
                device_mac=cond.device_mac,
                min_count=cond.min_count,
                max_count=cond.max_count,
                time_window=timedelta(seconds=cond.time_window) if cond.time_window else None
            )
            for cond in (model.count_conditions or [])
        ],
        actions=[
            Action(
                action_type=action.action_type,
                target=action.target,
                parameters=action.parameters,
                delay=timedelta(seconds=action.delay) if action.delay else None
            )
            for action in model.actions
        ],
        enabled=model.enabled,
        metadata=model.metadata
    )

def _update_rule_from_model(rule: AutomationRule, model: AutomationRuleUpdate) -> AutomationRule:
    """Update AutomationRule from update model."""
    if model.name is not None:
        rule.name = model.name
    if model.description is not None:
        rule.description = model.description
    if model.trigger_events is not None:
        rule.trigger_events = model.trigger_events
    if model.trigger_zones is not None:
        rule.trigger_zones = model.trigger_zones
    if model.trigger_devices is not None:
        rule.trigger_devices = model.trigger_devices
    if model.time_conditions is not None:
        rule.time_conditions = [
            TimeCondition(
                start_time=cond.start_time,
                end_time=cond.end_time,
                days_of_week=cond.days_of_week
            )
            for cond in model.time_conditions
        ]
    if model.device_conditions is not None:
        rule.device_conditions = [
            DeviceCondition(
                required_zones=cond.required_zones,
                excluded_zones=cond.excluded_zones,
                min_dwell_time=timedelta(seconds=cond.min_dwell_time) if cond.min_dwell_time else None
            )
            for cond in model.device_conditions
        ]
    if model.count_conditions is not None:
        rule.count_conditions = [
            CountCondition(
                event_type=cond.event_type,
                zone_id=cond.zone_id,
                device_mac=cond.device_mac,
                min_count=cond.min_count,
                max_count=cond.max_count,
                time_window=timedelta(seconds=cond.time_window) if cond.time_window else None
            )
            for cond in model.count_conditions
        ]
    if model.actions is not None:
        rule.actions = [
            Action(
                action_type=action.action_type,
                target=action.target,
                parameters=action.parameters,
                delay=timedelta(seconds=action.delay) if action.delay else None
            )
            for action in model.actions
        ]
    if model.enabled is not None:
        rule.enabled = model.enabled
    if model.metadata is not None:
        rule.metadata = model.metadata
    return rule

@router.post("/rules", response_model=AutomationRuleResponse)
async def create_rule(rule: AutomationRuleCreate):
    """Create new automation rule."""
    try:
        # Generate rule ID
        rule_id = f"rule_{datetime.now().timestamp()}"
        
        # Convert to internal model
        automation_rule = _convert_model_to_rule(rule, rule_id)
        
        # Add rule to engine
        from .main import automation
        success = automation.add_rule(automation_rule)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create rule")
            
        return _convert_rule_to_response(automation_rule)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules", response_model=List[AutomationRuleResponse])
async def get_rules():
    """Get all automation rules."""
    try:
        from .main import automation
        rules = automation.get_rules()
        return [_convert_rule_to_response(rule) for rule in rules]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules/{rule_id}", response_model=AutomationRuleResponse)
async def get_rule(rule_id: str):
    """Get specific automation rule."""
    try:
        from .main import automation
        rule = automation.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
        return _convert_rule_to_response(rule)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/rules/{rule_id}", response_model=AutomationRuleResponse)
async def update_rule(rule_id: str, rule_update: AutomationRuleUpdate):
    """Update automation rule."""
    try:
        from .main import automation
        
        # Get existing rule
        existing_rule = automation.get_rule(rule_id)
        if not existing_rule:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        # Update rule
        updated_rule = _update_rule_from_model(existing_rule, rule_update)
        
        # Add updated rule
        success = automation.add_rule(updated_rule)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update rule")
            
        return _convert_rule_to_response(updated_rule)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete automation rule."""
    try:
        from .main import automation
        success = automation.remove_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/{rule_id}/enable")
async def enable_rule(rule_id: str):
    """Enable automation rule."""
    try:
        from .main import automation
        rule = automation.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        rule.enabled = True
        success = automation.add_rule(rule)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to enable rule")
            
        return {"status": "success"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/{rule_id}/disable")
async def disable_rule(rule_id: str):
    """Disable automation rule."""
    try:
        from .main import automation
        rule = automation.get_rule(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Rule not found")
            
        rule.enabled = False
        success = automation.add_rule(rule)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to disable rule")
            
        return {"status": "success"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 