import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class QualityAnnotationBase(BaseModel):
    recording_id: UUID
    audio_quality: Optional[str] = "good"     # good, fair, poor
    noise_level: Optional[str] = "low"       # low, medium, high
    clipping: bool = False
    speech_present: bool = True
    multiple_speakers: bool = False
    reviewer: Optional[str] = None
    notes: Optional[str] = None

class QualityAnnotationCreate(QualityAnnotationBase):
    pass

class QualityAnnotationRead(QualityAnnotationBase):
    id: UUID
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
