import os
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class HAClient:
    """Home Assistant API client."""
    
    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        """Initialize the client.
        
        If url and token are not provided, assumes running as an add-on
        and uses the supervisor API.
        """
        self.base_url = url or os.getenv("SUPERVISOR_URL", "http://supervisor/core")
        self.token = token or os.getenv("SUPERVISOR_TOKEN")
        if not self.token:
            raise ValueError("No Home Assistant token provided")
            
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        
    async def validate_token(self) -> bool:
        """Validate the authentication token."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/",
                    headers=self.headers
                ) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"Failed to validate token: {e}")
            return False
            
    async def get_config(self) -> Dict[str, Any]:
        """Get Home Assistant configuration."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/config",
                headers=self.headers
            ) as response:
                return await response.json()
                
    async def register_device(self, device_info: Dict[str, Any]) -> Dict[str, Any]:
        """Register a device in Home Assistant."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/device_registry",
                headers=self.headers,
                json=device_info
            ) as response:
                return await response.json()
                
    async def create_entity(self, entity_info: Dict[str, Any]) -> Dict[str, Any]:
        """Create an entity in Home Assistant."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/states/{entity_info['entity_id']}",
                headers=self.headers,
                json={"state": entity_info["state"], "attributes": entity_info.get("attributes", {})}
            ) as response:
                return await response.json()
                
    async def update_entity(self, entity_id: str, state: str, attributes: Dict[str, Any] = None) -> Dict[str, Any]:
        """Update an entity's state in Home Assistant."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/states/{entity_id}",
                headers=self.headers,
                json={"state": state, "attributes": attributes or {}}
            ) as response:
                return await response.json()
                
    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user information."""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/api/auth/current_user",
                headers=self.headers
            ) as response:
                return await response.json() 