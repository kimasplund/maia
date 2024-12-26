"""
Storage module for MAIA.
Handles face and command data storage.
"""
import redis
import json
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
import asyncio
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

class StorageBase:
    """Base class for storage handlers."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        """Initialize storage base."""
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.prefix = "maia:"
        
    def _key(self, *parts: str) -> str:
        """Create Redis key with prefix."""
        return f"{self.prefix}{':'.join(parts)}"
        
    def _encode_array(self, arr: np.ndarray) -> str:
        """Encode numpy array to string."""
        return json.dumps(arr.tolist())
        
    def _decode_array(self, s: str) -> np.ndarray:
        """Decode string to numpy array."""
        return np.array(json.loads(s))
        
class FaceStorage(StorageBase):
    """Storage handler for face data."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        """Initialize face storage."""
        super().__init__(redis_host, redis_port)
        self.prefix = "maia:face:"
        
    async def store_face(
        self,
        user_id: str,
        encoding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store face encoding and metadata."""
        try:
            # Store face encoding
            encoding_key = self._key(user_id, "encoding")
            await self.redis.set(
                encoding_key,
                self._encode_array(encoding)
            )
            
            # Store metadata if provided
            if metadata:
                metadata_key = self._key(user_id, "metadata")
                await self.redis.hmset(metadata_key, metadata)
                
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to store face: {str(e)}")
            return False
            
    async def get_face(
        self,
        user_id: str
    ) -> Tuple[Optional[np.ndarray], Optional[Dict[str, Any]]]:
        """Get face encoding and metadata."""
        try:
            # Get face encoding
            encoding_key = self._key(user_id, "encoding")
            encoding_str = await self.redis.get(encoding_key)
            encoding = self._decode_array(encoding_str) if encoding_str else None
            
            # Get metadata
            metadata_key = self._key(user_id, "metadata")
            metadata = await self.redis.hgetall(metadata_key)
            
            return encoding, metadata
            
        except Exception as e:
            _LOGGER.error(f"Failed to get face: {str(e)}")
            return None, None
            
    def get_all_encodings_sync(self) -> Dict[str, np.ndarray]:
        """Get all face encodings (synchronous version)."""
        try:
            # Get all user IDs
            pattern = self._key("*", "encoding")
            encoding_keys = self.redis.keys(pattern)
            
            # Get encodings
            encodings = {}
            for key in encoding_keys:
                user_id = key.split(":")[-2]
                encoding_str = self.redis.get(key)
                if encoding_str:
                    encodings[user_id] = self._decode_array(encoding_str)
                    
            return encodings
            
        except Exception as e:
            _LOGGER.error(f"Failed to get all encodings: {str(e)}")
            return {}
            
    def get_user_info_sync(self, user_id: str) -> Dict[str, Any]:
        """Get user info (synchronous version)."""
        try:
            metadata_key = self._key(user_id, "metadata")
            return self.redis.hgetall(metadata_key)
            
        except Exception as e:
            _LOGGER.error(f"Failed to get user info: {str(e)}")
            return {}
            
    async def delete_face(self, user_id: str) -> bool:
        """Delete face data."""
        try:
            # Delete encoding and metadata
            encoding_key = self._key(user_id, "encoding")
            metadata_key = self._key(user_id, "metadata")
            
            await self.redis.delete(encoding_key, metadata_key)
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to delete face: {str(e)}")
            return False
            
class CommandStorage(StorageBase):
    """Storage handler for command data."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        """Initialize command storage."""
        super().__init__(redis_host, redis_port)
        self.prefix = "maia:cmd:"
        
    async def store_command(
        self,
        command: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Store command data."""
        try:
            # Generate command ID
            cmd_id = f"cmd_{datetime.now().timestamp()}"
            cmd_key = self._key(cmd_id)
            
            # Store command data
            await self.redis.hmset(cmd_key, command)
            
            # Set TTL if specified
            if ttl:
                await self.redis.expire(cmd_key, ttl)
                
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to store command: {str(e)}")
            return False
            
    async def get_command(self, cmd_id: str) -> Optional[Dict[str, Any]]:
        """Get command data."""
        try:
            cmd_key = self._key(cmd_id)
            return await self.redis.hgetall(cmd_key)
            
        except Exception as e:
            _LOGGER.error(f"Failed to get command: {str(e)}")
            return None
            
    async def get_recent_commands(
        self,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get recent commands."""
        try:
            # Get command keys sorted by timestamp
            pattern = self._key("cmd_*")
            cmd_keys = await self.redis.keys(pattern)
            cmd_keys.sort(reverse=True)
            
            # Apply limit and offset
            cmd_keys = cmd_keys[offset:offset + limit]
            
            # Get command data
            commands = []
            for key in cmd_keys:
                cmd_data = await self.redis.hgetall(key)
                if cmd_data:
                    commands.append(cmd_data)
                    
            return commands
            
        except Exception as e:
            _LOGGER.error(f"Failed to get recent commands: {str(e)}")
            return []
            
    async def delete_old_commands(
        self,
        days: int = 30
    ) -> int:
        """Delete commands older than specified days."""
        try:
            # Calculate cutoff timestamp
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_ts = cutoff.timestamp()
            
            # Get all command keys
            pattern = self._key("cmd_*")
            cmd_keys = await self.redis.keys(pattern)
            
            # Delete old commands
            deleted = 0
            for key in cmd_keys:
                try:
                    # Extract timestamp from key
                    ts = float(key.split("_")[-1])
                    if ts < cutoff_ts:
                        await self.redis.delete(key)
                        deleted += 1
                except ValueError:
                    continue
                    
            return deleted
            
        except Exception as e:
            _LOGGER.error(f"Failed to delete old commands: {str(e)}")
            return 0 