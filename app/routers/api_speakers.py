from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.speaker import SpeakerCreate, SpeakerRead
from app.services import auth as auth_service
from app.services import speaker as speaker_service
from app.services.storage import storage_service

router = APIRouter(
    prefix="/api/speakers",
    tags=["Speakers"],
    dependencies=[Depends(auth_service.require_api_roles("collector", "reviewer", "admin"))],
)


@router.get("", response_model=List[SpeakerRead])
def list_speakers(
    skip: int = 0,
    limit: int = 100,
    query: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return speaker_service.get_speakers(db, skip=skip, limit=limit, query=query)


@router.post("", response_model=SpeakerRead, status_code=status.HTTP_201_CREATED)
def create_speaker(
    speaker_in: SpeakerCreate,
    db: Session = Depends(get_db),
):
    return speaker_service.create_speaker(db, speaker_in)


@router.get("/{speaker_id}", response_model=SpeakerRead)
def get_speaker(
    speaker_id: UUID,
    db: Session = Depends(get_db),
):
    speaker = speaker_service.get_speaker_by_id(db, speaker_id)
    if not speaker:
        raise HTTPException(status_code=404, detail="Locuteur non trouvé")
    return speaker


@router.post("/{speaker_id}/consent-audio", response_model=SpeakerRead)
async def upload_speaker_consent_audio(
    speaker_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Le fichier audio de consentement est vide")

    content_type = file.content_type or "audio/wav"
    ext = "wav"
    if "webm" in content_type:
        ext = "webm"
    elif "ogg" in content_type:
        ext = "ogg"
    elif "mp4" in content_type or "m4a" in content_type:
        ext = "m4a"

    speaker = speaker_service.attach_consent_audio(
        db=db,
        speaker_id=speaker_id,
        audio_bytes=audio_bytes,
        file_extension=ext,
        content_type=content_type,
    )
    if not speaker:
        raise HTTPException(status_code=404, detail="Locuteur non trouvé")
    return speaker


@router.get("/{speaker_id}/consent-audio")
def stream_speaker_consent_audio(
    speaker_id: UUID,
    db: Session = Depends(get_db),
):
    speaker = speaker_service.get_speaker_by_id(db, speaker_id)
    if not speaker or not speaker.consent_audio_object_key:
        raise HTTPException(status_code=404, detail="Audio de consentement non trouvé")
    object_key = str(speaker.consent_audio_object_key)
    # Release DB connection immediately before streaming audio bytes
    db.close()

    try:
        stream = storage_service.get_object_stream(object_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture audio MinIO: {e}")

    def _iter_chunks():
        try:
            yield from stream.stream(32768)
        finally:
            try:
                stream.close()
            except Exception:
                pass
            if hasattr(stream, "release_conn"):
                try:
                    stream.release_conn()
                except Exception:
                    pass

    return StreamingResponse(_iter_chunks(), media_type="audio/wav")
