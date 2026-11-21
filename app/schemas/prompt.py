import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict

class PromptBase(BaseModel):
    prompt_type: str = "sentence" # image, question, topic, sentence, story, free_speech
    title: str
    description: Optional[str] = None
    content: str
    min_duration_seconds: Optional[float] = None
    language: str = "sus"
    topic: Optional[str] = None
    difficulty: Optional[str] = "easy"
    active: bool = True

class PromptCreate(PromptBase):
    prompt_code: Optional[str] = None # Generated automatically (PRM_000001)
    media_object_key: Optional[str] = None
    media_content_type: Optional[str] = None

class PromptRead(PromptBase):
    id: UUID
    prompt_code: str
    media_object_key: Optional[str] = None
    media_content_type: Optional[str] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
