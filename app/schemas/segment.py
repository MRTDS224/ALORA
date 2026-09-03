from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class SegmentBase(BaseModel):
    start_time: float
    end_time: float
    audio_object_key: Optional[str] = None

class SegmentCreate(SegmentBase):
    recording_id: UUID

class SegmentRead(SegmentBase):
    id: UUID
    recording_id: UUID
    segment_code: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WordAnnotationBase(BaseModel):
    word: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    normalized_form: Optional[str] = None
    annotation_type: Optional[str] = None
    value: Optional[str] = None
    annotator: Optional[str] = None

class WordAnnotationCreate(WordAnnotationBase):
    recording_id: UUID
    transcription_id: Optional[UUID] = None

class WordAnnotationRead(WordAnnotationBase):
    id: UUID
    recording_id: UUID
    transcription_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
