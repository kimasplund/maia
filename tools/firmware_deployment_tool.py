#!/usr/bin/env python3

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent directory to path for seal_tools import
sys.path.append(str(Path(__file__).parent.parent.parent.parent))
from core.seal_tools_integration import SealTools

class FirmwareDeploymentTool:
    def __init__(self):
        self.seal = SealTools()
        
    def build_firmware(self, config_file, output_dir):
        """Build firmware with specified configuration"""
        try:
            self.seal.log_info("Building firmware")
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            build_result = self.seal.build_firmware(
                config=config,
                output_dir=output_dir,
                platform="esp32cam",
                build_flags={
                    "PSRAM": "enabled",
                    "COMPONENT_EMBED_FILES": ["face_detection_model:models/face_detection.tflite"]
                }
            )
            return build_result
        except Exception as e:
            self.seal.log_error(f"Error building firmware: {str(e)}")
            return None

    def flash_device(self, firmware_file, port, baud_rate=921600):
        """Flash firmware to ESP32-CAM device"""
        try:
            self.seal.log_info(f"Flashing device on port {port}")
            flash_result = self.seal.flash_device(
                firmware_path=firmware_file,
                port=port,
                baud_rate=baud_rate,
                flash_mode="qio",
                flash_freq="80m",
                flash_size="4MB"
            )
            return flash_result
        except Exception as e:
            self.seal.log_error(f"Error flashing device: {str(e)}")
            return None

    def verify_firmware(self, port, expected_version):
        """Verify flashed firmware"""
        try:
            self.seal.log_info("Verifying firmware")
            verification = self.seal.verify_firmware(
                port=port,
                expected_version=expected_version,
                timeout=30
            )
            return verification
        except Exception as e:
            self.seal.log_error(f"Error verifying firmware: {str(e)}")
            return None

    def deploy_ota(self, firmware_file, devices):
        """Deploy firmware via OTA to multiple devices"""
        try:
            self.seal.log_info("Deploying OTA update")
            results = {}
            for device in devices:
                result = self.seal.deploy_ota(
                    firmware_path=firmware_file,
                    device_ip=device["ip"],
                    device_port=device.get("port", 3232),
                    auth_token=device.get("auth_token", "maia_ota_pass")
                )
                results[device["ip"]] = result
            return results
        except Exception as e:
            self.seal.log_error(f"Error deploying OTA update: {str(e)}")
            return None

    def backup_firmware(self, port, backup_file):
        """Backup existing firmware"""
        try:
            self.seal.log_info("Backing up firmware")
            backup = self.seal.backup_firmware(
                port=port,
                output_file=backup_file
            )
            return backup
        except Exception as e:
            self.seal.log_error(f"Error backing up firmware: {str(e)}")
            return None

def main():
    parser = argparse.ArgumentParser(description="Firmware Deployment Tool")
    parser.add_argument('--action', choices=['build', 'flash', 'verify', 'ota', 'backup'], required=True)
    parser.add_argument('--config', help="Configuration file for build")
    parser.add_argument('--output', help="Output directory/file")
    parser.add_argument('--port', help="Serial port for device")
    parser.add_argument('--baud-rate', type=int, default=921600, help="Baud rate for flashing")
    parser.add_argument('--version', help="Expected firmware version for verification")
    parser.add_argument('--devices', help="JSON file with device list for OTA")
    
    args = parser.parse_args()
    tool = FirmwareDeploymentTool()
    
    if args.action == 'build':
        if not args.config or not args.output:
            print("Error: --config and --output required for build")
            sys.exit(1)
        result = tool.build_firmware(args.config, args.output)
        if result:
            print(json.dumps(result, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'flash':
        if not args.output or not args.port:
            print("Error: --output and --port required for flash")
            sys.exit(1)
        result = tool.flash_device(args.output, args.port, args.baud_rate)
        if result:
            print(json.dumps(result, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'verify':
        if not args.port or not args.version:
            print("Error: --port and --version required for verify")
            sys.exit(1)
        result = tool.verify_firmware(args.port, args.version)
        if result:
            print(json.dumps(result, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'ota':
        if not args.output or not args.devices:
            print("Error: --output and --devices required for OTA")
            sys.exit(1)
        with open(args.devices, 'r') as f:
            devices = json.load(f)
        results = tool.deploy_ota(args.output, devices)
        if results:
            print(json.dumps(results, indent=2))
            sys.exit(0)
        sys.exit(1)
    
    elif args.action == 'backup':
        if not args.port or not args.output:
            print("Error: --port and --output required for backup")
            sys.exit(1)
        result = tool.backup_firmware(args.port, args.output)
        if result:
            print(json.dumps(result, indent=2))
            sys.exit(0)
        sys.exit(1)

if __name__ == "__main__":
    main() 