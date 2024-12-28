"""
MAIA Node implementation for distributed processing.
Handles node discovery, task distribution, and resource management.
"""
from typing import Dict, List, Optional, Any
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import docker
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo
from cryptography.fernet import Fernet

_LOGGER = logging.getLogger(__name__)

@dataclass
class NodeCapabilities:
    """Node capabilities and resources."""
    cpu_count: int
    gpu_available: bool
    gpu_name: Optional[str]
    memory_total: int  # In MB
    memory_available: int  # In MB
    docker_available: bool
    supported_tasks: List[str]

class MAIANode:
    """MAIA distributed processing node."""
    
    SERVICE_TYPE = "_maia-node._tcp.local."
    
    def __init__(
        self,
        node_key: str,
        host: str = "0.0.0.0",
        port: int = 5555,
        node_name: Optional[str] = None
    ):
        """Initialize MAIA Node."""
        self.node_key = node_key
        self.host = host
        self.port = port
        self.node_name = node_name or os.uname()[1]
        
        # Initialize encryption
        self.cipher = Fernet(node_key.encode())
        
        # Initialize node discovery
        self.zeroconf = Zeroconf()
        self.browser = None
        self.known_nodes: Dict[str, NodeCapabilities] = {}
        
        # Initialize Docker client if available
        try:
            self.docker = docker.from_env()
            self.docker_available = True
        except:
            self.docker = None
            self.docker_available = False
            
        # Initialize task queue
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        
    async def start(self):
        """Start the MAIA Node."""
        try:
            # Register service
            info = ServiceInfo(
                self.SERVICE_TYPE,
                f"{self.node_name}.{self.SERVICE_TYPE}",
                addresses=[self.host.encode()],
                port=self.port,
                properties={
                    "name": self.node_name,
                    "capabilities": json.dumps(self._get_capabilities())
                }
            )
            self.zeroconf.register_service(info)
            
            # Start service browser
            self.browser = ServiceBrowser(
                self.zeroconf,
                self.SERVICE_TYPE,
                handlers=[self._handle_service_state_change]
            )
            
            # Start task processor
            asyncio.create_task(self._process_tasks())
            
            _LOGGER.info(f"MAIA Node started: {self.node_name}")
            
        except Exception as e:
            _LOGGER.error(f"Failed to start MAIA Node: {str(e)}")
            raise
            
    def _get_capabilities(self) -> NodeCapabilities:
        """Get node capabilities."""
        try:
            import psutil
            import torch
            
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            gpu_available = torch.cuda.is_available()
            gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
            
            return NodeCapabilities(
                cpu_count=cpu_count,
                gpu_available=gpu_available,
                gpu_name=gpu_name,
                memory_total=memory.total // (1024 * 1024),  # Convert to MB
                memory_available=memory.available // (1024 * 1024),
                docker_available=self.docker_available,
                supported_tasks=[
                    "image_processing",
                    "voice_processing",
                    "ml_training",
                    "video_analysis"
                ]
            )
        except Exception as e:
            _LOGGER.error(f"Failed to get capabilities: {str(e)}")
            return NodeCapabilities(
                cpu_count=1,
                gpu_available=False,
                gpu_name=None,
                memory_total=0,
                memory_available=0,
                docker_available=self.docker_available,
                supported_tasks=[]
            )
            
    def _handle_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: str):
        """Handle service state changes."""
        try:
            if state_change == "Added":
                info = zeroconf.get_service_info(service_type, name)
                if info:
                    node_name = info.properties.get(b"name", b"").decode()
                    capabilities = json.loads(info.properties.get(b"capabilities", b"{}").decode())
                    self.known_nodes[node_name] = NodeCapabilities(**capabilities)
                    _LOGGER.info(f"New MAIA Node discovered: {node_name}")
                    
            elif state_change == "Removed":
                node_name = name.replace(f".{service_type}", "")
                if node_name in self.known_nodes:
                    del self.known_nodes[node_name]
                    _LOGGER.info(f"MAIA Node removed: {node_name}")
                    
        except Exception as e:
            _LOGGER.error(f"Error handling service state change: {str(e)}")
            
    async def submit_task(self, task: Dict[str, Any]) -> str:
        """Submit a task for processing."""
        try:
            # Encrypt task data
            task_data = json.dumps(task).encode()
            encrypted_data = self.cipher.encrypt(task_data)
            
            # Generate task ID
            task_id = f"task_{int(time.time())}_{len(self.processing_tasks)}"
            
            # Add to queue
            await self.task_queue.put({
                "id": task_id,
                "data": encrypted_data,
                "timestamp": datetime.now().isoformat()
            })
            
            return task_id
            
        except Exception as e:
            _LOGGER.error(f"Failed to submit task: {str(e)}")
            raise
            
    async def _process_tasks(self):
        """Process tasks from queue."""
        while True:
            try:
                # Get task from queue
                task = await self.task_queue.get()
                
                # Decrypt task data
                encrypted_data = task["data"]
                task_data = json.loads(self.cipher.decrypt(encrypted_data))
                
                # Find best node for task
                best_node = self._find_best_node(task_data)
                
                if best_node == self.node_name:
                    # Process locally
                    processing_task = asyncio.create_task(
                        self._process_task(task["id"], task_data)
                    )
                    self.processing_tasks[task["id"]] = processing_task
                else:
                    # Forward to other node
                    await self._forward_task(best_node, task)
                    
            except Exception as e:
                _LOGGER.error(f"Error processing task: {str(e)}")
                await asyncio.sleep(1)
                
    def _find_best_node(self, task: Dict[str, Any]) -> str:
        """Find best node to process task."""
        try:
            task_type = task.get("type", "")
            required_memory = task.get("required_memory", 0)
            requires_gpu = task.get("requires_gpu", False)
            
            best_node = self.node_name
            best_score = self._calculate_node_score(
                self._get_capabilities(),
                task_type,
                required_memory,
                requires_gpu
            )
            
            for node_name, capabilities in self.known_nodes.items():
                score = self._calculate_node_score(
                    capabilities,
                    task_type,
                    required_memory,
                    requires_gpu
                )
                if score > best_score:
                    best_node = node_name
                    best_score = score
                    
            return best_node
            
        except Exception as e:
            _LOGGER.error(f"Error finding best node: {str(e)}")
            return self.node_name
            
    def _calculate_node_score(
        self,
        capabilities: NodeCapabilities,
        task_type: str,
        required_memory: int,
        requires_gpu: bool
    ) -> float:
        """Calculate node score for task."""
        score = 0.0
        
        # Check basic requirements
        if required_memory > capabilities.memory_available:
            return 0.0
        if requires_gpu and not capabilities.gpu_available:
            return 0.0
        if task_type not in capabilities.supported_tasks:
            return 0.0
            
        # Calculate score based on resources
        score += capabilities.memory_available / (required_memory * 2)  # Memory headroom
        score += capabilities.cpu_count  # CPU cores
        if requires_gpu and capabilities.gpu_available:
            score += 10.0  # GPU bonus
            
        return score
        
    async def _process_task(self, task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task locally."""
        try:
            task_type = task.get("type", "")
            
            if task_type == "image_processing":
                result = await self._process_image(task)
            elif task_type == "voice_processing":
                result = await self._process_voice(task)
            elif task_type == "ml_training":
                result = await self._train_model(task)
            elif task_type == "video_analysis":
                result = await self._analyze_video(task)
            else:
                raise ValueError(f"Unsupported task type: {task_type}")
                
            return {
                "task_id": task_id,
                "status": "completed",
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            _LOGGER.error(f"Error processing task {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
    async def _forward_task(self, node_name: str, task: Dict[str, Any]):
        """Forward task to another node."""
        try:
            info = self.zeroconf.get_service_info(
                self.SERVICE_TYPE,
                f"{node_name}.{self.SERVICE_TYPE}"
            )
            if not info:
                raise ValueError(f"Node not found: {node_name}")
                
            host = info.addresses[0].decode()
            port = info.port
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"http://{host}:{port}/task",
                    json=task,
                    headers={"Authorization": f"Bearer {self.node_key}"}
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Failed to forward task: {await response.text()}")
                        
        except Exception as e:
            _LOGGER.error(f"Error forwarding task to {node_name}: {str(e)}")
            # Fallback to local processing
            await self.task_queue.put(task)
            
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Unregister service
            self.zeroconf.unregister_service(
                f"{self.node_name}.{self.SERVICE_TYPE}"
            )
            self.zeroconf.close()
            
            # Cancel processing tasks
            for task in self.processing_tasks.values():
                task.cancel()
                
            # Close Docker client
            if self.docker:
                self.docker.close()
                
        except Exception as e:
            _LOGGER.error(f"Error during cleanup: {str(e)}") 