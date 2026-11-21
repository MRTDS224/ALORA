import datetime
import hashlib
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    check_rate_limit,
    get_client_ip,
    is_secure_cookie,
    sign_token,
)
from app.models import User
from app.schemas.prompt import PromptCreate
from app.schemas.session import SessionCreate
from app.schemas.speaker import SpeakerCreate
from app.services import auth as auth_service
from app.services import prompt as prompt_service
from app.services import recording as recording_service
from app.services import session as session_service
from app.services import speaker as speaker_service

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["current_year"] = datetime.datetime.now().year


def static_url(asset_path: str) -> str:
    """Returns /static/<path>?v=<short-hash> so browsers never serve stale CSS/JS."""
    clean = asset_path.lstrip("/")
    file_path = Path("static") / clean
    if file_path.is_file():
        digest = hashlib.md5(file_path.read_bytes()).hexdigest()[:8]
        return f"/static/{clean}?v={digest}"
    return f"/static/{clean}"


templates.env.globals["static_url"] = static_url

web_router = APIRouter(tags=["Web Pages"])

COLLECTOR_ROLES = ("collector", "reviewer", "admin")
REVIEWER_ROLES = ("reviewer", "admin")
ADMIN_ROLES = ("admin",)


# --- PUBLIC PAGES ---
@web_router.get("/", response_class=HTMLResponse)
def page_home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html", context={})


@web_router.get("/contribuer", response_class=HTMLResponse)
def page_contribute(request: Request):
    return templates.TemplateResponse(request=request, name="contribute.html", context={})


# --- AUTHENTICATION ---
@web_router.get("/login", response_class=HTMLResponse)
def page_login(
    request: Request,
    next: str = "/dashboard",
    current_user: Optional[User] = Depends(auth_service.get_current_user_optional),
):
    if current_user:
        dest = "/record" if current_user.role == "collector" else "/dashboard"
        return RedirectResponse(url=dest, status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"next_url": next, "error": None, "email": "", "current_user": None},
    )


@web_router.post("/login")
def handle_login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/dashboard"),
    db: Session = Depends(get_db),
):
    if not check_rate_limit(f"login:{get_client_ip(request)}", max_requests=20, window_seconds=900):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "next_url": next,
                "error": "Trop de tentatives de connexion. Réessayez dans quelques minutes.",
                "email": email,
                "current_user": None,
            },
            status_code=429,
        )

    user = auth_service.authenticate_user(db, email=email, password=password)
    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "next_url": next,
                "error": "Identifiants invalides ou compte désactivé.",
                "email": email,
                "current_user": None,
            },
            status_code=401,
        )

    safe_dest = next if (next.startswith("/") and not next.startswith("//")) else "/dashboard"
    if user.role == "collector" and safe_dest in {"/dashboard", "/admin/users"}:
        safe_dest = "/record"

    resp = RedirectResponse(url=safe_dest, status_code=303)
    token = sign_token({"uid": str(user.id), "role": user.role})
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_secure_cookie(request),
        samesite="lax",
        max_age=settings.SESSION_MAX_AGE_SECONDS,
    )
    return resp


@web_router.post("/logout")
def handle_logout():
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(key=SESSION_COOKIE_NAME)
    return resp


