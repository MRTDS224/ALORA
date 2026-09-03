import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.session import SessionRead
from app.schemas.prompt import PromptRead

class RecordingBase(BaseModel):
    session_id: UUID
    prompt_id: Optional[UUID] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = 16000
    channels: Optional[int] = 1
    format: Optional[str] = "wav"

class RecordingCreate(RecordingBase):
    recording_code: Optional[str] = None  # Generated (REC_000001)

class RecordingRead(RecordingBase):
    id: UUID
    recording_code: str
    audio_object_key: str
    file_size_bytes: Optional[int] = None
    recording_status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    session: Optional[SessionRead] = None
    prompt: Optional[PromptRead] = None

    model_config = ConfigDict(from_attributes=True)
