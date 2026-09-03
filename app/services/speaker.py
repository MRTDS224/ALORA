from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Speaker
from app.schemas.speaker import SpeakerCreate

def generate_speaker_code(db: Session) -> str:
    count = db.query(func.count(Speaker.id)).scalar() or 0
    return f"SPK_{count + 1:06d}"

def create_speaker(db: Session, speaker_in: SpeakerCreate) -> Speaker:
    code = speaker_in.speaker_code or generate_speaker_code(db)
    db_speaker = Speaker(
        speaker_code=code,
        age_group=speaker_in.age_group,
        gender=speaker_in.gender,
        region=speaker_in.region,
        location=speaker_in.location,
        native_language=speaker_in.native_language,
        other_languages=speaker_in.other_languages,
        consent_status=speaker_in.consent_status
    )
    db.add(db_speaker)
    db.commit()
    db.refresh(db_speaker)
    return db_speaker

def get_speakers(db: Session, skip: int = 0, limit: int = 100, query: Optional[str] = None) -> List[Speaker]:
    q = db.query(Speaker)
    if query:
        search = f"%{query}%"
        q = q.filter(
            (Speaker.speaker_code.ilike(search)) |
            (Speaker.region.ilike(search)) |
            (Speaker.location.ilike(search))
        )
    return q.order_by(Speaker.created_at.desc()).offset(skip).limit(limit).all()

def get_speaker_by_id(db: Session, speaker_id: UUID) -> Optional[Speaker]:
    return db.query(Speaker).filter(Speaker.id == speaker_id).first()

def get_speaker_by_code(db: Session, speaker_code: str) -> Optional[Speaker]:
    return db.query(Speaker).filter(Speaker.speaker_code == speaker_code).first()
