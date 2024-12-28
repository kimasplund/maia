from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import traceback

from ..database import get_db
from ..models import HAUser, Face, Voice, Device, TrainingFeedback
from ..schemas import (
    UserCreate, UserUpdate, UserResponse,
    FaceResponse, VoiceResponse, DeviceResponse,
    DataMapping, TrainingFeedbackCreate
)
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.get("/users", response_model=List[UserResponse])
async def get_users(db: Session = Depends(get_db)):
    """Get all users with their associated data."""
    try:
        logger.info("Fetching all users")
        users = db.query(HAUser).all()
        logger.info("Successfully fetched users", count=len(users))
        return users
    except Exception as e:
        logger.error(
            "Failed to fetch users",
            error=str(e),
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user mapping."""
    try:
        logger.info(
            "Creating new user",
            user_data=user.dict(exclude_unset=True)
        )
        db_user = HAUser(**user.dict())
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(
            "Successfully created user",
            user_id=db_user.id,
            user_name=db_user.name
        )
        return db_user
    except Exception as e:
        logger.error(
            "Failed to create user",
            error=str(e),
            user_data=user.dict(exclude_unset=True),
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user's details."""
    try:
        logger.info("Fetching user details", user_id=user_id)
        user = db.query(HAUser).filter(HAUser.id == user_id).first()
        if not user:
            logger.warning("User not found", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        logger.info("Successfully fetched user details", user_id=user_id)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to fetch user details",
            error=str(e),
            user_id=user_id,
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user: UserUpdate, db: Session = Depends(get_db)):
    """Update a user's details."""
    try:
        logger.info(
            "Updating user",
            user_id=user_id,
            update_data=user.dict(exclude_unset=True)
        )
        db_user = db.query(HAUser).filter(HAUser.id == user_id).first()
        if not db_user:
            logger.warning("User not found for update", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        
        for key, value in user.dict(exclude_unset=True).items():
            setattr(db_user, key, value)
        
        db.commit()
        db.refresh(db_user)
        logger.info("Successfully updated user", user_id=user_id)
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update user",
            error=str(e),
            user_id=user_id,
            update_data=user.dict(exclude_unset=True),
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Failed to update user")

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user mapping."""
    try:
        logger.info("Deleting user", user_id=user_id)
        user = db.query(HAUser).filter(HAUser.id == user_id).first()
        if not user:
            logger.warning("User not found for deletion", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        
        db.delete(user)
        db.commit()
        logger.info("Successfully deleted user", user_id=user_id)
        return {"message": "User deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete user",
            error=str(e),
            user_id=user_id,
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Failed to delete user")

@router.get("/faces", response_model=List[FaceResponse])
async def get_faces(db: Session = Depends(get_db)):
    """Get all face data."""
    return db.query(Face).all()

@router.post("/faces/{face_id}/map")
async def map_face(face_id: int, mapping: DataMapping, db: Session = Depends(get_db)):
    """Map a face to a user."""
    try:
        logger.info(
            "Mapping face to user",
            face_id=face_id,
            mapping_data=mapping.dict(exclude_unset=True)
        )
        face = db.query(Face).filter(Face.id == face_id).first()
        if not face:
            logger.warning("Face not found for mapping", face_id=face_id)
            raise HTTPException(status_code=404, detail="Face not found")
        
        user = db.query(HAUser).filter(HAUser.id == mapping.user_id).first()
        if not user:
            logger.warning(
                "User not found for face mapping",
                user_id=mapping.user_id,
                face_id=face_id
            )
            raise HTTPException(status_code=404, detail="User not found")
        
        face.user_id = user.id
        face.confidence = mapping.confidence
        
        if mapping.feedback:
            feedback = TrainingFeedback(
                data_type="face",
                data_id=face_id,
                notes=mapping.feedback
            )
            db.add(feedback)
            logger.info(
                "Added training feedback for face",
                face_id=face_id,
                feedback=mapping.feedback
            )
        
        db.commit()
        logger.info(
            "Successfully mapped face to user",
            face_id=face_id,
            user_id=user.id,
            confidence=mapping.confidence
        )
        return {"message": "Face mapped successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to map face to user",
            error=str(e),
            face_id=face_id,
            mapping_data=mapping.dict(exclude_unset=True),
            traceback=traceback.format_exc()
        )
        raise HTTPException(status_code=500, detail="Failed to map face")

@router.post("/faces/{face_id}/reject")
async def reject_face(face_id: int, feedback: TrainingFeedbackCreate, db: Session = Depends(get_db)):
    """Mark a face as rejected for training purposes."""
    face = db.query(Face).filter(Face.id == face_id).first()
    if not face:
        raise HTTPException(status_code=404, detail="Face not found")
    
    face.is_rejected = True
    
    feedback_entry = TrainingFeedback(
        data_type="face",
        data_id=face_id,
        notes=feedback.notes
    )
    db.add(feedback_entry)
    
    db.commit()
    return {"message": "Face rejected"}

@router.get("/voices", response_model=List[VoiceResponse])
async def get_voices(db: Session = Depends(get_db)):
    """Get all voice data."""
    return db.query(Voice).all()

@router.post("/voices/{voice_id}/map")
async def map_voice(voice_id: int, mapping: DataMapping, db: Session = Depends(get_db)):
    """Map a voice to a user."""
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    
    user = db.query(HAUser).filter(HAUser.id == mapping.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    voice.user_id = user.id
    voice.confidence = mapping.confidence
    
    if mapping.feedback:
        feedback = TrainingFeedback(
            data_type="voice",
            data_id=voice_id,
            notes=mapping.feedback
        )
        db.add(feedback)
    
    db.commit()
    return {"message": "Voice mapped successfully"}

@router.post("/voices/{voice_id}/reject")
async def reject_voice(voice_id: int, feedback: TrainingFeedbackCreate, db: Session = Depends(get_db)):
    """Mark a voice as rejected for training purposes."""
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    
    voice.is_rejected = True
    
    feedback_entry = TrainingFeedback(
        data_type="voice",
        data_id=voice_id,
        notes=feedback.notes
    )
    db.add(feedback_entry)
    
    db.commit()
    return {"message": "Voice rejected"}

@router.get("/devices", response_model=List[DeviceResponse])
async def get_devices(db: Session = Depends(get_db)):
    """Get all device data."""
    return db.query(Device).all()

@router.post("/devices/{device_id}/map")
async def map_device(device_id: int, mapping: DataMapping, db: Session = Depends(get_db)):
    """Map a device to a user."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    user = db.query(HAUser).filter(HAUser.id == mapping.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    device.user_id = user.id
    
    if mapping.feedback:
        feedback = TrainingFeedback(
            data_type="device",
            data_id=device_id,
            notes=mapping.feedback
        )
        db.add(feedback)
    
    db.commit()
    return {"message": "Device mapped successfully"}

@router.post("/devices/{device_id}/forget")
async def forget_device(device_id: int, db: Session = Depends(get_db)):
    """Remove a device from tracking."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    db.delete(device)
    db.commit()
    return {"message": "Device forgotten"} 