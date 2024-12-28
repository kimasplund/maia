"""
Valkey connection pooling and monitoring system.
"""
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    """Connection statistics."""
    created_at: datetime
    last_used: datetime
    total_commands: int
    errors: int
    avg_response_time: float
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    health_check_failures: int = 0

class ValKeyConnection:
    """Managed Valkey connection."""
    
    def __init__(self, host: str, port: int):
        """Initialize connection."""
        self.host = host
        self.port = port
        self.stats = ConnectionStats(
            created_at=datetime.now(),
            last_used=datetime.now(),
            total_commands=0,
            errors=0,
            avg_response_time=0.0
        )
        self._lock = asyncio.Lock()
        self.is_healthy = True
        
    async def execute(self, *args) -> str:
        """Execute Valkey command with monitoring."""
        async with self._lock:
            start_time = time.time()
            try:
                # Execute command
                cmd = ["valkey", "-h", self.host, "-p", str(self.port)] + list(args)
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                
                # Update stats
                execution_time = time.time() - start_time
                self.stats.total_commands += 1
                self.stats.last_used = datetime.now()
                self.stats.avg_response_time = (
                    (self.stats.avg_response_time * (self.stats.total_commands - 1) + execution_time)
                    / self.stats.total_commands
                )
                
                if proc.returncode != 0:
                    self.stats.errors += 1
                    self.stats.consecutive_errors += 1
                    error_msg = stderr.decode().strip()
                    self.stats.last_error = error_msg
                    raise ValueError(f"Valkey command failed: {error_msg}")
                
                # Reset error counters on success
                self.stats.consecutive_errors = 0
                self.stats.last_error = None
                return stdout.decode().strip()
                
            except Exception as e:
                self.stats.errors += 1
                self.stats.consecutive_errors += 1
                self.stats.last_error = str(e)
                raise
                
    async def health_check(self) -> bool:
        """Check connection health."""
        try:
            result = await self.execute("PING")
            self.is_healthy = result == "PONG"
            if not self.is_healthy:
                self.stats.health_check_failures += 1
            return self.is_healthy
        except Exception as e:
            self.is_healthy = False
            self.stats.health_check_failures += 1
            _LOGGER.warning(f"Health check failed for connection {id(self)}: {str(e)}")
            return False

