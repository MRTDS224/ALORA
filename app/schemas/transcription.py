import datetime
from uuid import UUID
from typing import List, Optional
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


class TranscriptionReviewCreate(BaseModel):
    decision: str  # "approved" or "changes_requested"
    comment: Optional[str] = None
    corrected_text: Optional[str] = None


class TranscriptionReviewRead(BaseModel):
    id: UUID
    transcription_id: UUID
    reviewer_user_id: UUID
    reviewer_name: Optional[str] = None
    decision: str
    comment: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class TranscriptionRead(BaseModel):
    id: UUID
    recording_id: UUID
    text: str
    version: int
    transcriber: Optional[str] = None
    author_user_id: Optional[UUID] = None
    notes: Optional[str] = None
    language: str
    transcription_status: str
    reviews: List[TranscriptionReviewRead] = []
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
