from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import speaker as speaker_service
from app.services import session as session_service
from app.services import prompt as prompt_service
from app.services import recording as recording_service
from app.schemas.speaker import SpeakerCreate
from app.schemas.session import SessionCreate
from app.schemas.prompt import PromptCreate

templates = Jinja2Templates(directory="app/templates")

web_router = APIRouter(tags=["Web Pages"])

# --- DASHBOARD ---
@web_router.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request, db: Session = Depends(get_db)):
    from app.services import stats as stats_service
    stats = stats_service.get_dashboard_stats(db)
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"stats": stats})


# --- SPEAKERS ---
@web_router.get("/speakers", response_class=HTMLResponse)
def page_speakers(request: Request, db: Session = Depends(get_db)):
    speakers = speaker_service.get_speakers(db)
    return templates.TemplateResponse(request=request, name="speakers.html", context={"speakers": speakers})

@web_router.post("/speakers")
def handle_create_speaker(
    age_group: str = Form("18-25"),
    gender: str = Form("female"),
    region: str = Form("Kindia"),
    location: Optional[str] = Form(None),
    native_language: str = Form("Susu"),
    other_languages: Optional[str] = Form(None),
    consent_status: str = Form("granted"),
    speaker_code: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    speaker_in = SpeakerCreate(
        speaker_code=speaker_code if speaker_code else None,
        age_group=age_group,
        gender=gender,
        region=region,
        location=location,
        native_language=native_language,
        other_languages=other_languages,
        consent_status=consent_status
    )
    speaker_service.create_speaker(db, speaker_in)
    return RedirectResponse(url="/speakers", status_code=303)


# --- SESSIONS ---
@web_router.get("/sessions", response_class=HTMLResponse)
def page_sessions(request: Request, speaker_id: Optional[str] = None, db: Session = Depends(get_db)):
    speakers = speaker_service.get_speakers(db)
    sessions = session_service.get_sessions(db)
    return templates.TemplateResponse(request=request, name="sessions.html", context={
        "speakers": speakers,
        "sessions": sessions,
        "selected_speaker_id": speaker_id
    })

@web_router.post("/sessions")
def handle_create_session(
    speaker_id: str = Form(...),
    session_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    environment: str = Form("quiet_room"),
    device: str = Form("browser_mic"),
    collector: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    session_in = SessionCreate(
        speaker_id=UUID(speaker_id),
        session_code=session_code if session_code else None,
        location=location,
        environment=environment,
        device=device,
        collector=collector,
        notes=notes
    )
    session_service.create_session(db, session_in)
    return RedirectResponse(url="/sessions", status_code=303)


# --- PROMPTS ---
@web_router.get("/prompts", response_class=HTMLResponse)
def page_prompts(request: Request, db: Session = Depends(get_db)):
    prompts = prompt_service.get_prompts(db)
    return templates.TemplateResponse(request=request, name="prompts.html", context={"prompts": prompts})

@web_router.post("/prompts")
def handle_create_prompt(
    title: str = Form(...),
    content: str = Form(...),
    prompt_type: str = Form("sentence"),
    description: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    difficulty: str = Form("easy"),
    db: Session = Depends(get_db)
):
    prompt_in = PromptCreate(
        title=title,
        content=content,
        prompt_type=prompt_type,
        description=description,
        topic=topic,
        difficulty=difficulty,
        active=True
    )
    prompt_service.create_prompt(db, prompt_in)
    return RedirectResponse(url="/prompts", status_code=303)

@web_router.post("/prompts/{prompt_id}/toggle")
def handle_toggle_prompt(prompt_id: str, db: Session = Depends(get_db)):
    prompt_service.toggle_prompt_active(db, UUID(prompt_id))
    return RedirectResponse(url="/prompts", status_code=303)


# --- RECORDINGS & VALIDATION ---
@web_router.get("/recordings", response_class=HTMLResponse)
def page_recordings(
    request: Request,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    recordings = recording_service.get_recordings(db, status=status)
    return templates.TemplateResponse(request=request, name="recordings_list.html", context={
        "recordings": recordings,
        "current_status": status
    })

@web_router.get("/recordings/{recording_id}", response_class=HTMLResponse)
def page_recording_detail(
    request: Request,
    recording_id: str,
    db: Session = Depends(get_db)
):
    from app.services import quality as quality_service
    rec_uuid = UUID(recording_id)
    rec = recording_service.get_recording_by_id(db, rec_uuid)
    if not rec:
        return RedirectResponse(url="/recordings", status_code=303)

    qualities = quality_service.get_quality_annotations_by_recording(db, rec_uuid)
    last_quality = qualities[0] if qualities else None

    return templates.TemplateResponse(request=request, name="recording_detail.html", context={
        "recording": rec,
        "quality_history": qualities,
        "last_quality": last_quality
    })

@web_router.post("/recordings/{recording_id}/evaluate")
def handle_evaluate_recording(
    recording_id: str,
    action: str = Form(...), # "validate" or "reject"
    audio_quality: str = Form("good"),
    noise_level: str = Form("low"),
    clipping: Optional[str] = Form(None),
    speech_present: Optional[str] = Form(None),
    multiple_speakers: Optional[str] = Form(None),
    reviewer: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    from app.schemas.quality import QualityAnnotationCreate
    from app.services import quality as quality_service

    rec_uuid = UUID(recording_id)
    target_status = "validated" if action == "validate" else "rejected"

    qual_in = QualityAnnotationCreate(
        recording_id=rec_uuid,
        audio_quality=audio_quality,
        noise_level=noise_level,
        clipping=bool(clipping),
        speech_present=bool(speech_present),
        multiple_speakers=bool(multiple_speakers),
        reviewer=reviewer,
        notes=notes
    )
    quality_service.create_quality_annotation(db, qual_in, recording_status=target_status)
    return RedirectResponse(url=f"/recordings/{recording_id}", status_code=303)


# --- TRANSCRIPTIONS ---
@web_router.get("/transcriptions", response_class=HTMLResponse)
def page_transcriptions(request: Request, db: Session = Depends(get_db)):
    recordings = recording_service.get_recordings(db)
    return templates.TemplateResponse(request=request, name="transcriptions_list.html", context={
        "recordings": recordings
    })

@web_router.get("/transcriptions/{recording_id}", response_class=HTMLResponse)
def page_transcription_editor(
    request: Request,
    recording_id: str,
    db: Session = Depends(get_db)
):
    from app.services import transcription as transcription_service
    rec_uuid = UUID(recording_id)
    rec = recording_service.get_recording_by_id(db, rec_uuid)
    if not rec:
        return RedirectResponse(url="/transcriptions", status_code=303)

    transcriptions = transcription_service.get_transcriptions_by_recording(db, rec_uuid)
    latest_transcription = transcriptions[0] if transcriptions else None

    return templates.TemplateResponse(request=request, name="transcription_editor.html", context={
        "recording": rec,
        "transcriptions": transcriptions,
        "latest_transcription": latest_transcription
    })

@web_router.post("/transcriptions/{recording_id}")
def handle_save_transcription(
    recording_id: str,
    transcription_text: str = Form(...),
    transcriber: Optional[str] = Form(None),
    status: str = Form("draft"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    from app.schemas.transcription import TranscriptionCreate
    from app.services import transcription as transcription_service

    rec_uuid = UUID(recording_id)
    t_in = TranscriptionCreate(
        recording_id=rec_uuid,
        transcription_text=transcription_text,
        transcriber=transcriber,
        language_code="sus",
        status=status,
        notes=notes
    )
    transcription_service.create_transcription(db, t_in)
    return RedirectResponse(url=f"/transcriptions/{recording_id}", status_code=303)


# --- RECORD (COLLECTE) ---
@web_router.get("/record", response_class=HTMLResponse)
def page_record(
    request: Request,
    session_id: Optional[str] = None,
    prompt_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    sessions = session_service.get_sessions(db)
    prompts = prompt_service.get_prompts(db, active_only=True)
    return templates.TemplateResponse(request=request, name="record.html", context={
        "sessions": sessions,
        "prompts": prompts,
        "selected_session_id": session_id,
        "selected_prompt_id": prompt_id
    })
