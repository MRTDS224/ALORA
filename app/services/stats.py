from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Speaker, Session as SessionModel, Prompt, Recording, Transcription


def get_dashboard_stats(db: Session) -> Dict[str, Any]:
    total_speakers = db.query(func.count(Speaker.id)).scalar() or 0
    total_sessions = db.query(func.count(SessionModel.id)).scalar() or 0
    total_prompts = db.query(func.count(Prompt.id)).scalar() or 0
    image_prompts = (
        db.query(func.count(Prompt.id))
        .filter(Prompt.prompt_type == "image", Prompt.media_object_key.isnot(None))
        .scalar()
        or 0
    )

    total_recordings = db.query(func.count(Recording.id)).scalar() or 0
    total_duration_sec = db.query(func.sum(Recording.duration_seconds)).scalar() or 0.0

    status_counts = {}
    for st in ["uploaded", "validating", "validated", "transcribed", "reviewed", "accepted", "rejected"]:
        count = db.query(func.count(Recording.id)).filter(Recording.recording_status == st).scalar() or 0
        status_counts[st] = count

    gender_counts = {
        "female": db.query(func.count(Speaker.id)).filter(Speaker.gender == "female").scalar() or 0,
        "male": db.query(func.count(Speaker.id)).filter(Speaker.gender == "male").scalar() or 0,
        "other": db.query(func.count(Speaker.id)).filter(Speaker.gender.notin_(["female", "male"])).scalar() or 0,
    }

    task_counts = {
        "asr": db.query(func.count(SessionModel.id)).filter(SessionModel.target_task == "asr").scalar() or 0,
        "tts": db.query(func.count(SessionModel.id)).filter(SessionModel.target_task == "tts").scalar() or 0,
    }

    flagged_recordings = (
        db.query(func.count(Recording.id))
        .filter(Recording.auto_quality_flags.isnot(None), Recording.auto_quality_flags != "")
        .scalar()
        or 0
    )

    total_transcriptions = db.query(func.count(Transcription.id)).scalar() or 0
    recent_recordings = db.query(Recording).order_by(Recording.created_at.desc()).limit(5).all()

    return {
        "total_speakers": total_speakers,
        "total_sessions": total_sessions,
        "total_prompts": total_prompts,
        "image_prompts": image_prompts,
        "total_recordings": total_recordings,
        "total_duration_minutes": round(total_duration_sec / 60.0, 1),
        "total_duration_hours": round(total_duration_sec / 3600.0, 2),
        "status_counts": status_counts,
        "gender_counts": gender_counts,
        "task_counts": task_counts,
        "flagged_recordings": flagged_recordings,
        "total_transcriptions": total_transcriptions,
        "recent_recordings": recent_recordings,
    }
