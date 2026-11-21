from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.recording import RecordingRead
from app.services import auth as auth_service
from app.services import recording as recording_service
from app.services.storage import storage_service

router = APIRouter(
    prefix="/api/recordings",
    tags=["Recordings"],
    dependencies=[Depends(auth_service.require_api_roles("collector", "reviewer", "admin"))],
)
_reviewer_dep = Depends(auth_service.require_api_roles("reviewer", "admin"))

@router.get("", response_model=List[RecordingRead])
def list_recordings(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    session_id: Optional[UUID] = None,
    prompt_id: Optional[UUID] = None,
    db: Session = Depends(get_db)
):
    return recording_service.get_recordings(
        db, skip=skip, limit=limit, status=status, session_id=session_id, prompt_id=prompt_id
    )

@router.post("", response_model=RecordingRead, status_code=status.HTTP_201_CREATED)
async def create_recording_upload(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    prompt_id: Optional[str] = Form(None),
    duration_seconds: Optional[float] = Form(None),
    sample_rate: Optional[int] = Form(16000),
    channels: Optional[int] = Form(1),
    db: Session = Depends(get_db)
):
    try:
        session_uuid = UUID(session_id)
        prompt_uuid = UUID(prompt_id) if prompt_id and prompt_id.strip() else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Identifiant session_id ou prompt_id invalide")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Le fichier audio envoyé est vide")

    # Determine file extension
    content_type = file.content_type or "audio/wav"
    file_extension = "wav"
    if "webm" in content_type:
        file_extension = "webm"
    elif "ogg" in content_type:
        file_extension = "ogg"
    elif "mp3" in content_type:
        file_extension = "mp3"

    rec = recording_service.create_recording(
        db=db,
        session_id=session_uuid,
        prompt_id=prompt_uuid,
        audio_bytes=audio_bytes,
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        file_format=file_extension,
        content_type=content_type
    )
    return rec

@router.get("/{recording_id}", response_model=RecordingRead)
def get_recording(
    recording_id: UUID,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")
    return rec

@router.get("/{recording_id}/stream")
def stream_audio(
    recording_id: UUID,
    db: Session = Depends(get_db)
):
    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")

    try:
        stream = storage_service.get_object_stream(str(rec.audio_object_key))
        media_type = f"audio/{rec.format}" if rec.format else "audio/wav"
        return StreamingResponse(stream.stream(32768), media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture audio MinIO: {e}")

@router.post("/{recording_id}/validate", response_model=RecordingRead, dependencies=[_reviewer_dep])
def validate_recording(
    recording_id: UUID,
    audio_quality: str = Form("good"),
    noise_level: str = Form("low"),
    clipping: bool = Form(False),
    speech_present: bool = Form(True),
    multiple_speakers: bool = Form(False),
    reviewer: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    from app.schemas.quality import QualityAnnotationCreate
    from app.services import quality as quality_service

    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")

    qual_in = QualityAnnotationCreate(
        recording_id=recording_id,
        audio_quality=audio_quality,
        noise_level=noise_level,
        clipping=clipping,
        speech_present=speech_present,
        multiple_speakers=multiple_speakers,
        reviewer=reviewer,
        notes=notes
    )
    quality_service.create_quality_annotation(db, qual_in, recording_status="validated")
    return recording_service.get_recording_by_id(db, recording_id)

@router.post("/{recording_id}/reject", response_model=RecordingRead, dependencies=[_reviewer_dep])
def reject_recording(
    recording_id: UUID,
    audio_quality: str = Form("poor"),
    noise_level: str = Form("high"),
    clipping: bool = Form(False),
    speech_present: bool = Form(False),
    multiple_speakers: bool = Form(False),
    reviewer: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    from app.schemas.quality import QualityAnnotationCreate
    from app.services import quality as quality_service

    rec = recording_service.get_recording_by_id(db, recording_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Enregistrement non trouvé")

    qual_in = QualityAnnotationCreate(
        recording_id=recording_id,
        audio_quality=audio_quality,
        noise_level=noise_level,
        clipping=clipping,
        speech_present=speech_present,
        multiple_speakers=multiple_speakers,
        reviewer=reviewer,
        notes=notes
    )
    quality_service.create_quality_annotation(db, qual_in, recording_status="rejected")
    return recording_service.get_recording_by_id(db, recording_id)
