from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Union
from datetime import datetime

class UserBase(BaseModel):
    name: str
    ha_user_id: str
    display_name: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(UserBase):
    name: Optional[str] = None
    ha_user_id: Optional[str] = None

class FaceBase(BaseModel):
    encoding: str
    metadata: dict
    confidence: float = Field(ge=0, le=100)
    is_rejected: bool = False
    created_at: datetime

class FaceCreate(FaceBase):
    pass

class FaceResponse(FaceBase):
    id: int
    user_id: Optional[int]
    confidence_level: str

    class Config:
        orm_mode = True

    @property
    def confidence_level(self) -> str:
        if self.confidence >= 90:
            return "high"
        elif self.confidence >= 70:
            return "medium"
        return "low"

class VoiceBase(BaseModel):
    embedding: str
    metadata: dict
    confidence: float = Field(ge=0, le=100)
    is_rejected: bool = False
    created_at: datetime

class VoiceCreate(VoiceBase):
    pass

class VoiceResponse(VoiceBase):
    id: int
    user_id: Optional[int]
    confidence_level: str

    class Config:
        orm_mode = True

    @property
    def confidence_level(self) -> str:
        if self.confidence >= 90:
            return "high"
        elif self.confidence >= 70:
            return "medium"
        return "low"

class DeviceBase(BaseModel):
    device_type: str
    identifier: str
    metadata: dict
    last_seen: datetime

class DeviceCreate(DeviceBase):
    pass

class DeviceResponse(DeviceBase):
    id: int
    user_id: Optional[int]

    class Config:
        orm_mode = True

class DataMapping(BaseModel):
    user_id: int
    confidence: Optional[float] = Field(ge=0, le=100, default=100)
    feedback: Optional[str] = None

class TrainingFeedbackCreate(BaseModel):
    notes: str

class TrainingFeedbackResponse(BaseModel):
    id: int
    data_type: str
    data_id: int
    notes: str
    created_at: datetime

    class Config:
        orm_mode = True

class UserResponse(UserBase):
    id: int
    faces: List[FaceResponse]
    voices: List[VoiceResponse]
    devices: List[DeviceResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class StreamAuthData(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None

class StreamBase(BaseModel):
    name: str
    url: HttpUrl
    type: str
    auth_type: str = "none"
    auth_data: Optional[StreamAuthData] = None

class StreamCreate(StreamBase):
    pass

class StreamResponse(StreamBase):
    id: str
    status: str
    last_checked: Optional[datetime] = None
    error_message: Optional[str] = None
    capabilities: List[str]

    class Config:
        orm_mode = True

class StreamUpdate(StreamBase):
    name: Optional[str] = None
    url: Optional[HttpUrl] = None
    type: Optional[str] = None
    auth_type: Optional[str] = None
    auth_data: Optional[StreamAuthData] = None

class StreamHealth(BaseModel):
    id: str
    status: str
    last_checked: datetime
    response_time: float
    error_message: Optional[str] = None 