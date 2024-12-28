import os
import json
import time
import asyncio
import serial
import serial.tools.list_ports
from pathlib import Path
from ..core.logging import get_logger

logger = get_logger("test.esp32")

class ESP32Tester:
    def __init__(self):
        self.logger = get_logger("test.esp32.camera")
        self.serial_port = None
        self.test_data_dir = Path("test_data")
        self.test_data_dir.mkdir(exist_ok=True)
    
    def find_esp32_ports(self):
        """Find all ESP32 devices connected via USB."""
        esp_ports = []
        for port in serial.tools.list_ports.comports():
            # ESP32 usually shows up as CP2102 USB to UART or similar
            if "CP210" in port.description or "CH340" in port.description:
                esp_ports.append({
                    "port": port.device,
                    "description": port.description,
                    "hwid": port.hwid
                })
                self.logger.debug(
                    "Found ESP32 device",
                    port=port.device,
                    description=port.description
                )
        return esp_ports
    
    async def connect_camera(self, port: str, wifi_config: dict):
        """Connect to ESP32-CAM and configure it."""
        try:
            self.logger.info("Connecting to ESP32-CAM", port=port)
            self.serial_port = serial.Serial(port, 115200, timeout=1)
            time.sleep(2)  # Wait for ESP32 to reset
            
            # Send WiFi configuration
            config_json = json.dumps(wifi_config)
            self.serial_port.write(f"{config_json}\n".encode())
            
            # Wait for connection confirmation
            timeout = 30
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode().strip()
                    self.logger.debug("ESP32-CAM output", message=line)
                    if "WiFi connected" in line:
                        self.logger.info("ESP32-CAM connected to WiFi")
                        return True
                await asyncio.sleep(0.1)
            
            self.logger.error("ESP32-CAM WiFi connection timeout")
            return False
            
        except Exception as e:
            self.logger.error(
                "Failed to connect to ESP32-CAM",
                error=str(e),
                port=port
            )
            return False
    
    async def test_camera_capture(self):
        """Test camera capture and upload."""
        try:
            self.logger.info("Testing camera capture")
            
            # Wait for image upload
            timeout = 30
            start_time = time.time()
            image_received = False
            
            while time.time() - start_time < timeout and not image_received:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode().strip()
                    self.logger.debug("ESP32-CAM output", message=line)
                    if "Image uploaded successfully" in line:
                        image_received = True
                        self.logger.info("Camera capture test successful")
                        break
                await asyncio.sleep(0.1)
            
            if not image_received:
                self.logger.error("Camera capture test timeout")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Camera capture test failed",
                error=str(e)
            )
            return False
    
    def close(self):
        """Close serial connection."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.logger.info("Closed serial connection")

async def main():
    """Run ESP32 integration tests."""
    # First test logging
    print("Testing logging system...")
    logger.info("Starting ESP32 integration tests")
    
    # Initialize ESP32 tester
    tester = ESP32Tester()
    
    try:
        # Find ESP32 devices
        print("\nSearching for ESP32 devices...")
        esp_ports = tester.find_esp32_ports()
        
        if not esp_ports:
            print("No ESP32 devices found!")
            return
        
        print(f"\nFound {len(esp_ports)} ESP32 device(s):")
        for i, port_info in enumerate(esp_ports):
            print(f"{i+1}. {port_info['description']} on {port_info['port']}")
        
        # Let user select device
        selection = int(input("\nSelect device to test (1-{}): ".format(len(esp_ports))))
        selected_port = esp_ports[selection-1]["port"]
        
        # Get WiFi configuration
        wifi_config = {
            "ssid": input("Enter WiFi SSID: "),
            "password": input("Enter WiFi password: "),
            "maia_url": input("Enter MAIA server URL: ")
        }
        
        # Connect to ESP32-CAM
        print("\nConnecting to ESP32-CAM...")
        if await tester.connect_camera(selected_port, wifi_config):
            print("ESP32-CAM connected successfully!")
            
            # Test camera
            print("\nTesting camera capture...")
            if await tester.test_camera_capture():
                print("Camera test successful!")
            else:
                print("Camera test failed!")
        else:
            print("Failed to connect to ESP32-CAM!")
    
    except Exception as e:
        logger.error(
            "Test failed",
            error=str(e)
        )
        raise
    finally:
        tester.close()

if __name__ == "__main__":
    asyncio.run(main()) 