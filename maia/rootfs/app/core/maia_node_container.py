"""
MAIA Node container implementation.
Handles Docker container management for distributed processing nodes.
"""
from typing import Dict, List, Optional, Any
import asyncio
import logging
import docker
from docker.models.containers import Container
from pathlib import Path
import json
import os

_LOGGER = logging.getLogger(__name__)

class MAIANodeContainer:
    """MAIA Node container manager."""
    
    CONTAINER_PREFIX = "maia_node_"
    BASE_IMAGE = "maia/node:latest"
    
    def __init__(self, docker_client: Optional[docker.DockerClient] = None):
        """Initialize container manager."""
        self.docker = docker_client or docker.from_env()
        self.active_containers: Dict[str, Container] = {}
        
    async def start_container(
        self,
        node_key: str,
        node_name: str,
        host_port: int,
        gpu: bool = False,
        memory_limit: str = "4g",
        cpu_limit: float = 1.0
    ) -> Container:
        """Start a new MAIA Node container."""
        try:
            # Prepare container configuration
            container_name = f"{self.CONTAINER_PREFIX}{node_name}"
            
            # Remove existing container if any
            try:
                old_container = self.docker.containers.get(container_name)
                old_container.remove(force=True)
            except docker.errors.NotFound:
                pass
                
            # Prepare volume mounts
            volumes = {
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "ro"},
                str(Path.home() / ".maia" / "models"): {"bind": "/models", "mode": "rw"},
                str(Path.home() / ".maia" / "data"): {"bind": "/data", "mode": "rw"}
            }
            
            # Prepare environment variables
            environment = {
                "MAIA_NODE_KEY": node_key,
                "MAIA_NODE_NAME": node_name,
                "MAIA_NODE_PORT": "5555",  # Internal container port
                "NVIDIA_VISIBLE_DEVICES": "all" if gpu else "none"
            }
            
            # Prepare device requests for GPU
            device_requests = []
            if gpu:
                device_requests.append(docker.types.DeviceRequest(
                    count=-1,
                    capabilities=[["gpu"]]
                ))
                
            # Create and start container
            container = self.docker.containers.run(
                self.BASE_IMAGE,
                name=container_name,
                detach=True,
                volumes=volumes,
                environment=environment,
                ports={"5555/tcp": host_port},
                restart_policy={"Name": "unless-stopped"},
                device_requests=device_requests,
                mem_limit=memory_limit,
                cpu_period=100000,  # Default period
                cpu_quota=int(cpu_limit * 100000),  # Quota based on limit
                labels={
                    "app": "maia",
                    "type": "node",
                    "name": node_name
                }
            )
            
            self.active_containers[node_name] = container
            _LOGGER.info(f"Started MAIA Node container: {node_name}")
            
            return container
            
        except Exception as e:
            _LOGGER.error(f"Failed to start container: {str(e)}")
            raise
            
    async def stop_container(self, node_name: str) -> bool:
        """Stop a MAIA Node container."""
        try:
            container = self.active_containers.get(node_name)
            if not container:
                container_name = f"{self.CONTAINER_PREFIX}{node_name}"
                try:
                    container = self.docker.containers.get(container_name)
                except docker.errors.NotFound:
                    return False
                    
            container.stop(timeout=10)
            container.remove(force=True)
            
            if node_name in self.active_containers:
                del self.active_containers[node_name]
                
            _LOGGER.info(f"Stopped MAIA Node container: {node_name}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to stop container: {str(e)}")
            return False
            
    async def list_containers(self) -> List[Dict[str, Any]]:
        """List all MAIA Node containers."""
        try:
            containers = self.docker.containers.list(
                filters={
                    "label": ["app=maia", "type=node"]
                }
            )
            
            return [
                {
                    "name": container.labels.get("name", "unknown"),
                    "id": container.id,
                    "status": container.status,
                    "ports": container.ports,
                    "created": container.attrs["Created"]
                }
                for container in containers
            ]
            
        except Exception as e:
            _LOGGER.error(f"Failed to list containers: {str(e)}")
            return []
            
    async def get_container_stats(self, node_name: str) -> Optional[Dict[str, Any]]:
        """Get container statistics."""
        try:
            container = self.active_containers.get(node_name)
            if not container:
                container_name = f"{self.CONTAINER_PREFIX}{node_name}"
                try:
                    container = self.docker.containers.get(container_name)
                except docker.errors.NotFound:
                    return None
                    
            stats = container.stats(stream=False)
            
            # Process CPU stats
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0
            
            # Process memory stats
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100.0
            
            return {
                "cpu_percent": cpu_percent,
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": memory_percent,
                "network_rx": stats["networks"]["eth0"]["rx_bytes"],
                "network_tx": stats["networks"]["eth0"]["tx_bytes"]
            }
            
        except Exception as e:
            _LOGGER.error(f"Failed to get container stats: {str(e)}")
            return None
            
    async def update_container(
        self,
        node_name: str,
        memory_limit: Optional[str] = None,
        cpu_limit: Optional[float] = None
    ) -> bool:
        """Update container resource limits."""
        try:
            container = self.active_containers.get(node_name)
            if not container:
                container_name = f"{self.CONTAINER_PREFIX}{node_name}"
                try:
                    container = self.docker.containers.get(container_name)
                except docker.errors.NotFound:
                    return False
                    
            update_config = {}
            
            if memory_limit:
                update_config["mem_limit"] = memory_limit
                
            if cpu_limit is not None:
                update_config["cpu_period"] = 100000
                update_config["cpu_quota"] = int(cpu_limit * 100000)
                
            container.update(**update_config)
            _LOGGER.info(f"Updated container resources: {node_name}")
            return True
            
        except Exception as e:
            _LOGGER.error(f"Failed to update container: {str(e)}")
            return False
            
    async def cleanup(self):
        """Clean up all containers."""
        try:
            containers = await self.list_containers()
            for container in containers:
                await self.stop_container(container["name"])
                
        except Exception as e:
            _LOGGER.error(f"Error during cleanup: {str(e)}")
            
    def __del__(self):
        """Cleanup on deletion."""
        if self.docker:
            self.docker.close() 