class ValKeyPool:
    """Connection pool for Valkey."""
    
    def __init__(
        self,
        host: str = "valkey",
        port: int = 7000,
        min_size: int = 2,
        max_size: int = 10,
        max_idle_time: int = 300,  # 5 minutes
        health_check_interval: int = 60,  # 1 minute
        max_consecutive_errors: int = 3,
        connection_timeout: float = 5.0
    ):
        """Initialize connection pool."""
        self.host = host
        self.port = port
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.health_check_interval = health_check_interval
        self.max_consecutive_errors = max_consecutive_errors
        self.connection_timeout = connection_timeout
        
        self._available: List[ValKeyConnection] = []
        self._in_use: Dict[str, ValKeyConnection] = {}
        self._lock = asyncio.Lock()
        self._maintenance_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start connection pool."""
        try:
            # Create initial connections
            for _ in range(self.min_size):
                conn = await self._create_connection()
                if conn:
                    self._available.append(conn)
                
            # Start maintenance and health check tasks
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            _LOGGER.info(f"Valkey connection pool started with {len(self._available)} connections")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start connection pool: {str(e)}")
            raise
            
    async def stop(self):
        """Stop connection pool."""
        try:
            # Cancel maintenance and health check tasks
            for task in [self._maintenance_task, self._health_check_task]:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    
            # Clear connections
            self._available.clear()
            self._in_use.clear()
            _LOGGER.info("Valkey connection pool stopped")
            
        except Exception as e:
            _LOGGER.error(f"Error stopping connection pool: {str(e)}")
            
    async def _create_connection(self) -> Optional[ValKeyConnection]:
        """Create and validate new connection."""
        try:
            conn = ValKeyConnection(self.host, self.port)
            # Validate connection with health check
            if await conn.health_check():
                return conn
            return None
        except Exception as e:
            _LOGGER.error(f"Failed to create connection: {str(e)}")
            return None
            
    async def acquire(self) -> ValKeyConnection:
        """Acquire connection from pool."""
        async with self._lock:
            start_time = time.time()
            while True:
                # Check timeout
                if time.time() - start_time > self.connection_timeout:
                    raise TimeoutError("Failed to acquire connection from pool")
                
                # Try to get healthy available connection
                for i, conn in enumerate(self._available):
                    if conn.is_healthy:
                        self._available.pop(i)
                        self._in_use[id(conn)] = conn
                        return conn
                
                # Create new connection if possible
                if len(self._in_use) < self.max_size:
                    conn = await self._create_connection()
                    if conn:
                        self._in_use[id(conn)] = conn
                        return conn
                
                # Wait for connection to become available
                try:
                    await asyncio.wait_for(self._lock.acquire(), timeout=1.0)
                    self._lock.release()
                except asyncio.TimeoutError:
                    continue
                    
    async def release(self, conn: ValKeyConnection):
        """Release connection back to pool."""
        async with self._lock:
            conn_id = id(conn)
            if conn_id in self._in_use:
                del self._in_use[conn_id]
                # Only return healthy connections to the pool
                if conn.is_healthy and conn.stats.consecutive_errors < self.max_consecutive_errors:
                    self._available.append(conn)
                else:
                    _LOGGER.warning(f"Discarding unhealthy connection {conn_id}")
                
    async def _maintenance_loop(self):
        """Maintenance loop for connection pool."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                async with self._lock:
                    current_time = datetime.now()
                    
                    # Remove idle and unhealthy connections (but maintain min_size)
                    idle_limit = len(self._available) - self.min_size
                    if idle_limit > 0:
                        to_remove = []
                        for conn in self._available:
                            # Check idle time and health
                            is_idle = (current_time - conn.stats.last_used).total_seconds() > self.max_idle_time
                            is_unhealthy = (not conn.is_healthy or 
                                          conn.stats.consecutive_errors >= self.max_consecutive_errors)
                            
                            if is_idle or is_unhealthy:
                                to_remove.append(conn)
                                
                            if len(to_remove) >= idle_limit:
                                break
                                
                        for conn in to_remove:
                            self._available.remove(conn)
                            
                    # Ensure minimum connections
                    while len(self._available) < self.min_size:
                        conn = await self._create_connection()
                        if conn:
                            self._available.append(conn)
                            
                    # Log pool stats
                    self._log_pool_stats()
                    
            except Exception as e:
                _LOGGER.error(f"Error in maintenance loop: {str(e)}")
                
    async def _health_check_loop(self):
        """Health check loop for connections."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                async with self._lock:
                    # Check all connections
                    for conn in self._available + list(self._in_use.values()):
                        await conn.health_check()
                        
            except Exception as e:
                _LOGGER.error(f"Error in health check loop: {str(e)}")
                
    def _log_pool_stats(self):
        """Log detailed pool statistics."""
        stats = self.get_stats()
        _LOGGER.debug(
            "Pool stats - "
            f"Total: {stats['total_connections']}, "
            f"Available: {stats['available_connections']}, "
            f"In use: {stats['in_use_connections']}, "
            f"Commands: {stats['total_commands']}, "
            f"Errors: {stats['total_errors']}, "
            f"Avg response time: {stats['avg_response_time']:.3f}s"
        )
                
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed pool statistics."""
        total_connections = len(self._available) + len(self._in_use)
        total_commands = 0
        total_errors = 0
        total_response_time = 0.0
        health_check_failures = 0
        unhealthy_connections = 0
        
        # Collect stats from all connections
        for conn in self._available + list(self._in_use.values()):
            total_commands += conn.stats.total_commands
            total_errors += conn.stats.errors
            total_response_time += (
                conn.stats.avg_response_time * conn.stats.total_commands
            )
            health_check_failures += conn.stats.health_check_failures
            if not conn.is_healthy:
                unhealthy_connections += 1
            
        return {
            "total_connections": total_connections,
            "available_connections": len(self._available),
            "in_use_connections": len(self._in_use),
            "total_commands": total_commands,
            "total_errors": total_errors,
            "avg_response_time": (
                total_response_time / total_commands if total_commands > 0 else 0.0
            ),
            "health_check_failures": health_check_failures,
            "unhealthy_connections": unhealthy_connections,
            "connection_stats": [
                {
                    "id": id(conn),
                    "is_healthy": conn.is_healthy,
                    "consecutive_errors": conn.stats.consecutive_errors,
                    "last_error": conn.stats.last_error,
                    "total_commands": conn.stats.total_commands,
                    "errors": conn.stats.errors,
                    "avg_response_time": conn.stats.avg_response_time
                }
                for conn in self._available + list(self._in_use.values())
            ]
        } 