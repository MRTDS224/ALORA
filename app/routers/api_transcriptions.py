from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Form, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.transcription import TranscriptionCreate, TranscriptionRead
from app.services import transcription as transcription_service
from app.services import recording as recording_service

router = APIRouter(prefix="/api/transcriptions", tags=["Transcriptions"])

@router.get("", response_model=List[TranscriptionRead])
def list_transcriptions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    return transcription_service.get_all_transcriptions(db, skip=skip, limit=limit)

@router.get("/recording/{recording_id}", response_model=List[TranscriptionRead])
def get_recording_transcriptions(
    recording_id: UUID,
    db: Session = Depends(get_db)
):
    return transcription_service.get_transcriptions_by_recording(db, recording_id)

@router.post("", response_model=TranscriptionRead, status_code=status.HTTP_201_CREATED)
def create_transcription(
    transcription_in: TranscriptionCreate,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, transcription_in.recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    return transcription_service.create_transcription(db, transcription_in)
