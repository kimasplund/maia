#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class ConfigManagementTool:
    def __init__(self):
        self.seal = SealTools()
        
    def generate_config(self, device_info, features, output_file):
        """Generate device configuration file"""
        try:
            self.seal.log_info("Generating device configuration")
            config = {
                "device": {
                    "id": device_info["id"],
                    "name": device_info["name"],
                    "location": device_info.get("location", ""),
                    "type": "esp32cam"
                },
                "network": {
                    "wifi_ssid": device_info["wifi_ssid"],
                    "wifi_password": device_info["wifi_password"],
                    "ha_host": device_info["ha_host"],
                    "ha_port": device_info.get("ha_port", 8123),
                    "use_ssl": device_info.get("use_ssl", True)
                },
                "camera": {
                    "frame_size": features.get("frame_size", "VGA"),
                    "jpeg_quality": features.get("jpeg_quality", 12),
                    "frame_rate": features.get("frame_rate", 20)
                },
                "audio": {
                    "sample_rate": features.get("sample_rate", 16000),
                    "bit_depth": features.get("bit_depth", 16),
                    "buffer_size": features.get("buffer_size", 512)
                },
                "features": {
                    "face_detection": features.get("face_detection", True),
                    "motion_detection": features.get("motion_detection", True),
                    "audio_detection": features.get("audio_detection", True)
                },
                "security": {
                    "auth_token": device_info.get("auth_token", ""),
                    "ota_password": device_info.get("ota_password", "maia_ota_pass"),
                    "enable_https": device_info.get("enable_https", True)
                }
            }
            
            with open(output_file, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error generating config: {str(e)}")
            return False

    def validate_config(self, config_file):
        """Validate configuration file"""
        try:
            self.seal.log_info("Validating configuration")
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            validation = self.seal.validate_config(
                config=config,
                schema="esp32cam_config_schema",
                strict=True
            )
            return validation
        except Exception as e:
            self.seal.log_error(f"Error validating config: {str(e)}")
            return None

    def merge_configs(self, base_config, override_config, output_file):
        """Merge multiple configuration files"""
        try:
            self.seal.log_info("Merging configurations")
            merged = self.seal.merge_configs(
                base_config=base_config,
                override_config=override_config,
                merge_strategy="deep"
            )
            
            with open(output_file, 'w') as f:
                json.dump(merged, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error merging configs: {str(e)}")
            return False

    def encrypt_secrets(self, config_file, output_file, key_file=None):
        """Encrypt sensitive configuration data"""
        try:
            self.seal.log_info("Encrypting configuration secrets")
            if not key_file:
                key_file = self.seal.generate_key()
                
            encrypted = self.seal.encrypt_config(
                config_path=config_file,
                key_path=key_file,
                secrets=[
                    "network.wifi_password",
                    "security.auth_token",
                    "security.ota_password"
                ]
            )
            
            with open(output_file, 'w') as f:
                json.dump(encrypted, f, indent=2)
            return True
        except Exception as e:
            self.seal.log_error(f"Error encrypting config: {str(e)}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Configuration Management Tool")
    parser.add_argument('--action', choices=['generate', 'validate', 'merge', 'encrypt'], required=True)
    parser.add_argument('--device-info', help="JSON file with device information")
    parser.add_argument('--features', help="JSON file with feature configuration")
    parser.add_argument('--base-config', help="Base configuration file for merge")
    parser.add_argument('--override-config', help="Override configuration file for merge")
    parser.add_argument('--key-file', help="Key file for encryption")
    parser.add_argument('--input', help="Input configuration file")
    parser.add_argument('--output', help="Output configuration file")
    
    args = parser.parse_args()
    tool = ConfigManagementTool()
    
    if args.action == 'generate':
        if not args.device_info or not args.features or not args.output:
            print("Error: --device-info, --features, and --output required for generate")
            sys.exit(1)
            
        with open(args.device_info, 'r') as f:
            device_info = json.load(f)
        with open(args.features, 'r') as f:
            features = json.load(f)
            
        success = tool.generate_config(device_info, features, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'validate':
        if not args.input:
            print("Error: --input required for validate")
            sys.exit(1)
            
        validation = tool.validate_config(args.input)
        if validation:
            print(json.dumps(validation, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'merge':
        if not args.base_config or not args.override_config or not args.output:
            print("Error: --base-config, --override-config, and --output required for merge")
            sys.exit(1)
            
        success = tool.merge_configs(args.base_config, args.override_config, args.output)
        sys.exit(0 if success else 1)
    
    elif args.action == 'encrypt':
        if not args.input or not args.output:
            print("Error: --input and --output required for encrypt")
            sys.exit(1)
            
        success = tool.encrypt_secrets(args.input, args.output, args.key_file)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 