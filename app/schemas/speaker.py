import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class SpeakerBase(BaseModel):
    age_group: Optional[str] = "18-25"
    gender: Optional[str] = "female"
    region: Optional[str] = "Kindia"
    location: Optional[str] = None
    native_language: Optional[str] = "Susu"
    other_languages: Optional[str] = None
    consent_status: str = "granted"

class SpeakerCreate(SpeakerBase):
    speaker_code: Optional[str] = None  # Generated automatically if omitted (e.g. SPK_000001)

class SpeakerRead(SpeakerBase):
    id: UUID
    speaker_code: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
