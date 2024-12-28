"""
Automation tools for MAIA.
"""
from typing import Dict, List, Optional, Any
import logging
import json
import aiohttp
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

class AutomationTools:
    """Home Assistant automation tools."""
    
    def __init__(self, ha_url: str, ha_token: str):
        """Initialize automation tools."""
        self.ha_url = ha_url.rstrip('/')
        self.ha_token = ha_token
        self.headers = {
            "Authorization": f"Bearer {ha_token}",
            "Content-Type": "application/json"
        }
        
    async def call_service(
        self,
        domain: str,
        service: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call Home Assistant service."""
        try:
            url = f"{self.ha_url}/api/services/{domain}/{service}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data or {}, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        raise Exception(f"Service call failed: {error}")
                        
        except Exception as e:
            _LOGGER.error(f"Failed to call service {domain}.{service}: {str(e)}")
            return {"error": str(e)}
            
    async def get_state(self, entity_id: str) -> Dict[str, Any]:
        """Get entity state."""
        try:
            url = f"{self.ha_url}/api/states/{entity_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        raise Exception(f"Failed to get state: {error}")
                        
        except Exception as e:
            _LOGGER.error(f"Failed to get state for {entity_id}: {str(e)}")
            return {"error": str(e)}
            
    async def set_state(
        self,
        entity_id: str,
        state: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set entity state."""
        try:
            url = f"{self.ha_url}/api/states/{entity_id}"
            data = {
                "state": state,
                "attributes": attributes or {}
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        raise Exception(f"Failed to set state: {error}")
                        
        except Exception as e:
            _LOGGER.error(f"Failed to set state for {entity_id}: {str(e)}")
            return {"error": str(e)}
            
    async def trigger_automation(
        self,
        automation_id: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger automation."""
        return await self.call_service(
            "automation",
            "trigger",
            {
                "entity_id": automation_id,
                **(data or {})
            }
        )
        
    async def toggle_entity(self, entity_id: str) -> Dict[str, Any]:
        """Toggle entity state."""
        try:
            # Get domain from entity_id
            domain = entity_id.split('.')[0]
            
            return await self.call_service(
                domain,
                "toggle",
                {"entity_id": entity_id}
            )
            
        except Exception as e:
            _LOGGER.error(f"Failed to toggle {entity_id}: {str(e)}")
            return {"error": str(e)}
            
    async def get_history(
        self,
        entity_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get entity state history."""
        try:
            url = f"{self.ha_url}/api/history/period"
            params = {"filter_entity_id": entity_id}
            
            if start_time:
                params["start_time"] = start_time.isoformat()
            if end_time:
                params["end_time"] = end_time.isoformat()
                
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        raise Exception(f"Failed to get history: {error}")
                        
        except Exception as e:
            _LOGGER.error(f"Failed to get history for {entity_id}: {str(e)}")
            return []
            
    async def create_script(
        self,
        script_id: str,
        sequence: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create or update script."""
        try:
            url = f"{self.ha_url}/api/config/script/config/{script_id}"
            data = {
                "sequence": sequence,
                "mode": "single"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error = await response.text()
                        raise Exception(f"Failed to create script: {error}")
                        
        except Exception as e:
            _LOGGER.error(f"Failed to create script {script_id}: {str(e)}")
            return {"error": str(e)} 