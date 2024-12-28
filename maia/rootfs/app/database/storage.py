"""
Storage module for MAIA.
Handles face and command data storage using Valkey.
"""
import json
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging
import asyncio
from datetime import datetime, timedelta
from ..core.valkey_pool import ValKeyPool, ValKeyConnection

_LOGGER = logging.getLogger(__name__)

class ValKeyError(Exception):
    """Valkey specific errors."""
    pass

class StorageBase:
    """Base class for storage handlers."""
    
    def __init__(
        self,
        valkey_host: str = "valkey",
        valkey_port: int = 7000,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        command_timeout: float = 5.0
    ):
        """Initialize storage base."""
        self.pool = ValKeyPool(
            host=valkey_host,
            port=valkey_port,
            min_size=min_pool_size,
            max_size=max_pool_size,
            connection_timeout=command_timeout,
            health_check_interval=30  # 30 seconds
        )
        self.prefix = "maia:"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.command_timeout = command_timeout
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start storage handler."""
        await self.pool.start()
        # Start health check task
        self._health_check_task = asyncio.create_task(self._monitor_health())
        
    async def stop(self):
        """Stop storage handler."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        await self.pool.stop()
        
    async def _monitor_health(self):
        """Monitor storage health and log issues."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                stats = self.pool.get_stats()
                
                # Log warnings for concerning stats
                if stats["unhealthy_connections"] > 0:
                    _LOGGER.warning(
                        f"{stats['unhealthy_connections']} unhealthy Valkey connections detected"
                    )
                
                if stats["total_errors"] > 0:
                    error_rate = stats["total_errors"] / max(stats["total_commands"], 1)
                    if error_rate > 0.1:  # More than 10% error rate
                        _LOGGER.warning(
                            f"High Valkey error rate: {error_rate:.1%} "
                            f"({stats['total_errors']}/{stats['total_commands']} commands failed)"
                        )
                
                # Log detailed connection stats at debug level
                for conn_stat in stats["connection_stats"]:
                    if not conn_stat["is_healthy"]:
                        _LOGGER.debug(
                            f"Unhealthy connection {conn_stat['id']}: "
                            f"{conn_stat['consecutive_errors']} consecutive errors, "
                            f"last error: {conn_stat['last_error']}"
                        )
                    
            except Exception as e:
                _LOGGER.error(f"Error in health monitor: {str(e)}")
        
    def _key(self, *parts: str) -> str:
        """Create Valkey key with prefix."""
        return f"{self.prefix}{':'.join(parts)}"
        
    def _encode_array(self, arr: np.ndarray) -> str:
        """Encode numpy array to string."""
        return json.dumps(arr.tolist())
        
    def _decode_array(self, s: str) -> np.ndarray:
        """Decode string to numpy array."""
        return np.array(json.loads(s))
        
    async def _valkey_cmd(self, *args) -> str:
        """Execute Valkey command with retries using connection pool."""
        last_error = None
        conn: Optional[ValKeyConnection] = None
        
        for attempt in range(self.max_retries):
            try:
                # Get connection from pool
                if not conn:
                    conn = await self.pool.acquire()
                
                try:
                    # Execute command with timeout
                    return await asyncio.wait_for(
                        conn.execute(*args),
                        timeout=self.command_timeout
                    )
                except asyncio.TimeoutError:
                    _LOGGER.warning(f"Command timed out on attempt {attempt + 1}")
                    # Force connection check on timeout
                    await conn.health_check()
                    raise
                finally:
                    if conn:
                        await self.pool.release(conn)
                        conn = None
                    
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    _LOGGER.warning(
                        f"Valkey command failed (attempt {attempt + 1}/{self.max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    # Get fresh connection for retry
                    if conn:
                        await self.pool.release(conn)
                        conn = None
                continue
                
        _LOGGER.error(f"Valkey command failed after {self.max_retries} attempts: {str(last_error)}")
        raise ValKeyError(f"Command failed: {str(last_error)}")
        
    async def ensure_connection(self) -> bool:
        """Ensure Valkey connection is available."""
        try:
            # Try to execute a PING command
            await self._valkey_cmd("PING")
            
            # Check pool health
            stats = self.pool.get_stats()
            if stats["unhealthy_connections"] > 0:
                _LOGGER.warning(
                    f"Pool has {stats['unhealthy_connections']} unhealthy connections"
                )
                
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to connect to Valkey: {str(e)}")
            return False
            
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed storage statistics."""
        pool_stats = self.pool.get_stats()
        return {
            "pool": pool_stats,
            "prefix": self.prefix,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "command_timeout": self.command_timeout,
            "error_rate": (
                pool_stats["total_errors"] / max(pool_stats["total_commands"], 1)
            )
        }

