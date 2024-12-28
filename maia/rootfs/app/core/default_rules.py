"""
Default automation rules for MAIA.
"""
from datetime import time, timedelta
from typing import List
from .automation_rules import (
    AutomationRule, Action, TimeCondition,
    DeviceCondition, CountCondition
)

def get_default_rules() -> List[AutomationRule]:
    """Get default automation rules."""
    return [
        # Rule 1: Welcome Home Notification
        AutomationRule(
            rule_id="welcome_home",
            name="Welcome Home",
            description="Send welcome notification when device enters home zone during evening hours",
            trigger_events=["enter"],
            trigger_zones=["home"],
            time_conditions=[
                TimeCondition(
                    start_time=time(17, 0),  # 5:00 PM
                    end_time=time(23, 0)     # 11:00 PM
                )
            ],
            actions=[
                Action(
                    action_type="notify",
                    target="user",
                    parameters={
                        "message": "Welcome home! Would you like me to turn on the lights?",
                        "service": "mobile_app"
                    }
                ),
                Action(
                    action_type="scene",
                    target="evening_lights",
                    parameters={
                        "transition": 2.0
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 2: Office Automation
        AutomationRule(
            rule_id="office_automation",
            name="Office Automation",
            description="Automate office environment when device enters during work hours",
            trigger_events=["enter"],
            trigger_zones=["office"],
            time_conditions=[
                TimeCondition(
                    start_time=time(8, 0),   # 8:00 AM
                    end_time=time(18, 0),    # 6:00 PM
                    days_of_week=[0,1,2,3,4] # Monday-Friday
                )
            ],
            device_conditions=[
                DeviceCondition(
                    min_dwell_time=timedelta(minutes=5)  # Must stay for 5 minutes
                )
            ],
            actions=[
                Action(
                    action_type="scene",
                    target="office_work",
                    parameters={
                        "transition": 1.0
                    }
                ),
                Action(
                    action_type="device",
                    target="office_ac",
                    parameters={
                        "command": "set_temperature",
                        "parameters": {
                            "temperature": 23.0
                        }
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 3: Away Mode
        AutomationRule(
            rule_id="away_mode",
            name="Away Mode",
            description="Activate away mode when all devices leave home",
            trigger_events=["exit"],
            trigger_zones=["home"],
            count_conditions=[
                CountCondition(
                    event_type="exit",
                    zone_id="home",
                    time_window=timedelta(minutes=15),
                    min_count=1
                )
            ],
            device_conditions=[
                DeviceCondition(
                    excluded_zones=["home"]  # No devices in home
                )
            ],
            actions=[
                Action(
                    action_type="scene",
                    target="away_mode",
                    parameters={
                        "transition": 1.0
                    }
                ),
                Action(
                    action_type="device",
                    target="security_system",
                    parameters={
                        "command": "arm_away"
                    }
                ),
                Action(
                    action_type="notify",
                    target="user",
                    parameters={
                        "message": "Away mode activated. Security system armed.",
                        "service": "mobile_app"
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 4: Garage Door Reminder
        AutomationRule(
            rule_id="garage_reminder",
            name="Garage Door Reminder",
            description="Remind to close garage door when leaving",
            trigger_events=["exit"],
            trigger_zones=["garage"],
            actions=[
                Action(
                    action_type="condition",
                    target="device",
                    parameters={
                        "condition": {
                            "device_id": "garage_door",
                            "state": "open"
                        },
                        "then": [
                            Action(
                                action_type="notify",
                                target="user",
                                parameters={
                                    "message": "Garage door is still open! Would you like me to close it?",
                                    "service": "mobile_app",
                                    "actions": [
                                        {
                                            "action": "close_garage",
                                            "title": "Yes, close it"
                                        }
                                    ]
                                }
                            )
                        ]
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 5: Activity Monitoring
        AutomationRule(
            rule_id="activity_monitor",
            name="Activity Monitoring",
            description="Monitor unusual activity patterns",
            trigger_events=["enter", "exit"],
            count_conditions=[
                CountCondition(
                    event_type="enter",
                    time_window=timedelta(hours=1),
                    min_count=5
                )
            ],
            actions=[
                Action(
                    action_type="notify",
                    target="admin",
                    parameters={
                        "message": "Unusual activity detected: {device} has triggered {count} events in the last hour",
                        "service": "admin_notification",
                        "level": "warning"
                    }
                ),
                Action(
                    action_type="webhook",
                    target="https://api.security.example.com/alerts",
                    parameters={
                        "method": "POST",
                        "payload": {
                            "device": "{device}",
                            "event_count": "{count}",
                            "timestamp": "{timestamp}"
                        }
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 6: Zone Sequence Detection
        AutomationRule(
            rule_id="zone_sequence",
            name="Zone Sequence Detection",
            description="Detect specific sequence of zone transitions",
            trigger_events=["enter"],
            trigger_zones=["zone_c"],
            count_conditions=[
                CountCondition(
                    event_type="enter",
                    zone_id="zone_a",
                    time_window=timedelta(minutes=5),
                    min_count=1
                ),
                CountCondition(
                    event_type="enter",
                    zone_id="zone_b",
                    time_window=timedelta(minutes=5),
                    min_count=1
                )
            ],
            actions=[
                Action(
                    action_type="script",
                    target="sequence_detected",
                    parameters={
                        "variables": {
                            "device": "{device}",
                            "sequence": "A -> B -> C"
                        }
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 7: Extended Presence
        AutomationRule(
            rule_id="extended_presence",
            name="Extended Presence",
            description="Actions for extended presence in a zone",
            trigger_events=["dwell"],
            device_conditions=[
                DeviceCondition(
                    min_dwell_time=timedelta(hours=2)
                )
            ],
            actions=[
                Action(
                    action_type="sequence",
                    target="comfort_adjustments",
                    parameters={
                        "actions": [
                            Action(
                                action_type="device",
                                target="hvac",
                                parameters={
                                    "command": "optimize_comfort",
                                    "parameters": {
                                        "mode": "auto"
                                    }
                                }
                            ),
                            Action(
                                action_type="device",
                                target="air_purifier",
                                parameters={
                                    "command": "set_mode",
                                    "parameters": {
                                        "mode": "auto"
                                    }
                                }
                            )
                        ]
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 8: Quick Transitions
        AutomationRule(
            rule_id="quick_transitions",
            name="Quick Zone Transitions",
            description="Detect rapid transitions between zones",
            trigger_events=["enter", "exit"],
            count_conditions=[
                CountCondition(
                    event_type="enter",
                    time_window=timedelta(minutes=2),
                    min_count=3
                )
            ],
            actions=[
                Action(
                    action_type="notify",
                    target="admin",
                    parameters={
                        "message": "Rapid zone transitions detected for device {device}",
                        "service": "admin_notification",
                        "level": "info"
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 9: Zone Occupancy
        AutomationRule(
            rule_id="zone_occupancy",
            name="Zone Occupancy Management",
            description="Manage zone based on occupancy",
            trigger_events=["enter", "exit"],
            trigger_zones=["meeting_room"],
            actions=[
                Action(
                    action_type="parallel",
                    target="occupancy_actions",
                    parameters={
                        "actions": [
                            Action(
                                action_type="device",
                                target="occupancy_counter",
                                parameters={
                                    "command": "update",
                                    "parameters": {
                                        "event_type": "{event}"
                                    }
                                }
                            ),
                            Action(
                                action_type="device",
                                target="ventilation",
                                parameters={
                                    "command": "adjust",
                                    "parameters": {
                                        "based_on": "occupancy"
                                    }
                                }
                            )
                        ]
                    }
                )
            ],
            enabled=True
        ),
        
        # Rule 10: Time-based Zone Restrictions
        AutomationRule(
            rule_id="zone_restrictions",
            name="Zone Access Restrictions",
            description="Monitor and enforce zone access restrictions",
            trigger_events=["enter"],
            trigger_zones=["restricted_area"],
            time_conditions=[
                TimeCondition(
                    start_time=time(23, 0),  # 11:00 PM
                    end_time=time(5, 0)      # 5:00 AM
                )
            ],
            actions=[
                Action(
                    action_type="notify",
                    target="security",
                    parameters={
                        "message": "Restricted zone access detected: {device} entered {zone} during restricted hours",
                        "service": "security_notification",
                        "level": "warning"
                    }
                ),
                Action(
                    action_type="webhook",
                    target="https://api.security.example.com/incidents",
                    parameters={
                        "method": "POST",
                        "payload": {
                            "type": "restricted_access",
                            "device": "{device}",
                            "zone": "{zone}",
                            "timestamp": "{timestamp}"
                        }
                    }
                )
            ],
            enabled=True
        )
    ] 