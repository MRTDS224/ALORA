import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.speaker import SpeakerRead

class SessionBase(BaseModel):
    speaker_id: UUID
    location: Optional[str] = None
    environment: Optional[str] = "quiet_room"
    target_task: str = "asr"  # asr or tts
    language: str = "sus"     # ISO 639-3 code (e.g. sus, fuf, emk)
    source: str = "field_agent"  # field_agent or public_web
    device: Optional[str] = "smartphone_mic"
    collector: Optional[str] = None
    notes: Optional[str] = None

class SessionCreate(SessionBase):
    session_code: Optional[str] = None  # Generated automatically if omitted (e.g. SES_000001)

class SessionRead(SessionBase):
    id: UUID
    session_code: str
    recorded_at: datetime.datetime
    created_at: datetime.datetime
    speaker: Optional[SpeakerRead] = None

    model_config = ConfigDict(from_attributes=True)
