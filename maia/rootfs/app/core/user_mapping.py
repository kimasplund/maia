"""
User mapping handler for MAIA.
Links BLE devices to Home Assistant users.
"""
from typing import Dict, Optional, List
import logging
import json
import os
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

class UserMapping:
    """Maps BLE devices to Home Assistant users."""
    
    def __init__(self):
        """Initialize user mapping."""
        self._config_dir = Path("/config")
        self._mapping_file = self._config_dir / "user_mapping.json"
        self._device_to_user: Dict[str, str] = {}
        self._user_to_devices: Dict[str, List[str]] = {}
        self._load_mapping()
        
    def _load_mapping(self):
        """Load mapping from file."""
        try:
            if self._mapping_file.exists():
                with open(self._mapping_file, 'r') as f:
                    data = json.load(f)
                    self._device_to_user = data.get("device_to_user", {})
                    self._user_to_devices = data.get("user_to_devices", {})
                _LOGGER.info(f"Loaded user mapping: {len(self._device_to_user)} devices mapped")
            else:
                _LOGGER.info("No existing user mapping found")
        except Exception as e:
            _LOGGER.error(f"Failed to load user mapping: {str(e)}")
            
    def _save_mapping(self):
        """Save mapping to file."""
        try:
            data = {
                "device_to_user": self._device_to_user,
                "user_to_devices": self._user_to_devices
            }
            with open(self._mapping_file, 'w') as f:
                json.dump(data, f, indent=2)
            _LOGGER.info("Saved user mapping")
        except Exception as e:
            _LOGGER.error(f"Failed to save user mapping: {str(e)}")
            
    def map_device_to_user(self, device_mac: str, ha_user: str) -> bool:
        """Map a device to a Home Assistant user."""
        try:
            # Remove existing mapping if any
            if device_mac in self._device_to_user:
                old_user = self._device_to_user[device_mac]
                if old_user in self._user_to_devices:
                    self._user_to_devices[old_user].remove(device_mac)
                    
            # Add new mapping
            self._device_to_user[device_mac] = ha_user
            if ha_user not in self._user_to_devices:
                self._user_to_devices[ha_user] = []
            if device_mac not in self._user_to_devices[ha_user]:
                self._user_to_devices[ha_user].append(device_mac)
                
            self._save_mapping()
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to map device to user: {str(e)}")
            return False
            
    def unmap_device(self, device_mac: str) -> bool:
        """Remove device mapping."""
        try:
            if device_mac in self._device_to_user:
                ha_user = self._device_to_user[device_mac]
                del self._device_to_user[device_mac]
                if ha_user in self._user_to_devices:
                    self._user_to_devices[ha_user].remove(device_mac)
                self._save_mapping()
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to unmap device: {str(e)}")
            return False
            
    def get_user_for_device(self, device_mac: str) -> Optional[str]:
        """Get Home Assistant user for device."""
        return self._device_to_user.get(device_mac)
        
    def get_devices_for_user(self, ha_user: str) -> List[str]:
        """Get devices mapped to Home Assistant user."""
        return self._user_to_devices.get(ha_user, []) 