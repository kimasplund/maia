#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class HADeviceControlTool:
    def __init__(self):
        self.seal = SealTools()
        
    def discover_devices(self, ha_url, auth_token):
        """Discover available Home Assistant devices and their capabilities"""
        try:
            self.seal.log_info("Discovering Home Assistant devices")
            devices = self.seal.ha_discover_devices(
                ha_url=ha_url,
                auth_token=auth_token,
                include_attributes=True
            )
            return devices
        except Exception as e:
            self.seal.log_error(f"Error discovering devices: {str(e)}")
            return None

    def create_automation(self, trigger_config, action_config, output_file):
        """Create Home Assistant automation"""
        try:
            self.seal.log_info("Creating automation")
            automation = {
                "trigger": trigger_config,
                "action": action_config,
                "mode": "single"  # or "parallel", "queued", "restart"
            }
            
            # Validate automation configuration
            validation = self.seal.validate_ha_automation(automation)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid automation: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(automation, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating automation: {str(e)}")
            return False

    def create_scene(self, scene_config, output_file):
        """Create Home Assistant scene"""
        try:
            self.seal.log_info("Creating scene")
            scene = {
                "name": scene_config["name"],
                "entities": scene_config["entities"]
            }
            
            # Validate scene configuration
            validation = self.seal.validate_ha_scene(scene)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid scene: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(scene, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating scene: {str(e)}")
            return False

    def create_script(self, script_config, output_file):
        """Create Home Assistant script"""
        try:
            self.seal.log_info("Creating script")
            script = {
                "sequence": script_config["sequence"],
                "mode": script_config.get("mode", "single"),
                "max": script_config.get("max", 10)
            }
            
            # Validate script configuration
            validation = self.seal.validate_ha_script(script)
            if not validation["valid"]:
                self.seal.log_error(f"Invalid script: {validation['errors']}")
                return False
            
            with open(output_file, 'w') as f:
                json.dump(script, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error creating script: {str(e)}")
            return False

    def generate_device_controls(self, device_list, output_dir):
        """Generate device control configurations"""
        try:
            self.seal.log_info("Generating device controls")
            controls = {}
            
            for device in device_list:
                device_config = self.seal.generate_ha_device_config(
                    device_type=device["type"],
                    entity_id=device["entity_id"],
                    name=device["name"],
                    attributes=device.get("attributes", {})
                )
                controls[device["entity_id"]] = device_config
            
            # Generate individual control files
            for entity_id, config in controls.items():
                output_file = os.path.join(output_dir, f"{entity_id.replace('.', '_')}.json")
                with open(output_file, 'w') as f:
                    json.dump(config, f, indent=2)
            
            return True
        except Exception as e:
            self.seal.log_error(f"Error generating device controls: {str(e)}")
            return False

    def validate_controls(self, control_dir):
        """Validate device control configurations"""
        try:
            self.seal.log_info("Validating device controls")
            validation_results = {}
            
            for file in os.listdir(control_dir):
                if file.endswith('.json'):
                    with open(os.path.join(control_dir, file), 'r') as f:
                        config = json.load(f)
                    
                    validation = self.seal.validate_ha_device_config(config)
                    validation_results[file] = validation
            
            return validation_results
        except Exception as e:
            self.seal.log_error(f"Error validating controls: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Home Assistant Device Control Tool")
    parser.add_argument('--action', choices=['discover', 'automation', 'scene', 'script', 'controls', 'validate'], required=True)
    parser.add_argument('--ha-url', help="Home Assistant URL")
    parser.add_argument('--auth-token', help="Home Assistant auth token")
    parser.add_argument('--config', help="Configuration file for automation/scene/script")
    parser.add_argument('--devices', help="JSON file with device list")
    parser.add_argument('--output', help="Output file/directory")
    parser.add_argument('--control-dir', help="Directory containing control configurations")
    
    args = parser.parse_args()
    tool = HADeviceControlTool()
    
    if args.action == 'discover':
        if not args.ha_url or not args.auth_token:
            print("Error: --ha-url and --auth-token required for discovery")
            sys.exit(1)
        devices = tool.discover_devices(args.ha_url, args.auth_token)
        if devices:
            print(json.dumps(devices, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'automation':
        if not args.config or not args.output:
            print("Error: --config and --output required for automation")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_automation(config["trigger"], config["action"], args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'scene':
        if not args.config or not args.output:
            print("Error: --config and --output required for scene")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_scene(config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'script':
        if not args.config or not args.output:
            print("Error: --config and --output required for script")
            sys.exit(1)
        with open(args.config, 'r') as f:
            config = json.load(f)
        success = tool.create_script(config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'controls':
        if not args.devices or not args.output:
            print("Error: --devices and --output required for controls")
            sys.exit(1)
        with open(args.devices, 'r') as f:
            devices = json.load(f)
        success = tool.generate_device_controls(devices, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'validate':
        if not args.control_dir:
            print("Error: --control-dir required for validation")
            sys.exit(1)
        results = tool.validate_controls(args.control_dir)
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main() 