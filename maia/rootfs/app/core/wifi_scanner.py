"""
WiFi scanner for MAIA.
Handles WiFi network scanning.
"""
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import subprocess
import re
import json
from .scanner_base import BaseScanner, ScannerRegistry, ScanResult, ScannerLocation

_LOGGER = logging.getLogger(__name__)

class WiFiScanner(BaseScanner):
    """Handles WiFi network scanning."""
    
    def __init__(
        self,
        scanner_id: str,
        registry: ScannerRegistry,
        is_mobile: bool = False,
        location: Optional[ScannerLocation] = None,
        metadata: Optional[Dict[str, Any]] = None,
        scan_interval: float = 10.0  # seconds
    ):
        """Initialize WiFi scanner."""
        super().__init__(
            scanner_id=scanner_id,
            scanner_type="wifi",
            is_mobile=is_mobile,
            registry=registry,
            location=location,
            metadata=metadata
        )
        self._scan_interval = scan_interval
        self._scanning = False
        self._scan_task = None
        
    async def start(self):
        """Start WiFi scanning."""
        try:
            if self._scanning:
                return True
                
            # Start scan loop
            self._scanning = True
            self._scan_task = asyncio.create_task(self._scan_loop())
            _LOGGER.info(f"WiFi scanner {self._scanner_id} started")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to start WiFi scanner: {str(e)}")
            return False
            
    async def stop(self):
        """Stop WiFi scanning."""
        try:
            self._scanning = False
            if self._scan_task:
                self._scan_task.cancel()
                try:
                    await self._scan_task
                except asyncio.CancelledError:
                    pass
            _LOGGER.info(f"WiFi scanner {self._scanner_id} stopped")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to stop WiFi scanner: {str(e)}")
            return False
            
    async def _scan_loop(self):
        """Main scanning loop."""
        while self._scanning:
            try:
                # Perform scan
                networks = await self._scan_networks()
                
                # Process results
                timestamp = datetime.now()
                for network in networks:
                    result = ScanResult(
                        timestamp=timestamp,
                        scanner_id=self._scanner_id,
                        device_id=network["bssid"],
                        rssi=network["rssi"],
                        metadata={
                            "ssid": network["ssid"],
                            "channel": network["channel"],
                            "frequency": network["frequency"],
                            "capabilities": network["capabilities"]
                        }
                    )
                    await self._handle_detection(result)
                    
            except Exception as e:
                _LOGGER.error(f"Error in scan loop: {str(e)}")
                
            # Wait for next scan
            await asyncio.sleep(self._scan_interval)
            
    async def _scan_networks(self) -> List[Dict[str, Any]]:
        """Scan for WiFi networks."""
        try:
            networks = []
            
            # Try using iw command first
            try:
                output = await self._run_command(["iw", "dev", "wlan0", "scan"])
                networks.extend(self._parse_iw_output(output))
            except:
                _LOGGER.debug("iw scan failed, trying iwlist")
                
            # Fall back to iwlist
            if not networks:
                try:
                    output = await self._run_command(["iwlist", "wlan0", "scan"])
                    networks.extend(self._parse_iwlist_output(output))
                except:
                    _LOGGER.error("Both iw and iwlist scans failed")
                    
            return networks
            
        except Exception as e:
            _LOGGER.error(f"Failed to scan networks: {str(e)}")
            return []
            
    @staticmethod
    async def _run_command(cmd: List[str]) -> str:
        """Run shell command asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Command failed: {stderr.decode()}")
        return stdout.decode()
        
    def _parse_iw_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse iw scan output."""
        networks = []
        current_network = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            if line.startswith("BSS "):
                if current_network:
                    networks.append(current_network)
                current_network = {
                    "bssid": line.split()[1].lower(),
                    "rssi": -100,  # Default value
                    "ssid": "",
                    "channel": 0,
                    "frequency": 0,
                    "capabilities": []
                }
                
            elif current_network:
                if "signal:" in line:
                    # Convert dBm to RSSI
                    dbm = float(line.split("signal:")[1].split()[0])
                    current_network["rssi"] = int(dbm)
                    
                elif "SSID:" in line:
                    current_network["ssid"] = line.split("SSID:")[1].strip()
                    
                elif "freq:" in line:
                    current_network["frequency"] = int(line.split("freq:")[1].split()[0])
                    current_network["channel"] = self._freq_to_channel(current_network["frequency"])
                    
                elif "capability:" in line:
                    current_network["capabilities"] = line.split("capability:")[1].strip().split()
                    
        if current_network:
            networks.append(current_network)
            
        return networks
        
    def _parse_iwlist_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse iwlist scan output."""
        networks = []
        current_network = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            if "Cell" in line and "Address:" in line:
                if current_network:
                    networks.append(current_network)
                current_network = {
                    "bssid": line.split("Address:")[1].strip().lower(),
                    "rssi": -100,  # Default value
                    "ssid": "",
                    "channel": 0,
                    "frequency": 0,
                    "capabilities": []
                }
                
            elif current_network:
                if "Quality" in line and "Signal level" in line:
                    # Parse signal level
                    match = re.search(r"Signal level[=:](-\d+) dBm", line)
                    if match:
                        current_network["rssi"] = int(match.group(1))
                        
                elif "ESSID:" in line:
                    current_network["ssid"] = line.split('ESSID:"')[1].strip('"')
                    
                elif "Frequency:" in line:
                    match = re.search(r"(\d+\.\d+) GHz", line)
                    if match:
                        freq = float(match.group(1)) * 1000
                        current_network["frequency"] = int(freq)
                        current_network["channel"] = self._freq_to_channel(current_network["frequency"])
                        
                elif "Encryption key:" in line:
                    if "on" in line.lower():
                        current_network["capabilities"].append("WPA2")
                        
        if current_network:
            networks.append(current_network)
            
        return networks
        
    @staticmethod
    def _freq_to_channel(freq: int) -> int:
        """Convert frequency to channel number."""
        if 2412 <= freq <= 2484:
            return (freq - 2412) // 5 + 1
        elif 5170 <= freq <= 5825:
            return (freq - 5170) // 5 + 34
        return 0 