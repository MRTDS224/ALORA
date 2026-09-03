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
from app.schemas.speaker import SpeakerCreate
from app.schemas.session import SessionCreate
from app.schemas.prompt import PromptCreate

templates = Jinja2Templates(directory="app/templates")

web_router = APIRouter(tags=["Web Pages"])

# --- SPEAKERS ---
@web_router.get("/speakers", response_class=HTMLResponse)
def page_speakers(request: Request, db: Session = Depends(get_db)):
    speakers = speaker_service.get_speakers(db)
    return templates.TemplateResponse("speakers.html", {
        "request": request,
        "speakers": speakers
    })

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
    return templates.TemplateResponse("sessions.html", {
        "request": request,
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
    return templates.TemplateResponse("prompts.html", {
        "request": request,
        "prompts": prompts
    })

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
    return templates.TemplateResponse("record.html", {
        "request": request,
        "sessions": sessions,
        "prompts": prompts,
        "selected_session_id": session_id,
        "selected_prompt_id": prompt_id
    })
