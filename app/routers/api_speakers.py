from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.speaker import SpeakerCreate, SpeakerRead
from app.services import speaker as speaker_service

router = APIRouter(prefix="/api/speakers", tags=["Speakers"])

@router.get("", response_model=List[SpeakerRead])
def list_speakers(
    skip: int = 0,
    limit: int = 100,
    query: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return speaker_service.get_speakers(db, skip=skip, limit=limit, query=query)

@router.post("", response_model=SpeakerRead, status_code=status.HTTP_201_CREATED)
def create_speaker(
    speaker_in: SpeakerCreate,
    db: Session = Depends(get_db)
):
    return speaker_service.create_speaker(db, speaker_in)

@router.get("/{speaker_id}", response_model=SpeakerRead)
def get_speaker(
    speaker_id: UUID,
    db: Session = Depends(get_db)
):
    speaker = speaker_service.get_speaker_by_id(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Locuteur non trouvé")
    return speaker
