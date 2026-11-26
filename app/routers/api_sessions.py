from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import User
from app.schemas.session import SessionCreate, SessionRead
from app.services import auth as auth_service
from app.services import session as session_service

router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"],
    dependencies=[Depends(auth_service.require_api_roles("collector", "reviewer", "admin"))],
)

@router.get("", response_model=List[SessionRead])
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    speaker_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    return session_service.get_sessions(db, skip=skip, limit=limit, speaker_id=speaker_id)

@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(
    session_in: SessionCreate,
    current_user: User = Depends(auth_service.require_api_roles("collector", "reviewer", "admin")),
    db: Session = Depends(get_db),
):
    if not session_in.collector:
        session_in = session_in.model_copy(update={"collector": current_user.full_name})
    return session_service.create_session(db, session_in, collector_user_id=current_user.id)

@router.get("/{session_id}", response_model=SessionRead)
def get_session(
    session_id: UUID,
    db: Session = Depends(get_db)
):
    sess = session_service.get_session_by_id(db, session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session non trouvée")
    return sess
