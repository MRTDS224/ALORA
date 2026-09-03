import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class TranscriptionBase(BaseModel):
    recording_id: UUID
    transcription_text: str = Field(..., alias="text")
    transcriber: Optional[str] = None
    language_code: str = Field("sus", alias="language")
    status: str = Field("draft", alias="transcription_status")
    notes: Optional[str] = None

class TranscriptionCreate(BaseModel):
    recording_id: UUID
    transcription_text: str
    transcriber: Optional[str] = None
    language_code: str = "sus"
    status: str = "draft"
    notes: Optional[str] = None

class TranscriptionRead(BaseModel):
    id: UUID
    recording_id: UUID
    text: str
    version: int
    transcriber: Optional[str] = None
    language: str
    transcription_status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @property
    def transcription_text(self) -> str:
        return self.text

    @property
    def version_number(self) -> int:
        return self.version

    @property
    def status(self) -> str:
        return self.transcription_status

    model_config = ConfigDict(from_attributes=True)
