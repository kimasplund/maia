"""
MAIA Node API implementation.
Provides REST and WebSocket endpoints for node communication and task management.
"""
from typing import Dict, List, Optional, Any
import logging
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Header, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import asyncio
import json
from datetime import datetime
import nvidia_smi
from .maia_node import MAIANode, NodeCapabilities
from .gpu_monitor import GPUMonitor

_LOGGER = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="MAIA Node API", version="1.0.0")
security = HTTPBearer()

# Initialize NVIDIA Management Library
nvidia_smi.nvmlInit()

class TaskSubmission(BaseModel):
    """Task submission model."""
    type: str = Field(..., description="Task type (image_processing, voice_processing, etc.)")
    data: Dict[str, Any] = Field(..., description="Task data")
    requires_gpu: bool = Field(False, description="Whether task requires GPU")
    required_memory: int = Field(0, description="Required memory in MB")
    priority: int = Field(0, description="Task priority (0-10)")
    timeout: Optional[int] = Field(None, description="Task timeout in seconds")

class TaskResult(BaseModel):
    """Task result model."""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime

class NodeInfo(BaseModel):
    """Node information model."""
    node_name: str
    capabilities: NodeCapabilities
    stats: Dict[str, Any]
    active_tasks: int
    queued_tasks: int

async def verify_node_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Verify node authentication key."""
    try:
        if not credentials or not credentials.credentials:
            raise HTTPException(status_code=401, detail="Missing authentication")
            
        # Get node instance
        node = app.state.node
        if not node:
            raise HTTPException(status_code=503, detail="Node not initialized")
            
        # Verify key
        if credentials.credentials != node.node_key:
            raise HTTPException(status_code=401, detail="Invalid authentication")
            
        return credentials.credentials
        
    except Exception as e:
        _LOGGER.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

@app.on_event("startup")
async def startup():
    """Initialize node on startup."""
    try:
        # Initialize GPU monitor
        app.state.gpu_monitor = GPUMonitor()
        await app.state.gpu_monitor.start()
        
        # Initialize node
        app.state.node = app.state.get_node_instance()
        if not app.state.node:
            raise Exception("Node instance not found")
            
        await app.state.node.start()
        _LOGGER.info("Node API started successfully")
        
    except Exception as e:
        _LOGGER.error(f"Failed to start node API: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    try:
        if hasattr(app.state, "gpu_monitor"):
            await app.state.gpu_monitor.stop()
            
        if hasattr(app.state, "node"):
            await app.state.node.cleanup()
            
        nvidia_smi.nvmlShutdown()
        _LOGGER.info("Node API shutdown complete")
        
    except Exception as e:
        _LOGGER.error(f"Error during shutdown: {str(e)}")

@app.post("/task", response_model=str)
async def submit_task(
    task: TaskSubmission,
    _: str = Depends(verify_node_key)
) -> str:
    """Submit task for processing."""
    try:
        # Get node instance
        node = app.state.node
        if not node:
            raise HTTPException(status_code=503, detail="Node not initialized")
            
        # Submit task
        task_id = await node.submit_task(task.dict())
        return task_id
        
    except Exception as e:
        _LOGGER.error(f"Failed to submit task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/task/{task_id}", response_model=TaskResult)
async def get_task_status(
    task_id: str,
    _: str = Depends(verify_node_key)
) -> TaskResult:
    """Get task status and result."""
    try:
        # Get node instance
        node = app.state.node
        if not node:
            raise HTTPException(status_code=503, detail="Node not initialized")
            
        # Get task status
        task = node.processing_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        if not task.done():
            return TaskResult(
                task_id=task_id,
                status="processing",
                timestamp=datetime.now()
            )
            
        # Get task result
        try:
            result = await task
            return TaskResult(
                task_id=task_id,
                status="completed",
                result=result,
                timestamp=datetime.now()
            )
        except Exception as e:
            return TaskResult(
                task_id=task_id,
                status="failed",
                error=str(e),
                timestamp=datetime.now()
            )
            
    except Exception as e:
        _LOGGER.error(f"Failed to get task status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/info", response_model=NodeInfo)
async def get_node_info(
    _: str = Depends(verify_node_key)
) -> NodeInfo:
    """Get node information and status."""
    try:
        # Get node instance
        node = app.state.node
        if not node:
            raise HTTPException(status_code=503, detail="Node not initialized")
            
        # Get GPU stats if available
        gpu_stats = {}
        if app.state.gpu_monitor:
            gpu_stats = await app.state.gpu_monitor.get_stats()
            
        return NodeInfo(
            node_name=node.node_name,
            capabilities=node._get_capabilities(),
            stats={
                "gpu": gpu_stats,
                "tasks": {
                    "active": len(node.processing_tasks),
                    "queued": node.task_queue.qsize()
                }
            },
            active_tasks=len(node.processing_tasks),
            queued_tasks=node.task_queue.qsize()
        )
        
    except Exception as e:
        _LOGGER.error(f"Failed to get node info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    try:
        # Accept connection
        await websocket.accept()
        
        # Verify authentication
        try:
            auth = await websocket.receive_text()
            if not auth.startswith("Bearer "):
                raise ValueError("Invalid authentication format")
            
            token = auth.split(" ")[1]
            if token != app.state.node.node_key:
                raise ValueError("Invalid authentication token")
                
        except Exception as e:
            await websocket.close(code=4001, reason="Authentication failed")
            return
            
        # Start update loop
        while True:
            try:
                # Get node stats
                node = app.state.node
                gpu_stats = await app.state.gpu_monitor.get_stats() if app.state.gpu_monitor else {}
                
                # Send update
                await websocket.send_json({
                    "timestamp": datetime.now().isoformat(),
                    "node_name": node.node_name,
                    "stats": {
                        "gpu": gpu_stats,
                        "tasks": {
                            "active": len(node.processing_tasks),
                            "queued": node.task_queue.qsize()
                        }
                    }
                })
                
                await asyncio.sleep(1)  # Update every second
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                _LOGGER.error(f"WebSocket error: {str(e)}")
                break
                
    except Exception as e:
        _LOGGER.error(f"WebSocket connection failed: {str(e)}")
    finally:
        try:
            await websocket.close()
        except:
            pass

@app.post("/task/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    _: str = Depends(verify_node_key)
) -> Dict[str, Any]:
    """Cancel a running task."""
    try:
        # Get node instance
        node = app.state.node
        if not node:
            raise HTTPException(status_code=503, detail="Node not initialized")
            
        # Get task
        task = node.processing_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        # Cancel task
        task.cancel()
        
        return {
            "task_id": task_id,
            "status": "cancelled",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        _LOGGER.error(f"Failed to cancel task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 