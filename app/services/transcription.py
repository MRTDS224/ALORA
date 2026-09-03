from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Transcription
from app.schemas.transcription import TranscriptionCreate
from app.services import recording as recording_service

def get_next_version_number(db: Session, recording_id: UUID) -> int:
    max_ver = db.query(func.max(Transcription.version)).filter(Transcription.recording_id == recording_id).scalar()
    return (max_ver or 0) + 1

def create_transcription(db: Session, transcription_in: TranscriptionCreate) -> Transcription:
    version = get_next_version_number(db, transcription_in.recording_id)
    db_transcription = Transcription(
        recording_id=transcription_in.recording_id,
        version=version,
        text=transcription_in.transcription_text,
        transcriber=transcription_in.transcriber,
        language=transcription_in.language_code,
        transcription_status=transcription_in.status
    )
    db.add(db_transcription)

    # Update recording status to transcribed
    recording_service.update_recording_status(db, transcription_in.recording_id, "transcribed")

    db.commit()
    db.refresh(db_transcription)
    return db_transcription

def get_transcriptions_by_recording(db: Session, recording_id: UUID) -> List[Transcription]:
    return db.query(Transcription).filter(Transcription.recording_id == recording_id).order_by(Transcription.version.desc()).all()

def get_latest_transcription(db: Session, recording_id: UUID) -> Optional[Transcription]:
    return db.query(Transcription).filter(Transcription.recording_id == recording_id).order_by(Transcription.version.desc()).first()

def get_all_transcriptions(db: Session, skip: int = 0, limit: int = 100) -> List[Transcription]:
    return db.query(Transcription).order_by(Transcription.created_at.desc()).offset(skip).limit(limit).all()
