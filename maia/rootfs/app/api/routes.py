"""
API routes for MAIA.
"""
from fastapi import FastAPI, WebSocket, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
import asyncio
import logging
import json
from datetime import datetime
from ..core.voice_processor import VoiceProcessor
from ..core.camera_processor import CameraProcessor
from ..core.openai_integration import OpenAIIntegration
from ..database.storage import FaceStorage, CommandStorage

_LOGGER = logging.getLogger(__name__)

app = FastAPI(
    title="MAIA API",
    description="API for MAIA - My AI Assistant",
    version="1.0.0"
)

# Initialize processors
voice_processor = None
camera_processor = None
openai_integration = None
face_storage = None
command_storage = None

@app.on_event("startup")
async def startup():
    """Initialize components on startup."""
    global voice_processor, camera_processor, openai_integration
    global face_storage, command_storage
    
    try:
        # Initialize storage
        face_storage = FaceStorage()
        command_storage = CommandStorage()
        
        # Initialize processors with default configs
        voice_processor = VoiceProcessor({})
        camera_processor = CameraProcessor({})
        openai_integration = OpenAIIntegration({})
        
        _LOGGER.info("MAIA API initialized successfully")
        
    except Exception as e:
        _LOGGER.error(f"Failed to initialize MAIA API: {str(e)}")
        raise

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    try:
        if voice_processor:
            voice_processor.cleanup()
        if camera_processor:
            camera_processor.cleanup()
        if openai_integration:
            openai_integration.cleanup()
            
        _LOGGER.info("MAIA API shutdown complete")
        
    except Exception as e:
        _LOGGER.error(f"Error during shutdown: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "MAIA API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/voice/process")
async def process_voice(audio: UploadFile = File(...)):
    """Process voice command."""
    try:
        # Read audio data
        audio_data = await audio.read()
        
        # Process audio
        result = await voice_processor.process_audio(audio_data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to process audio")
            
        # Store command
        await command_storage.store_command(result)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        _LOGGER.error(f"Voice processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/camera/process")
async def process_frame(frame: UploadFile = File(...)):
    """Process camera frame."""
    try:
        # Read frame data
        frame_data = await frame.read()
        
        # Process frame
        result = await camera_processor.process_frame(frame_data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to process frame")
            
        return JSONResponse(content=result)
        
    except Exception as e:
        _LOGGER.error(f"Frame processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/face/register")
async def register_face(
    user_id: str,
    face_data: UploadFile = File(...),
    metadata: Optional[Dict[str, Any]] = None
):
    """Register face for user."""
    try:
        # Read face data
        face_data = await face_data.read()
        
        # Process face
        result = await camera_processor.process_frame(face_data)
        if not result or not result.get("faces"):
            raise HTTPException(status_code=400, detail="No face detected")
            
        # Get face encoding
        face = result["faces"][0]
        if not face.get("encoding"):
            raise HTTPException(status_code=400, detail="Failed to encode face")
            
        # Store face
        success = await face_storage.store_face(
            user_id,
            face["encoding"],
            metadata
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store face")
            
        return {"status": "success", "user_id": user_id}
        
    except Exception as e:
        _LOGGER.error(f"Face registration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/face/{user_id}")
async def delete_face(user_id: str):
    """Delete registered face."""
    try:
        success = await face_storage.delete_face(user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Face not found")
            
        return {"status": "success", "user_id": user_id}
        
    except Exception as e:
        _LOGGER.error(f"Face deletion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/commands/recent")
async def get_recent_commands(
    limit: int = 100,
    offset: int = 0
):
    """Get recent commands."""
    try:
        commands = await command_storage.get_recent_commands(limit, offset)
        return {"commands": commands, "total": len(commands)}
        
    except Exception as e:
        _LOGGER.error(f"Failed to get recent commands: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    try:
        await websocket.accept()
        
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process message
            if message.get("type") == "voice":
                result = await voice_processor.process_audio(
                    message.get("data", "").encode()
                )
            elif message.get("type") == "camera":
                result = await camera_processor.process_frame(
                    message.get("data", "").encode()
                )
            else:
                result = {"error": "Invalid message type"}
                
            # Send response
            await websocket.send_text(json.dumps(result))
            
    except Exception as e:
        _LOGGER.error(f"WebSocket error: {str(e)}")
        if websocket.client_state.connected:
            await websocket.close()

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "voice_processor": bool(voice_processor),
            "camera_processor": bool(camera_processor),
            "openai_integration": bool(openai_integration),
            "face_storage": bool(face_storage),
            "command_storage": bool(command_storage)
        }
    } 