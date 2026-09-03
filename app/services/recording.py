import subprocess
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Recording
from app.services.storage import storage_service

def generate_recording_code(db: Session) -> str:
    count = db.query(func.count(Recording.id)).scalar() or 0
    return f"REC_{count + 1:06d}"

def normalize_audio_ffmpeg(audio_bytes: bytes) -> bytes:
    """
    Normalizes input audio bytes to 16kHz, mono 16-bit PCM WAV using FFmpeg.
    Returns converted bytes or original bytes if conversion fails.
    """
    if not audio_bytes:
        return audio_bytes
    try:
        process = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, err = process.communicate(input=audio_bytes)
        if process.returncode == 0 and out and len(out) > 44:  # 44 bytes minimum for WAV header
            return out
    except Exception as e:
        print(f"[FFmpeg] Normalization warning: {e}")
    return audio_bytes

def create_recording(
    db: Session,
    session_id: UUID,
    audio_bytes: bytes,
    prompt_id: Optional[UUID] = None,
    recording_code: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    sample_rate: Optional[int] = 16000,
    channels: Optional[int] = 1,
    file_format: str = "wav",
    content_type: str = "audio/wav"
) -> Recording:
    # 1. Normalize audio with FFmpeg to 16kHz Mono WAV
    processed_bytes = normalize_audio_ffmpeg(audio_bytes)
    final_format = "wav" if processed_bytes != audio_bytes else file_format
    final_content_type = "audio/wav" if processed_bytes != audio_bytes else content_type

    code = recording_code or generate_recording_code(db)
    object_key = storage_service.generate_object_key(recording_code=code, file_extension=final_format)

    # 2. Upload audio to MinIO
    storage_service.upload_file(
        file_bytes=processed_bytes,
        object_key=object_key,
        content_type=final_content_type
    )

    # 3. Create PostgreSQL Recording record
    db_recording = Recording(
        recording_code=code,
        session_id=session_id,
        prompt_id=prompt_id,
        audio_object_key=object_key,
        duration_seconds=duration_seconds,
        sample_rate=16000 if processed_bytes != audio_bytes else sample_rate,
        channels=1 if processed_bytes != audio_bytes else channels,
        format=final_format,
        file_size_bytes=len(processed_bytes),
        recording_status="uploaded"
    )

    db.add(db_recording)
    db.commit()
    db.refresh(db_recording)
    return db_recording

def get_recordings(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    session_id: Optional[UUID] = None,
    prompt_id: Optional[UUID] = None
) -> List[Recording]:
    q = db.query(Recording)
    if status:
        q = q.filter(Recording.recording_status == status)
    if session_id:
        q = q.filter(Recording.session_id == session_id)
    if prompt_id:
        q = q.filter(Recording.prompt_id == prompt_id)

    return q.order_by(Recording.created_at.desc()).offset(skip).limit(limit).all()

def get_recording_by_id(db: Session, recording_id: UUID) -> Optional[Recording]:
    return db.query(Recording).filter(Recording.id == recording_id).first()

def update_recording_status(db: Session, recording_id: UUID, new_status: str) -> Optional[Recording]:
    recording = get_recording_by_id(db, recording_id)
    if recording:
        recording.recording_status = new_status
        db.commit()
        db.refresh(recording)
    return recording
