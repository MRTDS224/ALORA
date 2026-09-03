from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Speaker, Session as SessionModel, Prompt, Recording, Transcription, QualityAnnotation

def get_dashboard_stats(db: Session) -> Dict[str, Any]:
    total_speakers = db.query(func.count(Speaker.id)).scalar() or 0
    total_sessions = db.query(func.count(SessionModel.id)).scalar() or 0
    total_prompts = db.query(func.count(Prompt.id)).scalar() or 0
    
    total_recordings = db.query(func.count(Recording.id)).scalar() or 0
    total_duration_sec = db.query(func.sum(Recording.duration_seconds)).scalar() or 0.0
    
    status_counts = {}
    for st in ["uploaded", "validating", "validated", "transcribed", "reviewed", "accepted", "rejected"]:
        count = db.query(func.count(Recording.id)).filter(Recording.recording_status == st).scalar() or 0
        status_counts[st] = count

    total_transcriptions = db.query(func.count(Transcription.id)).scalar() or 0
    
    recent_recordings = db.query(Recording).order_by(Recording.created_at.desc()).limit(5).all()

    return {
        "total_speakers": total_speakers,
        "total_sessions": total_sessions,
        "total_prompts": total_prompts,
        "total_recordings": total_recordings,
        "total_duration_minutes": round(total_duration_sec / 60.0, 1),
        "total_duration_hours": round(total_duration_sec / 3600.0, 2),
        "status_counts": status_counts,
        "total_transcriptions": total_transcriptions,
        "recent_recordings": recent_recordings
    }