# --- ADMIN USERS ---
@web_router.get("/admin/users", response_class=HTMLResponse)
def page_admin_users(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    users = auth_service.list_users(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context={"users": users, "current_user": current_user, "error": None, "success": None},
    )


@web_router.post("/admin/users")
def handle_create_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("collector"),
    current_user: User = Depends(auth_service.require_web_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    error = None
    success = None
    try:
        created = auth_service.create_user(
            db=db, email=email, full_name=full_name, password=password, role=role
        )
        success = f"Compte créé : {created.full_name} ({created.email}, rôle {created.role})."
    except ValueError as e:
        error = str(e)

    users = auth_service.list_users(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context={"users": users, "current_user": current_user, "error": error, "success": success},
        status_code=400 if error else 200,
    )


@web_router.post("/admin/users/{user_id}/toggle")
def handle_toggle_user(
    user_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    target_id = UUID(user_id)
    if target_id != current_user.id:
        auth_service.toggle_user_active(db, target_id)
    return RedirectResponse(url="/admin/users", status_code=303)


# --- ADMIN CONTACT MESSAGES (REVIEWER & ADMIN) ---
@web_router.get("/admin/messages", response_class=HTMLResponse)
def page_admin_messages(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.models import ContactMessage

    messages = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(200).all()
    unread_count = sum(1 for m in messages if not m.is_read)
    return templates.TemplateResponse(
        request=request,
        name="admin_messages.html",
        context={"messages": messages, "unread_count": unread_count, "current_user": current_user},
    )


@web_router.post("/admin/messages/{message_id}/toggle-read")
def handle_toggle_message_read(
    message_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.models import ContactMessage

    entry = db.query(ContactMessage).filter(ContactMessage.id == UUID(message_id)).first()
    if entry:
        entry.is_read = not entry.is_read
        db.commit()
    return RedirectResponse(url="/admin/messages", status_code=303)


# --- DASHBOARD (REVIEWER & ADMIN) ---
@web_router.get("/dashboard", response_class=HTMLResponse)
def page_dashboard(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.services import stats as stats_service

    stats = stats_service.get_dashboard_stats(db)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"stats": stats, "current_user": current_user},
    )


# --- SPEAKERS (COLLECTOR+) ---
@web_router.get("/speakers", response_class=HTMLResponse)
def page_speakers(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    speakers = speaker_service.get_speakers(db)
    return templates.TemplateResponse(
        request=request,
        name="speakers.html",
        context={"speakers": speakers, "current_user": current_user},
    )


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
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    speaker_in = SpeakerCreate(
        speaker_code=speaker_code if speaker_code else None,
        age_group=age_group,
        gender=gender,
        region=region,
        location=location,
        native_language=native_language,
        other_languages=other_languages,
        consent_status=consent_status,
    )
    speaker_service.create_speaker(db, speaker_in)
    return RedirectResponse(url="/speakers", status_code=303)


# --- SESSIONS (COLLECTOR+) ---
@web_router.get("/sessions", response_class=HTMLResponse)
def page_sessions(
    request: Request,
    speaker_id: Optional[str] = None,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    speakers = speaker_service.get_speakers(db)
    sessions = session_service.get_sessions(db)
    return templates.TemplateResponse(
        request=request,
        name="sessions.html",
        context={
            "speakers": speakers,
            "sessions": sessions,
            "selected_speaker_id": speaker_id,
            "current_user": current_user,
        },
    )


@web_router.post("/sessions")
def handle_create_session(
    speaker_id: str = Form(...),
    session_code: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    environment: str = Form("quiet_room"),
    target_task: str = Form("asr"),
    device: str = Form("smartphone_mic"),
    collector: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    session_in = SessionCreate(
        speaker_id=UUID(speaker_id),
        session_code=session_code if session_code else None,
        location=location,
        environment=environment,
        target_task=target_task if target_task in {"asr", "tts"} else "asr",
        source="field_agent",
        device=device,
        collector=collector or current_user.full_name,
        notes=notes,
    )
    session_service.create_session(db, session_in)
    return RedirectResponse(url="/sessions", status_code=303)


# --- PROMPTS (COLLECTOR+) ---
@web_router.get("/prompts", response_class=HTMLResponse)
def page_prompts(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    prompts = prompt_service.get_prompts(db, limit=200)
    return templates.TemplateResponse(
        request=request,
        name="prompts.html",
        context={"prompts": prompts, "current_user": current_user},
    )


@web_router.post("/prompts")
async def handle_create_prompt(
    title: str = Form(...),
    content: str = Form(...),
    prompt_type: str = Form("image"),
    description: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    difficulty: str = Form("easy"),
    min_duration_seconds: Optional[str] = Form(None),
    media_license: Optional[str] = Form(None),
    media_attribution: Optional[str] = Form(None),
    image_file: Optional[UploadFile] = File(None),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    parsed_min_dur: Optional[float] = None
    if min_duration_seconds and min_duration_seconds.strip():
        try:
            parsed_min_dur = float(min_duration_seconds.strip())
        except ValueError:
            parsed_min_dur = None

    prompt_in = PromptCreate(
        title=title,
        content=content,
        prompt_type=prompt_type,
        description=description,
        topic=topic,
        difficulty=difficulty,
        min_duration_seconds=parsed_min_dur,
        media_license=media_license.strip() if media_license and media_license.strip() else None,
        media_attribution=(
            media_attribution.strip() if media_attribution and media_attribution.strip() else current_user.full_name
        ),
        active=True,
    )
    created = prompt_service.create_prompt(db, prompt_in, created_by_user_id=current_user.id)

    if image_file and image_file.filename:
        image_bytes = await image_file.read()
        if image_bytes:
            try:
                prompt_service.attach_prompt_media(
                    db=db,
                    prompt_id=created.id,
                    image_bytes=image_bytes,
                    content_type=image_file.content_type or "image/jpeg",
                )
            except ValueError as e:
                print(f"[Prompt Media Upload Warning] {e}")

    return RedirectResponse(url="/prompts", status_code=303)


@web_router.post("/prompts/batch")
async def handle_batch_upload_prompts(
    topic: str = Form(...),
    title_prefix: str = Form("Scène terrain"),
    content: str = Form("Racontez en soussou ce que vous voyez sur cette photo."),
    media_license: str = Form("CC-BY-4.0"),
    image_files: List[UploadFile] = File(...),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    idx = 0
    for f in image_files:
        if not f or not f.filename:
            continue
        raw = await f.read()
        if not raw:
            continue
        idx += 1
        created = prompt_service.create_prompt(
            db,
            PromptCreate(
                prompt_type="image",
                title=f"{title_prefix.strip()} #{idx}",
                content=content.strip(),
                topic=topic.strip() or None,
                min_duration_seconds=15.0,
                media_license=media_license.strip() or "CC-BY-4.0",
                media_attribution=current_user.full_name,
                active=True,
            ),
            created_by_user_id=current_user.id,
        )
        try:
            prompt_service.attach_prompt_media(
                db=db,
                prompt_id=created.id,
                image_bytes=raw,
                content_type=f.content_type or "image/jpeg",
            )
        except ValueError as e:
            print(f"[Batch Upload Warning] {f.filename}: {e}")

    return RedirectResponse(url="/prompts", status_code=303)


@web_router.post("/prompts/{prompt_id}/toggle")
def handle_toggle_prompt(
    prompt_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    prompt_service.toggle_prompt_active(db, UUID(prompt_id))
    return RedirectResponse(url="/prompts", status_code=303)


# --- RECORDINGS & VALIDATION (REVIEWER+) ---
@web_router.get("/recordings", response_class=HTMLResponse)
def page_recordings(
    request: Request,
    status: Optional[str] = None,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    recordings = recording_service.get_recordings(db, status=status)
    return templates.TemplateResponse(
        request=request,
        name="recordings_list.html",
        context={
            "recordings": recordings,
            "current_status": status,
            "current_user": current_user,
        },
    )


@web_router.get("/recordings/{recording_id}", response_class=HTMLResponse)
def page_recording_detail(
    request: Request,
    recording_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.services import quality as quality_service

    rec_uuid = UUID(recording_id)
    rec = recording_service.get_recording_by_id(db, rec_uuid)
    if not rec:
        return RedirectResponse(url="/recordings", status_code=303)

    qualities = quality_service.get_quality_annotations_by_recording(db, rec_uuid)
    last_quality = qualities[0] if qualities else None

    return templates.TemplateResponse(
        request=request,
        name="recording_detail.html",
        context={
            "recording": rec,
            "quality_history": qualities,
            "last_quality": last_quality,
            "current_user": current_user,
        },
    )


@web_router.post("/recordings/{recording_id}/evaluate")
def handle_evaluate_recording(
    recording_id: str,
    action: str = Form(...),
    audio_quality: str = Form("good"),
    noise_level: str = Form("low"),
    clipping: Optional[str] = Form(None),
    speech_present: Optional[str] = Form(None),
    multiple_speakers: Optional[str] = Form(None),
    reviewer: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
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
        reviewer=reviewer or current_user.full_name,
        notes=notes,
    )
    quality_service.create_quality_annotation(db, qual_in, recording_status=target_status)
    return RedirectResponse(url=f"/recordings/{recording_id}", status_code=303)


# --- TRANSCRIPTIONS (REVIEWER+) ---
@web_router.get("/transcriptions", response_class=HTMLResponse)
def page_transcriptions(
    request: Request,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    recordings = recording_service.get_recordings(db)
    return templates.TemplateResponse(
        request=request,
        name="transcriptions_list.html",
        context={"recordings": recordings, "current_user": current_user},
    )


@web_router.get("/transcriptions/{recording_id}", response_class=HTMLResponse)
def page_transcription_editor(
    request: Request,
    recording_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.services import transcription as transcription_service

    rec_uuid = UUID(recording_id)
    rec = recording_service.get_recording_by_id(db, rec_uuid)
    if not rec:
        return RedirectResponse(url="/transcriptions", status_code=303)

    transcriptions = transcription_service.get_transcriptions_by_recording(db, rec_uuid)
    latest_transcription = transcriptions[0] if transcriptions else None

    return templates.TemplateResponse(
        request=request,
        name="transcription_editor.html",
        context={
            "recording": rec,
            "transcriptions": transcriptions,
            "latest_transcription": latest_transcription,
            "current_user": current_user,
        },
    )


@web_router.post("/transcriptions/{recording_id}")
def handle_save_transcription(
    recording_id: str,
    transcription_text: str = Form(...),
    transcriber: Optional[str] = Form(None),
    status: str = Form("draft"),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from app.schemas.transcription import TranscriptionCreate
    from app.services import transcription as transcription_service

    rec_uuid = UUID(recording_id)
    t_in = TranscriptionCreate(
        recording_id=rec_uuid,
        transcription_text=transcription_text,
        transcriber=transcriber or current_user.full_name,
        language_code="sus",
        status=status,
        notes=notes,
    )
    transcription_service.create_transcription(db, t_in)
    return RedirectResponse(url=f"/transcriptions/{recording_id}", status_code=303)


# --- RECORD / COLLECTE AGENT (COLLECTOR+) ---
@web_router.get("/record", response_class=HTMLResponse)
def page_record(
    request: Request,
    session_id: Optional[str] = None,
    prompt_id: Optional[str] = None,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    sessions = session_service.get_sessions(db)
    prompts = prompt_service.get_prompts(db, limit=200, active_only=True)
    return templates.TemplateResponse(
        request=request,
        name="record.html",
        context={
            "sessions": sessions,
            "prompts": prompts,
            "selected_session_id": session_id,
            "selected_prompt_id": prompt_id,
            "current_user": current_user,
        },
    )
