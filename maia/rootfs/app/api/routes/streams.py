from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from ..schemas import StreamCreate, StreamResponse
from ..database import get_db
from ..core.companion_detector import CompanionManager
from ..core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/streams", response_model=StreamResponse)
async def create_stream(stream: StreamCreate, db: Session = Depends(get_db)):
    """Register a new external stream."""
    try:
        logger.info(f"Registering new external stream: {stream.name}")
        companion_manager = CompanionManager()
        stream_device = await companion_manager.register_external_stream(
            name=stream.name,
            url=stream.url,
            stream_type=stream.type,
            auth_type=stream.auth_type,
            auth_data=stream.auth_data
        )
        logger.info(f"Successfully registered stream {stream.name} with ID {stream_device.id}")
        return stream_device
    except Exception as e:
        logger.error(f"Failed to register stream {stream.name}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/streams", response_model=List[StreamResponse])
async def list_streams(db: Session = Depends(get_db)):
    """List all registered external streams."""
    try:
        logger.info("Fetching list of external streams")
        companion_manager = CompanionManager()
        streams = await companion_manager.get_external_streams()
        return streams
    except Exception as e:
        logger.error(f"Failed to fetch streams: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/streams/{stream_id}", response_model=StreamResponse)
async def get_stream(stream_id: str, db: Session = Depends(get_db)):
    """Get details of a specific external stream."""
    try:
        logger.info(f"Fetching details for stream {stream_id}")
        companion_manager = CompanionManager()
        stream = await companion_manager.get_external_stream(stream_id)
        if not stream:
            raise HTTPException(status_code=404, detail="Stream not found")
        return stream
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch stream {stream_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/streams/{stream_id}")
async def delete_stream(stream_id: str, db: Session = Depends(get_db)):
    """Remove an external stream."""
    try:
        logger.info(f"Removing stream {stream_id}")
        companion_manager = CompanionManager()
        await companion_manager.remove_external_stream(stream_id)
        logger.info(f"Successfully removed stream {stream_id}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to remove stream {stream_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/streams/{stream_id}", response_model=StreamResponse)
async def update_stream(stream_id: str, stream: StreamCreate, db: Session = Depends(get_db)):
    """Update an external stream's configuration."""
    try:
        logger.info(f"Updating stream {stream_id}")
        companion_manager = CompanionManager()
        updated_stream = await companion_manager.update_external_stream(
            stream_id,
            name=stream.name,
            url=stream.url,
            stream_type=stream.type,
            auth_type=stream.auth_type,
            auth_data=stream.auth_data
        )
        logger.info(f"Successfully updated stream {stream_id}")
        return updated_stream
    except Exception as e:
        logger.error(f"Failed to update stream {stream_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/streams/{stream_id}/check")
async def check_stream_health(stream_id: str, db: Session = Depends(get_db)):
    """Check the health of an external stream."""
    try:
        logger.info(f"Checking health of stream {stream_id}")
        companion_manager = CompanionManager()
        health_status = await companion_manager.check_external_stream_health(stream_id)
        return health_status
    except Exception as e:
        logger.error(f"Failed to check stream health {stream_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 