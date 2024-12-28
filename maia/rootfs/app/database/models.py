"""Database models for MAIA."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class HAUser(Base):
    """Home Assistant user mapping."""
    __tablename__ = "ha_users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    ha_user_id = Column(String, nullable=False, unique=True)
    display_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    faces = relationship("Face", back_populates="user")
    voices = relationship("Voice", back_populates="user")
    devices = relationship("Device", back_populates="user")

class Face(Base):
    """Face data."""
    __tablename__ = "faces"

    id = Column(Integer, primary_key=True, index=True)
    encoding = Column(String, nullable=False)  # Base64 encoded face encoding
    metadata = Column(JSON, nullable=False)  # Image metadata, URLs, etc.
    confidence = Column(Float, nullable=False)
    is_rejected = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("ha_users.id"))

    user = relationship("HAUser", back_populates="faces")
    feedback = relationship("TrainingFeedback", 
                          primaryjoin="and_(Face.id==TrainingFeedback.data_id, "
                                    "TrainingFeedback.data_type=='face')")

class Voice(Base):
    """Voice data."""
    __tablename__ = "voices"

    id = Column(Integer, primary_key=True, index=True)
    embedding = Column(String, nullable=False)  # Base64 encoded voice embedding
    metadata = Column(JSON, nullable=False)  # Audio metadata, URLs, etc.
    confidence = Column(Float, nullable=False)
    is_rejected = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("ha_users.id"))

    user = relationship("HAUser", back_populates="voices")
    feedback = relationship("TrainingFeedback", 
                          primaryjoin="and_(Voice.id==TrainingFeedback.data_id, "
                                    "TrainingFeedback.data_type=='voice')")

class Device(Base):
    """Device data (BLE, WiFi, etc.)."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_type = Column(String, nullable=False)  # bluetooth, wifi, etc.
    identifier = Column(String, nullable=False, unique=True)  # MAC address, etc.
    metadata = Column(JSON, nullable=False)  # Device info, capabilities, etc.
    last_seen = Column(DateTime(timezone=True), nullable=False)
    user_id = Column(Integer, ForeignKey("ha_users.id"))

    user = relationship("HAUser", back_populates="devices")
    feedback = relationship("TrainingFeedback", 
                          primaryjoin="and_(Device.id==TrainingFeedback.data_id, "
                                    "TrainingFeedback.data_type=='device')")

class TrainingFeedback(Base):
    """User feedback for training data."""
    __tablename__ = "training_feedback"

    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String, nullable=False)  # face, voice, or device
    data_id = Column(Integer, nullable=False)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 