class FaceStorage(StorageBase):
    """Storage handler for face data using Valkey."""
    
    def __init__(
        self,
        valkey_host: str = "valkey",
        valkey_port: int = 7000,
        min_pool_size: int = 2,
        max_pool_size: int = 10
    ):
        """Initialize face storage."""
        super().__init__(
            valkey_host=valkey_host,
            valkey_port=valkey_port,
            min_pool_size=min_pool_size,
            max_pool_size=max_pool_size,
            max_retries=3,
            retry_delay=1.0,
            command_timeout=5.0
        )
        self.prefix = "maia:face:"
        
    async def store_face(
        self,
        user_id: str,
        encoding: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store face encoding and metadata."""
        try:
            # Store face encoding with pipeline
            encoding_key = self._key(user_id, "encoding")
            await self._valkey_cmd("SET", encoding_key, self._encode_array(encoding))
            
            # Store metadata if provided
            if metadata:
                metadata_key = self._key(user_id, "metadata")
                # Build HSET command with multiple field-value pairs
                hset_args = ["HSET", metadata_key]
                for key, value in metadata.items():
                    hset_args.extend([key, json.dumps(value)])
                await self._valkey_cmd(*hset_args)
                    
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
            encoding_str = await self._valkey_cmd("GET", encoding_key)
            encoding = self._decode_array(encoding_str) if encoding_str else None
            
            # Get metadata
            metadata_key = self._key(user_id, "metadata")
            metadata_str = await self._valkey_cmd("HGETALL", metadata_key)
            metadata = {}
            if metadata_str:
                pairs = metadata_str.split("\n")
                for i in range(0, len(pairs), 2):
                    if i + 1 < len(pairs):
                        metadata[pairs[i]] = json.loads(pairs[i + 1])
                        
            return encoding, metadata
            
        except Exception as e:
            _LOGGER.error(f"Failed to get face: {str(e)}")
            return None, None

class CommandStorage(StorageBase):
    """Storage handler for command data using Valkey."""
    
    def __init__(
        self,
        valkey_host: str = "valkey",
        valkey_port: int = 7000,
        min_pool_size: int = 2,
        max_pool_size: int = 10
    ):
        """Initialize command storage."""
        super().__init__(
            valkey_host=valkey_host,
            valkey_port=valkey_port,
            min_pool_size=min_pool_size,
            max_pool_size=max_pool_size,
            max_retries=3,
            retry_delay=1.0,
            command_timeout=5.0
        )
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
            
            # Build HSET command with multiple field-value pairs
            hset_args = ["HSET", cmd_key]
            for key, value in command.items():
                hset_args.extend([key, json.dumps(value)])
            
            # Store command data
            await self._valkey_cmd(*hset_args)
                
            # Set TTL if specified
            if ttl:
                await self._valkey_cmd("EXPIRE", cmd_key, str(ttl))
                
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to store command: {str(e)}")
            return False
            
    async def get_command(self, cmd_id: str) -> Optional[Dict[str, Any]]:
        """Get command data."""
        try:
            cmd_key = self._key(cmd_id)
            result = await self._valkey_cmd("HGETALL", cmd_key)
            
            command = {}
            if result:
                pairs = result.split("\n")
                for i in range(0, len(pairs), 2):
                    if i + 1 < len(pairs):
                        command[pairs[i]] = json.loads(pairs[i + 1])
                        
            return command
            
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
            keys_str = await self._valkey_cmd("KEYS", pattern)
            cmd_keys = sorted(keys_str.split("\n") if keys_str else [], reverse=True)
            
            # Apply limit and offset
            cmd_keys = cmd_keys[offset:offset + limit]
            
            # Get command data in parallel
            tasks = [self.get_command(key.split(":")[-1]) for key in cmd_keys]
            commands = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out errors and None values
            return [cmd for cmd in commands if cmd and isinstance(cmd, dict)]
            
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
            keys_str = await self._valkey_cmd("KEYS", pattern)
            cmd_keys = keys_str.split("\n") if keys_str else []
            
            # Delete old commands in batches
            deleted = 0
            batch_size = 100
            del_keys = []
            
            for key in cmd_keys:
                try:
                    # Extract timestamp from key
                    ts = float(key.split("_")[-1])
                    if ts < cutoff_ts:
                        del_keys.append(key)
                        if len(del_keys) >= batch_size:
                            # Delete batch
                            await self._valkey_cmd("DEL", *del_keys)
                            deleted += len(del_keys)
                            del_keys = []
                except ValueError:
                    continue
                    
            # Delete remaining keys
            if del_keys:
                await self._valkey_cmd("DEL", *del_keys)
                deleted += len(del_keys)
                
            return deleted
            
        except Exception as e:
            _LOGGER.error(f"Failed to delete old commands: {str(e)}")
            return 0 