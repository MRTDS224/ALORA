import os
import subprocess
import tempfile
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Prompt, Recording, Session as SessionModel
from app.services.audio_qa import analyze_wav_bytes
from app.services.storage import storage_service


def generate_recording_code(db: Session) -> str:
    last = (
        db.query(Recording.recording_code)
        .filter(Recording.recording_code.like("REC_%"))
        .order_by(Recording.recording_code.desc())
        .first()
    )
    next_num = 1
    if last and last[0]:
        try:
            next_num = int(str(last[0]).split("_", 1)[1]) + 1
        except (ValueError, IndexError):
            next_num = (db.query(func.count(Recording.id)).scalar() or 0) + 1
    return f"REC_{next_num:06d}"


def normalize_audio_ffmpeg(audio_bytes: bytes) -> bytes:
    """
    Normalizes input audio bytes to a standards-compliant 16kHz, mono, 16-bit PCM WAV
    using FFmpeg with a seekable temp output so RIFF/data chunk sizes are always exact.
    """
    if not audio_bytes:
        return audio_bytes
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        process = subprocess.Popen(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-f",
                "wav",
                tmp_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process.communicate(input=audio_bytes)
        if process.returncode == 0 and os.path.exists(tmp_path):
            with open(tmp_path, "rb") as f:
                out = f.read()
            if len(out) >= 44:
                return out
    except Exception as e:
        print(f"[FFmpeg] Normalization warning: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
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
    content_type: str = "audio/wav",
) -> Recording:
    # 1. Normalize audio with FFmpeg to 16kHz Mono 16-bit PCM WAV
    processed_bytes = normalize_audio_ffmpeg(audio_bytes)
    normalized = processed_bytes != audio_bytes
    final_format = "wav" if normalized else file_format
    final_content_type = "audio/wav" if normalized else content_type

    # 2. Fetch session/prompt context for acoustic QA thresholds
    sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    prompt = db.query(Prompt).filter(Prompt.id == prompt_id).first() if prompt_id else None
    target_task = sess.target_task if sess else "asr"
    prompt_type = prompt.prompt_type if prompt else None
    min_duration = prompt.min_duration_seconds if prompt else None

    # 3. Compute automatic acoustic QA metrics (duration, SNR, clipping, speech ratio)
    qa = analyze_wav_bytes(
        wav_bytes=processed_bytes,
        target_task=target_task,
        prompt_type=prompt_type,
        min_duration_seconds=min_duration,
        fallback_duration=duration_seconds,
    )

    code = recording_code or generate_recording_code(db)
    object_key = storage_service.generate_object_key(recording_code=code, file_extension=final_format)

    # 4. Upload audio to MinIO
    storage_service.upload_file(
        file_bytes=processed_bytes,
        object_key=object_key,
        content_type=final_content_type,
    )

    # 5. Create PostgreSQL Recording record
    db_recording = Recording(
        recording_code=code,
        session_id=session_id,
        prompt_id=prompt_id,
        audio_object_key=object_key,
        duration_seconds=qa.duration_seconds if qa.duration_seconds is not None else duration_seconds,
        sample_rate=qa.sample_rate or (16000 if normalized else sample_rate),
        channels=qa.channels or (1 if normalized else channels),
        format=final_format,
        file_size_bytes=len(processed_bytes),
        snr_db=qa.snr_db,
        peak_amplitude=qa.peak_amplitude,
        clipping_detected=qa.clipping_detected,
        speech_ratio=qa.speech_ratio,
        auto_quality_flags=qa.flags_csv,
        recording_status="uploaded",
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
    prompt_id: Optional[UUID] = None,
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
