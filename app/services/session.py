from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Session as SessionModel
from app.schemas.session import SessionCreate

def generate_session_code(db: Session) -> str:
    count = db.query(func.count(SessionModel.id)).scalar() or 0
    return f"SES_{count + 1:06d}"

def create_session(db: Session, session_in: SessionCreate) -> SessionModel:
    code = session_in.session_code or generate_session_code(db)
    db_session = SessionModel(
        session_code=code,
        speaker_id=session_in.speaker_id,
        location=session_in.location,
        environment=session_in.environment,
        target_task=session_in.target_task or "asr",
        device=session_in.device,
        collector=session_in.collector,
        notes=session_in.notes
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

def get_sessions(db: Session, skip: int = 0, limit: int = 100, speaker_id: Optional[UUID] = None) -> List[SessionModel]:
    q = db.query(SessionModel)
    if speaker_id:
        q = q.filter(SessionModel.speaker_id == speaker_id)
    return q.order_by(SessionModel.recorded_at.desc()).offset(skip).limit(limit).all()

def get_session_by_id(db: Session, session_id: UUID) -> Optional[SessionModel]:
    return db.query(SessionModel).filter(SessionModel.id == session_id).first()
