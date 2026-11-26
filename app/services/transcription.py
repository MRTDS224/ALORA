from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import Transcription, TranscriptionReview, User
from app.schemas.transcription import TranscriptionCreate
from app.services import recording as recording_service


def get_next_version_number(db: Session, recording_id: UUID) -> int:
    max_ver = db.query(func.max(Transcription.version)).filter(Transcription.recording_id == recording_id).scalar()
    return (max_ver or 0) + 1


def create_transcription(
    db: Session,
    transcription_in: TranscriptionCreate,
    author: Optional[User] = None,
) -> Transcription:
    version = get_next_version_number(db, transcription_in.recording_id)
    # New versions always start as 'draft' so no author can self-accept their own transcription.
    db_transcription = Transcription(
        recording_id=transcription_in.recording_id,
        version=version,
        text=transcription_in.transcription_text.strip(),
        transcriber=(transcription_in.transcriber or (author.full_name if author else None)),
        author_user_id=author.id if author else None,
        notes=transcription_in.notes.strip() if transcription_in.notes and transcription_in.notes.strip() else None,
        language=transcription_in.language_code,
        transcription_status="draft",
    )
    db.add(db_transcription)

    # Update recording status to transcribed (unless already accepted on an earlier version)
    recording_service.update_recording_status(db, transcription_in.recording_id, "transcribed")

    db.commit()
    db.refresh(db_transcription)
    return db_transcription


def review_transcription(
    db: Session,
    transcription_id: UUID,
    reviewer: User,
    decision: str,
    comment: Optional[str] = None,
    corrected_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Peer-review workflow (WAXAL multi-reviewer protocol):
      - An author can NEVER approve their own transcription version.
      - Each reviewer can vote at most once per version (UNIQUE constraint).
      - Approving increments peer approvals; reaching TRANSCRIPTION_REQUIRED_APPROVALS
        automatically promotes the transcription & recording to 'accepted'.
      - Proposing a correction ('changes_requested' + corrected_text) creates a new
        version authored by the reviewer, which must in turn be validated by another user.
    """
    decision_clean = (decision or "").strip().lower()
    if decision_clean not in {"approved", "changes_requested"}:
        raise ValueError("Décision invalide (doit être 'approved' ou 'changes_requested').")

    tr = (
        db.query(Transcription)
        .options(selectinload(Transcription.reviews))
        .filter(Transcription.id == transcription_id)
        .first()
    )
    if not tr:
        raise LookupError("Transcription non trouvée.")

    if decision_clean == "approved" and tr.author_user_id and tr.author_user_id == reviewer.id:
        raise PermissionError(
            "Auto-validation interdite : vous êtes l'auteur de cette version. Un autre réviseur doit l'approuver."
        )

    existing = (
        db.query(TranscriptionReview)
        .filter(
            TranscriptionReview.transcription_id == transcription_id,
            TranscriptionReview.reviewer_user_id == reviewer.id,
        )
        .first()
    )
    if existing:
        raise ValueError("Vous avez déjà soumis une évaluation pour cette version.")

    clean_comment = comment.strip() if comment and comment.strip() else None
    clean_correction = corrected_text.strip() if corrected_text and corrected_text.strip() else None

    if decision_clean == "changes_requested" and not clean_correction and not clean_comment:
        raise ValueError("Veuillez saisir une version corrigée ou un commentaire explicatif.")

    review = TranscriptionReview(
        transcription_id=tr.id,
        reviewer_user_id=reviewer.id,
        reviewer_name=reviewer.full_name,
        decision=decision_clean,
        comment=clean_comment,
    )
    db.add(review)
    db.flush()

    created_version: Optional[Transcription] = None
    required_approvals = max(1, int(settings.TRANSCRIPTION_REQUIRED_APPROVALS or 2))

    if decision_clean == "approved":
        approvals = (
            db.query(func.count(TranscriptionReview.id))
            .filter(
                TranscriptionReview.transcription_id == tr.id,
                TranscriptionReview.decision == "approved",
            )
            .scalar()
            or 0
        )
        tr.reviewer = reviewer.full_name
        if approvals >= required_approvals:
            tr.transcription_status = "accepted"
            recording_service.update_recording_status(db, tr.recording_id, "accepted")
        else:
            tr.transcription_status = "reviewed"
            recording_service.update_recording_status(db, tr.recording_id, "reviewed")
    else:
        # Reviewer requested changes and optionally supplied a corrected version
        if clean_correction and clean_correction != tr.text:
            next_ver = get_next_version_number(db, tr.recording_id)
            created_version = Transcription(
                recording_id=tr.recording_id,
                version=next_ver,
                text=clean_correction,
                transcriber=reviewer.full_name,
                author_user_id=reviewer.id,
                notes=clean_comment or f"Correction proposée à partir de la version {tr.version}",
                language=tr.language,
                transcription_status="draft",
            )
            db.add(created_version)
            recording_service.update_recording_status(db, tr.recording_id, "transcribed")

    db.commit()
    db.refresh(tr)
    if created_version:
        db.refresh(created_version)

    approvals_final = (
        db.query(func.count(TranscriptionReview.id))
        .filter(
            TranscriptionReview.transcription_id == tr.id,
            TranscriptionReview.decision == "approved",
        )
        .scalar()
        or 0
    )

    return {
        "transcription": tr,
        "review": review,
        "created_version": created_version,
        "approvals_count": int(approvals_final),
        "required_approvals": required_approvals,
    }


def get_transcriptions_by_recording(db: Session, recording_id: UUID) -> List[Transcription]:
    return (
        db.query(Transcription)
        .options(selectinload(Transcription.reviews))
        .filter(Transcription.recording_id == recording_id)
        .order_by(Transcription.version.desc())
        .all()
    )


def get_latest_transcription(db: Session, recording_id: UUID) -> Optional[Transcription]:
    return (
        db.query(Transcription)
        .options(selectinload(Transcription.reviews))
        .filter(Transcription.recording_id == recording_id)
        .order_by(Transcription.version.desc())
        .first()
    )


def get_all_transcriptions(db: Session, skip: int = 0, limit: int = 100) -> List[Transcription]:
    return (
        db.query(Transcription)
        .options(selectinload(Transcription.reviews))
        .order_by(Transcription.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
