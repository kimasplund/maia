#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class HAAutomationTool:
    def __init__(self):
        self.seal = SealTools()
        
    def create_motion_automation(self, camera_id, action_config, output_file):
        """Create motion detection automation"""
        try:
            self.seal.log_info("Creating motion detection automation")
            automation = {
                "alias": f"Motion Detection - {camera_id}",
                "trigger": {
                    "platform": "event",
                    "event_type": "motion_detected",
                    "event_data": {
                        "device_id": camera_id
                    }
                },
                "condition": [],
                "action": action_config
            }
            
            validation = self.seal.validate_ha_automation(automation)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid automation: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(automation, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating motion automation: {str(e)}")
            return False

    def create_face_automation(self, camera_id, face_name, action_config, output_file):
        """Create face recognition automation"""
        try:
            self.seal.log_info("Creating face recognition automation")
            automation = {
                "alias": f"Face Recognition - {face_name}",
                "trigger": {
                    "platform": "event",
                    "event_type": "face_detected",
                    "event_data": {
                        "device_id": camera_id,
                        "face_name": face_name
                    }
                },
                "condition": [],
                "action": action_config
            }
            
            validation = self.seal.validate_ha_automation(automation)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid automation: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(automation, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating face automation: {str(e)}")
            return False

    def create_voice_automation(self, camera_id, action_config, output_file):
        """Create voice detection automation"""
        try:
            self.seal.log_info("Creating voice detection automation")
            automation = {
                "alias": f"Voice Detection - {camera_id}",
                "trigger": {
                    "platform": "event",
                    "event_type": "voice_detected",
                    "event_data": {
                        "device_id": camera_id
                    }
                },
                "condition": [],
                "action": action_config
            }
            
            validation = self.seal.validate_ha_automation(automation)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid automation: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(automation, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating voice automation: {str(e)}")
            return False

    def create_time_based_scene(self, scene_name, entities, time_config, output_file):
        """Create time-based scene"""
        try:
            self.seal.log_info("Creating time-based scene")
            scene = {
                "name": scene_name,
                "entities": entities,
                "trigger": {
                    "platform": "time",
                    "at": time_config["time"]
                },
                "condition": time_config.get("conditions", []),
                "action": {
                    "service": "scene.turn_on",
                    "target": {
                        "entity_id": f"scene.{scene_name.lower().replace(' ', '_')}"
                    }
                }
            }
            
            validation = self.seal.validate_ha_scene(scene)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid scene: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(scene, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating time-based scene: {str(e)}")
            return False

    def create_presence_scene(self, scene_name, entities, presence_config, output_file):
        """Create presence-based scene"""
        try:
            self.seal.log_info("Creating presence-based scene")
            scene = {
                "name": scene_name,
                "entities": entities,
                "trigger": {
                    "platform": "state",
                    "entity_id": presence_config["sensor"],
                    "to": presence_config["state"]
                },
                "condition": presence_config.get("conditions", []),
                "action": {
                    "service": "scene.turn_on",
                    "target": {
                        "entity_id": f"scene.{scene_name.lower().replace(' ', '_')}"
                    }
                }
            }
            
            validation = self.seal.validate_ha_scene(scene)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid scene: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(scene, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating presence-based scene: {str(e)}")
            return False

    def create_adaptive_lighting(self, light_entities, config, output_file):
        """Create adaptive lighting automation"""
        try:
            self.seal.log_info("Creating adaptive lighting automation")
            automation = {
                "alias": "Adaptive Lighting",
                "trigger": [
                    {
                        "platform": "time_pattern",
                        "minutes": "/5"
                    },
                    {
                        "platform": "state",
                        "entity_id": light_entities
                    }
                ],
                "condition": [
                    {
                        "condition": "state",
                        "entity_id": light_entities,
                        "state": "on"
                    }
                ],
                "action": {
                    "service": "light.turn_on",
                    "target": {
                        "entity_id": light_entities
                    },
                    "data": {
                        "brightness_pct": "{{ states('sensor.adaptive_lighting_brightness') }}",
                        "color_temp": "{{ states('sensor.adaptive_lighting_color_temp') }}"
                    }
                },
                "mode": "queued"
            }
            
            # Create adaptive lighting sensors
            sensors = {
                "adaptive_lighting_brightness": {
                    "min_brightness": config.get("min_brightness", 10),
                    "max_brightness": config.get("max_brightness", 100),
                    "transition_time": config.get("transition_time", 30)
                },
                "adaptive_lighting_color_temp": {
                    "min_temp": config.get("min_color_temp", 2000),
                    "max_temp": config.get("max_color_temp", 6500),
                    "transition_time": config.get("transition_time", 30)
                }
            }
            
            # Save configuration
            config = {
                "automation": automation,
                "sensors": sensors
            }
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating adaptive lighting: {str(e)}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Home Assistant Automation Tool")
    parser.add_argument('--action', choices=['motion', 'face', 'voice', 'time-scene', 'presence-scene', 'adaptive'], required=True)
    parser.add_argument('--camera-id', help="Camera device ID")
    parser.add_argument('--face-name', help="Face name for recognition")
    parser.add_argument('--scene-name', help="Scene name")
    parser.add_argument('--entities', help="JSON file with entity configurations")
    parser.add_argument('--config', help="Configuration file")
    parser.add_argument('--output', help="Output file", required=True)
    
    args = parser.parse_args()
    tool = HAAutomationTool()
    
    if args.action == 'motion':
        if not args.camera_id or not args.config:
            print("Error: --camera-id and --config required for motion automation")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_motion_automation(args.camera_id, config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'face':
        if not args.camera_id or not args.face_name or not args.config:
            print("Error: --camera-id, --face-name, and --config required for face automation")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_face_automation(args.camera_id, args.face_name, config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'voice':
        if not args.camera_id or not args.config:
            print("Error: --camera-id and --config required for voice automation")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_voice_automation(args.camera_id, config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'time-scene':
        if not args.scene_name or not args.entities or not args.config:
            print("Error: --scene-name, --entities, and --config required for time-based scene")
            sys.exit(1)
        with open(args.entities, 'r') as f:
            entities = json.load(f)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_time_based_scene(args.scene_name, entities, config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'presence-scene':
        if not args.scene_name or not args.entities or not args.config:
            print("Error: --scene-name, --entities, and --config required for presence-based scene")
            sys.exit(1)
        with open(args.entities, 'r') as f:
            entities = json.load(f)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_presence_scene(args.scene_name, entities, config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'adaptive':
        if not args.entities or not args.config:
            print("Error: --entities and --config required for adaptive lighting")
            sys.exit(1)
        with open(args.entities, 'r') as f:
            entities = json.load(f)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_adaptive_lighting(entities, config, args.output)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 