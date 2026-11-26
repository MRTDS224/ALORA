from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import QualityAnnotation
from app.schemas.quality import QualityAnnotationCreate
from app.services import recording as recording_service

def create_quality_annotation(
    db: Session,
    annotation_in: QualityAnnotationCreate,
    recording_status: Optional[str] = "validated",
    reviewer_user_id: Optional[UUID] = None,
) -> QualityAnnotation:
    db_quality = QualityAnnotation(
        recording_id=annotation_in.recording_id,
        audio_quality=annotation_in.audio_quality,
        noise_level=annotation_in.noise_level,
        clipping=annotation_in.clipping,
        speech_present=annotation_in.speech_present,
        multiple_speakers=annotation_in.multiple_speakers,
        reviewer=annotation_in.reviewer,
        reviewer_user_id=reviewer_user_id,
        notes=annotation_in.notes
    )
    db.add(db_quality)

    # Also update Recording status
    if recording_status:
        recording_service.update_recording_status(db, annotation_in.recording_id, recording_status)

    db.commit()
    db.refresh(db_quality)
    return db_quality

def get_quality_annotations_by_recording(db: Session, recording_id: UUID) -> List[QualityAnnotation]:
    return db.query(QualityAnnotation).filter(QualityAnnotation.recording_id == recording_id).order_by(QualityAnnotation.created_at.desc()).all()
