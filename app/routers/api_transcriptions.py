from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_client_ip
from app.models import User
from app.schemas.transcription import (
    TranscriptionCreate,
    TranscriptionRead,
    TranscriptionReviewCreate,
)
from app.services import audit as audit_service
from app.services import auth as auth_service
from app.services import transcription as transcription_service
from app.services import recording as recording_service

_reviewer_dep = Depends(auth_service.require_api_roles("reviewer", "admin"))

router = APIRouter(
    prefix="/api/transcriptions",
    tags=["Transcriptions"],
    dependencies=[_reviewer_dep],
)


@router.get("", response_model=List[TranscriptionRead])
def list_transcriptions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    return transcription_service.get_all_transcriptions(db, skip=skip, limit=limit)


@router.get("/recording/{recording_id}", response_model=List[TranscriptionRead])
def get_recording_transcriptions(
    recording_id: UUID,
    db: Session = Depends(get_db),
):
    return transcription_service.get_transcriptions_by_recording(db, recording_id)


@router.post("", response_model=TranscriptionRead, status_code=status.HTTP_201_CREATED)
def create_transcription(
    request: Request,
    transcription_in: TranscriptionCreate,
    current_user: User = _reviewer_dep,
    db: Session = Depends(get_db),
):
    rec = recording_service.get_recording_by_id(db, transcription_in.recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    created = transcription_service.create_transcription(db, transcription_in, author=current_user)
    audit_service.record_audit(
        db=db,
        action="transcription.create",
        actor=current_user,
        target_type="transcription",
        target_id=created.id,
        details={"recording_id": str(rec.id), "version": created.version},
        ip_address=get_client_ip(request),
    )
    return created


@router.post("/{transcription_id}/review")
def review_transcription_api(
    request: Request,
    transcription_id: UUID,
    review_in: TranscriptionReviewCreate,
    current_user: User = _reviewer_dep,
    db: Session = Depends(get_db),
):
    try:
        res = transcription_service.review_transcription(
            db=db,
            transcription_id=transcription_id,
            reviewer=current_user,
            decision=review_in.decision,
            comment=review_in.comment,
            corrected_text=review_in.corrected_text,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    audit_action = (
        "transcription.approve"
        if review_in.decision == "approved"
        else "transcription.propose_correction"
    )
    audit_service.record_audit(
        db=db,
        action=audit_action,
        actor=current_user,
        target_type="transcription",
        target_id=transcription_id,
        details={
            "decision": review_in.decision,
            "approvals_count": res["approvals_count"],
            "required_approvals": res["required_approvals"],
            "new_version_id": str(res["created_version"].id) if res["created_version"] else None,
        },
        ip_address=get_client_ip(request),
    )

    tr = res["transcription"]
    return {
        "transcription_id": str(tr.id),
        "version": tr.version,
        "status": tr.transcription_status,
        "approvals_count": res["approvals_count"],
        "required_approvals": res["required_approvals"],
        "created_version": (
            {
                "id": str(res["created_version"].id),
                "version": res["created_version"].version,
                "status": res["created_version"].transcription_status,
            }
            if res["created_version"]
            else None
        ),
    }
