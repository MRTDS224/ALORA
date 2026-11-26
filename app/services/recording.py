import os
import subprocess
import tempfile
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.logging import get_logger
from app.models import Prompt, Recording, Session as SessionModel
from app.services.audio_qa import analyze_wav_bytes
from app.services.storage import storage_service

logger = get_logger("recording")


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


def normalize_audio_ffmpeg(
    audio_bytes: bytes,
    input_ext: str = "webm",
    content_type: str = "",
) -> bytes:
    """
    Normalizes input audio bytes to a standards-compliant 16kHz, mono, 16-bit PCM WAV
    using seekable temp files for BOTH input and output so MP4/M4A (iOS Safari, moov-at-end)
    and mobile WebM/OGG streams decode reliably.
    """
    if not audio_bytes:
        return audio_bytes
    in_path = None
    out_path = None
    clean_ext = "".join(ch for ch in (input_ext or "bin").lower() if ch.isalnum())[:8] or "bin"
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{clean_ext}", delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            in_path = tmp_in.name

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            out_path = tmp_out.name

        res = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                in_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-acodec",
                "pcm_s16le",
                "-f",
                "wav",
                out_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if res.returncode == 0 and os.path.exists(out_path):
            with open(out_path, "rb") as f:
                out = f.read()
            if len(out) >= 44:
                return out
        stderr_msg = (res.stderr or b"").decode("utf-8", errors="replace").strip()[:400]
        logger.warning(
            "FFmpeg audio normalization failed",
            extra={
                "returncode": res.returncode,
                "input_bytes": len(audio_bytes),
                "input_ext": clean_ext,
                "content_type": content_type,
                "stderr": stderr_msg,
            },
        )
    except Exception as e:
        logger.warning(
            "FFmpeg audio normalization exception: %s",
            str(e),
            extra={
                "input_bytes": len(audio_bytes),
                "input_ext": clean_ext,
                "content_type": content_type,
            },
        )
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
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
    processed_bytes = normalize_audio_ffmpeg(
        audio_bytes,
        input_ext=file_format,
        content_type=content_type,
    )
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
