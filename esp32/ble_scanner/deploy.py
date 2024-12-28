#!/usr/bin/env python3
"""
Deployment script for ESP32 BLE scanner firmware.
Handles firmware compilation, upload, and initial configuration.
"""
import os
import sys
import time
import json
import serial
import serial.tools.list_ports
import subprocess
import argparse
import logging
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

class ESP32Deployer:
    """ESP32 firmware deployment handler."""
    
    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        arduino_cli_path: Optional[str] = None
    ):
        """Initialize deployer."""
        self.port = port
        self.baud_rate = baud_rate
        self.arduino_cli = arduino_cli_path or self._find_arduino_cli()
        
    def _find_arduino_cli(self) -> str:
        """Find arduino-cli executable."""
        # Check common paths
        paths = [
            "arduino-cli",
            os.path.expanduser("~/.arduino15/arduino-cli"),
            os.path.expanduser("~/Arduino/arduino-cli"),
            "C:\\Program Files\\Arduino\\arduino-cli.exe",
            "C:\\Program Files (x86)\\Arduino\\arduino-cli.exe"
        ]
        
        for path in paths:
            try:
                subprocess.run(
                    [path, "version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                return path
            except:
                continue
                
        raise RuntimeError(
            "arduino-cli not found. Please install it or specify path."
        )
        
    def _find_esp32_port(self) -> Optional[str]:
        """Find ESP32 serial port."""
        ports = list(serial.tools.list_ports.comports())
        
        for port in ports:
            if "CP210" in port.description or "CH340" in port.description:
                return port.device
                
        return None
        
    def _run_arduino_cli(
        self,
        command: List[str],
        check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run arduino-cli command."""
        try:
            result = subprocess.run(
                [self.arduino_cli] + command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            _LOGGER.error(f"Arduino CLI error: {e.stderr}")
            raise
            
    def setup_environment(self):
        """Set up Arduino environment."""
        _LOGGER.info("Setting up Arduino environment...")
        
        # Update index
        self._run_arduino_cli(["core", "update-index"])
        
        # Install ESP32 core if needed
        try:
            self._run_arduino_cli(
                ["core", "install", "esp32:esp32"],
                check=False
            )
        except:
            pass
            
        # Install required libraries
        libraries = [
            "WiFi",
            "PubSubClient",
            "ArduinoJson",
            "ESP32 BLE Arduino"
        ]
        
        for lib in libraries:
            try:
                self._run_arduino_cli(
                    ["lib", "install", lib],
                    check=False
                )
            except:
                pass
                
    def compile_firmware(self, sketch_path: str):
        """Compile firmware."""
        _LOGGER.info("Compiling firmware...")
        
        self._run_arduino_cli([
            "compile",
            "--fqbn", "esp32:esp32:esp32",
            sketch_path
        ])
        
    def upload_firmware(self, sketch_path: str):
        """Upload firmware to ESP32."""
        _LOGGER.info("Uploading firmware...")
        
        # Find port if not specified
        port = self.port or self._find_esp32_port()
        if not port:
            raise RuntimeError("ESP32 not found. Please specify port.")
            
        self._run_arduino_cli([
            "upload",
            "--fqbn", "esp32:esp32:esp32",
            "--port", port,
            sketch_path
        ])
        
    def configure_device(
        self,
        config: Dict[str, Any],
        timeout: int = 30
    ):
        """Configure device via serial."""
        _LOGGER.info("Configuring device...")
        
        # Find port if not specified
        port = self.port or self._find_esp32_port()
        if not port:
            raise RuntimeError("ESP32 not found. Please specify port.")
            
        # Open serial connection
        with serial.Serial(port, self.baud_rate, timeout=1) as ser:
            # Wait for device to boot
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ser.in_waiting:
                    line = ser.readline().decode().strip()
                    if "WiFi connection failed" in line:
                        # Device is ready for configuration
                        break
                        
            # Send configuration
            config_json = json.dumps(config)
            ser.write(f"CONFIG:{config_json}\n".encode())
            
            # Wait for confirmation
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ser.in_waiting:
                    line = ser.readline().decode().strip()
                    if "Configuration updated" in line:
                        _LOGGER.info("Device configured successfully")
                        return
                        
            raise TimeoutError("Configuration timeout")
            
def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="ESP32 BLE Scanner deployment tool"
    )
    
    parser.add_argument(
        "--port",
        help="Serial port for ESP32"
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baud rate"
    )
    parser.add_argument(
        "--arduino-cli",
        help="Path to arduino-cli executable"
    )
    parser.add_argument(
        "--config",
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Skip firmware compilation"
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip firmware upload"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize deployer
        deployer = ESP32Deployer(
            port=args.port,
            baud_rate=args.baud,
            arduino_cli_path=args.arduino_cli
        )
        
        # Setup environment
        deployer.setup_environment()
        
        # Get sketch path
        sketch_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "ble_scanner.ino"
        )
        
        # Compile firmware
        if not args.skip_compile:
            deployer.compile_firmware(sketch_path)
            
        # Upload firmware
        if not args.skip_upload:
            deployer.upload_firmware(sketch_path)
            
        # Configure device if config provided
        if args.config:
            with open(args.config) as f:
                config = json.load(f)
            deployer.configure_device(config)
            
        _LOGGER.info("Deployment completed successfully")
        
    except Exception as e:
        _LOGGER.error(f"Deployment failed: {str(e)}")
        sys.exit(1)
        
if __name__ == "__main__":
    main() 