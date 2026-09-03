from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.segment import SegmentCreate, SegmentRead, WordAnnotationCreate, WordAnnotationRead
from app.services import segmentation as segmentation_service
from app.services import recording as recording_service

router = APIRouter(prefix="/api/recordings", tags=["Segmentation & Praat TextGrid"])

@router.post("/{recording_id}/segments", response_model=SegmentRead, status_code=status.HTTP_201_CREATED)
def create_segment(
    recording_id: UUID,
    segment_in: SegmentCreate,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    segment_in.recording_id = recording_id
    return segmentation_service.create_segment(db, segment_in)

@router.get("/{recording_id}/segments", response_model=List[SegmentRead])
def list_segments(
    recording_id: UUID,
    db: Session = Depends(get_db)
):
    return segmentation_service.get_segments_by_recording(db, recording_id)

@router.post("/{recording_id}/words", response_model=WordAnnotationRead, status_code=status.HTTP_201_CREATED)
def create_word_annotation(
    recording_id: UUID,
    word_in: WordAnnotationCreate,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    word_in.recording_id = recording_id
    return segmentation_service.create_word_annotation(db, word_in)

@router.get("/{recording_id}/textgrid")
def download_praat_textgrid(
    recording_id: UUID,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    
    try:
        textgrid_content = segmentation_service.generate_praat_textgrid(db, recording_id)
        filename = f"{rec.recording_code}.TextGrid"
        return Response(
            content=textgrid_content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de génération TextGrid: {e}")
