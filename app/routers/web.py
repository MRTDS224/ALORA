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
from app.core.languages import (
    AGE_GROUPS,
    CONSENT_STATUSES,
    DEVICES,
    ENVIRONMENTS,
    GENDERS,
    GUINEA_REGIONS,
    NATIVE_LANGUAGES,
    TARGET_TASKS,
    normalize_choice,
)
from app.core.security import (
    SESSION_COOKIE_NAME,
    check_rate_limit,
    get_client_ip,
    is_secure_cookie,
    sign_token,
)
from app.models import User
from app.schemas.prompt import PromptCreate, PromptUpdate
from app.schemas.session import SessionCreate
from app.schemas.speaker import SpeakerCreate
from app.services import audit as audit_service
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
def page_home(
    request: Request,
    current_user: Optional[User] = Depends(auth_service.get_current_user_optional),
):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "current_user": current_user,
            "platform_url": auth_service.default_home_for_user(current_user),
        },
    )


@web_router.get("/contribuer", response_class=HTMLResponse)
def page_contribute(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="contribute.html",
        context={"regions": GUINEA_REGIONS},
    )


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
        audit_service.record_audit(
            db=db,
            action="auth.login_failed",
            actor_email=email.strip().lower(),
            target_type="auth",
            ip_address=get_client_ip(request),
        )
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

    audit_service.record_audit(
        db=db,
        action="auth.login_success",
        actor=user,
        target_type="auth",
        ip_address=get_client_ip(request),
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
        audit_service.record_audit(
            db=db,
            action="user.create",
            actor=current_user,
            target_type="user",
            target_id=created.id,
            details={"email": created.email, "role": created.role},
            ip_address=get_client_ip(request),
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
    request: Request,
    user_id: str,
    current_user: User = Depends(auth_service.require_web_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    target_id = UUID(user_id)
    if target_id != current_user.id:
        toggled = auth_service.toggle_user_active(db, target_id)
        if toggled:
            audit_service.record_audit(
                db=db,
                action="user.toggle",
                actor=current_user,
                target_type="user",
                target_id=toggled.id,
                details={"email": toggled.email, "is_active": toggled.is_active},
                ip_address=get_client_ip(request),
            )
    return RedirectResponse(url="/admin/users", status_code=303)


# --- ADMIN AUDIT LOGS (ADMIN ONLY) ---
@web_router.get("/admin/audit", response_class=HTMLResponse)
def page_admin_audit(
    request: Request,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    current_user: User = Depends(auth_service.require_web_roles(*ADMIN_ROLES)),
    db: Session = Depends(get_db),
):
    logs = audit_service.list_audit_logs(db, action=action, actor_email=actor_email, limit=150)
    available_actions = audit_service.list_distinct_actions(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_audit.html",
        context={
            "logs": logs,
            "available_actions": available_actions,
            "selected_action": action or "",
            "selected_actor": actor_email or "",
            "current_user": current_user,
        },
    )


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
    last_session = session_service.get_last_session_for_collector(db, current_user.id)
    default_region = (
        normalize_choice(last_session.location, GUINEA_REGIONS, "Conakry")
        if last_session and last_session.location
        else "Conakry"
    )
    return templates.TemplateResponse(
        request=request,
        name="speakers.html",
        context={
            "speakers": speakers,
            "regions": GUINEA_REGIONS,
            "native_languages": NATIVE_LANGUAGES,
            "default_region": default_region,
            "last_session": last_session,
            "current_user": current_user,
        },
    )


@web_router.post("/speakers")
def handle_create_speaker(
    request: Request,
    age_group: str = Form("18-25"),
    gender: str = Form("female"),
    region: str = Form("Conakry"),
    native_language: str = Form("Soussou"),
    other_languages: Optional[str] = Form(None),
    consent_status: str = Form("granted"),
    action: str = Form("save"),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    clean_age = normalize_choice(age_group, AGE_GROUPS, "18-25")
    clean_gender = normalize_choice(gender, GENDERS, "female")
    clean_region = normalize_choice(region, GUINEA_REGIONS, "Conakry")
    clean_native = normalize_choice(native_language, NATIVE_LANGUAGES, "Soussou")
    clean_consent = normalize_choice(consent_status, CONSENT_STATUSES, "granted")
    clean_other = (other_languages.strip()[:200] or None) if other_languages else None

    speaker_in = SpeakerCreate(
        age_group=clean_age,
        gender=clean_gender,
        region=clean_region,
        native_language=clean_native,
        other_languages=clean_other,
        consent_status=clean_consent,
    )
    created_speaker = speaker_service.create_speaker(db, speaker_in)
    audit_service.record_audit(
        db=db,
        action="speaker.create",
        actor=current_user,
        target_type="speaker",
        target_id=created_speaker.id,
        details={"speaker_code": created_speaker.speaker_code, "region": clean_region, "native_language": clean_native},
        ip_address=get_client_ip(request),
    )

    if action == "save_and_collect":
        last_sess = session_service.get_last_session_for_collector(db, current_user.id)
        env = normalize_choice(last_sess.environment if last_sess else None, ENVIRONMENTS, "quiet_room")
        task = normalize_choice(last_sess.target_task if last_sess else None, TARGET_TASKS, "asr")
        dev = normalize_choice(last_sess.device if last_sess else None, DEVICES, "smartphone_mic")
        new_sess = session_service.create_session(
            db,
            SessionCreate(
                speaker_id=created_speaker.id,
                location=clean_region,
                environment=env,
                target_task=task,
                language=settings.DEFAULT_LANGUAGE,
                source="field_agent",
                device=dev,
                collector=current_user.full_name,
            ),
            collector_user_id=current_user.id,
        )
        audit_service.record_audit(
            db=db,
            action="session.create",
            actor=current_user,
            target_type="session",
            target_id=new_sess.id,
            details={"session_code": new_sess.session_code, "speaker_code": created_speaker.speaker_code, "quick_start": True},
            ip_address=get_client_ip(request),
        )
        return RedirectResponse(url=f"/record?session_id={new_sess.id}", status_code=303)

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
    last_session = session_service.get_last_session_for_collector(db, current_user.id)
    default_location = (
        normalize_choice(last_session.location, GUINEA_REGIONS, "Conakry")
        if last_session and last_session.location
        else "Conakry"
    )
    return templates.TemplateResponse(
        request=request,
        name="sessions.html",
        context={
            "speakers": speakers,
            "sessions": sessions,
            "regions": GUINEA_REGIONS,
            "default_location": default_location,
            "selected_speaker_id": speaker_id,
            "current_user": current_user,
        },
    )


@web_router.post("/sessions")
def handle_create_session(
    request: Request,
    speaker_id: str = Form(...),
    location: str = Form("Conakry"),
    environment: str = Form("quiet_room"),
    target_task: str = Form("asr"),
    device: str = Form("smartphone_mic"),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        spk_uuid = UUID(speaker_id)
    except ValueError:
        return RedirectResponse(url="/sessions", status_code=303)

    clean_location = normalize_choice(location, GUINEA_REGIONS, "Conakry")
    clean_env = normalize_choice(environment, ENVIRONMENTS, "quiet_room")
    clean_task = normalize_choice(target_task, TARGET_TASKS, "asr")
    clean_device = normalize_choice(device, DEVICES, "smartphone_mic")
    clean_notes = (notes.strip()[:1000] or None) if notes else None

    session_in = SessionCreate(
        speaker_id=spk_uuid,
        location=clean_location,
        environment=clean_env,
        target_task=clean_task,
        language=settings.DEFAULT_LANGUAGE,
        source="field_agent",
        device=clean_device,
        collector=current_user.full_name,
        notes=clean_notes,
    )
    created_sess = session_service.create_session(db, session_in, collector_user_id=current_user.id)
    audit_service.record_audit(
        db=db,
        action="session.create",
        actor=current_user,
        target_type="session",
        target_id=created_sess.id,
        details={"session_code": created_sess.session_code, "location": clean_location, "target_task": clean_task},
        ip_address=get_client_ip(request),
    )
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

    prompt_lang = "mul" if prompt_type == "image" else settings.DEFAULT_LANGUAGE
    prompt_in = PromptCreate(
        title=title,
        content=content,
        prompt_type=prompt_type,
        language=prompt_lang,
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
                language="mul",
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
    prompt_id: UUID,
    next: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    prompt_service.toggle_prompt_active(db, prompt_id)
    dest = next if (next and next.startswith("/") and not next.startswith("//")) else "/prompts"
    return RedirectResponse(url=dest, status_code=303)


@web_router.get("/prompts/{prompt_id}", response_class=HTMLResponse)
def page_prompt_detail(
    request: Request,
    prompt_id: UUID,
    saved: Optional[str] = None,
    error: Optional[str] = None,
    current_user: User = Depends(auth_service.require_web_roles(*COLLECTOR_ROLES)),
    db: Session = Depends(get_db),
):
    prompt = prompt_service.get_prompt_by_id(db, prompt_id)
    if not prompt:
        return RedirectResponse(url="/prompts", status_code=303)
    recordings_count = prompt_service.count_prompt_recordings(db, prompt_id)
    return templates.TemplateResponse(
        request=request,
        name="prompt_detail.html",
        context={
            "prompt": prompt,
            "recordings_count": recordings_count,
            "saved": saved == "1",
            "error": error,
            "current_user": current_user,
        },
    )


@web_router.post("/prompts/{prompt_id}/edit")
async def handle_edit_prompt(
    prompt_id: UUID,
    title: str = Form(...),
    content: str = Form(...),
    prompt_type: str = Form("image"),
    description: Optional[str] = Form(None),
    topic: Optional[str] = Form(None),
    difficulty: str = Form("easy"),
    min_duration_seconds: Optional[str] = Form(None),
    media_license: Optional[str] = Form(None),
    media_attribution: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
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

    updated = prompt_service.update_prompt(
        db,
        prompt_id,
        PromptUpdate(
            title=title,
            content=content,
            prompt_type=prompt_type,
            description=description,
            topic=topic,
            difficulty=difficulty,
            min_duration_seconds=parsed_min_dur,
            media_license=media_license,
            media_attribution=media_attribution,
            active=(active == "on"),
        ),
    )
    if not updated:
        return RedirectResponse(url="/prompts", status_code=303)

    if image_file and image_file.filename:
        image_bytes = await image_file.read()
        if image_bytes:
            try:
                prompt_service.attach_prompt_media(
                    db=db,
                    prompt_id=prompt_id,
                    image_bytes=image_bytes,
                    content_type=image_file.content_type or "image/jpeg",
                )
            except ValueError as e:
                from urllib.parse import quote as url_quote
                return RedirectResponse(
                    url=f"/prompts/{prompt_id}?error={url_quote(str(e))}",
                    status_code=303,
                )

    return RedirectResponse(url=f"/prompts/{prompt_id}?saved=1", status_code=303)


@web_router.post("/prompts/{prompt_id}/delete")
def handle_delete_prompt(
    prompt_id: UUID,
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    try:
        prompt_service.delete_prompt(db, prompt_id)
    except ValueError as e:
        from urllib.parse import quote as url_quote
        return RedirectResponse(
            url=f"/prompts/{prompt_id}?error={url_quote(str(e))}",
            status_code=303,
        )
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
    request: Request,
    recording_id: str,
    action: str = Form(...),
    audio_quality: str = Form("good"),
    noise_level: str = Form("low"),
    clipping: Optional[str] = Form(None),
    speech_present: Optional[str] = Form(None),
    multiple_speakers: Optional[str] = Form(None),
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
        audio_quality=normalize_choice(audio_quality, ("good", "fair", "poor"), "good"),
        noise_level=normalize_choice(noise_level, ("low", "medium", "high"), "low"),
        clipping=bool(clipping),
        speech_present=bool(speech_present),
        multiple_speakers=bool(multiple_speakers),
        reviewer=current_user.full_name,
        notes=(notes.strip()[:1000] or None) if notes else None,
    )
    quality_service.create_quality_annotation(
        db,
        qual_in,
        recording_status=target_status,
        reviewer_user_id=current_user.id,
    )
    audit_service.record_audit(
        db=db,
        action=f"recording.{target_status}",
        actor=current_user,
        target_type="recording",
        target_id=rec_uuid,
        details={"audio_quality": qual_in.audio_quality, "noise_level": qual_in.noise_level},
        ip_address=get_client_ip(request),
    )
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
    msg: Optional[str] = None,
    error: Optional[str] = None,
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

    required_approvals = max(1, int(settings.TRANSCRIPTION_REQUIRED_APPROVALS or 2))
    latest_approvals = 0
    user_already_reviewed = False
    is_latest_author = False
    if latest_transcription:
        latest_approvals = sum(1 for r in latest_transcription.reviews if r.decision == "approved")
        user_already_reviewed = any(r.reviewer_user_id == current_user.id for r in latest_transcription.reviews)
        is_latest_author = bool(latest_transcription.author_user_id and latest_transcription.author_user_id == current_user.id)

    return templates.TemplateResponse(
        request=request,
        name="transcription_editor.html",
        context={
            "recording": rec,
            "transcriptions": transcriptions,
            "latest_transcription": latest_transcription,
            "latest_approvals": latest_approvals,
            "required_approvals": required_approvals,
            "user_already_reviewed": user_already_reviewed,
            "is_latest_author": is_latest_author,
            "msg": msg,
            "error": error,
            "current_user": current_user,
        },
    )


@web_router.post("/transcriptions/{recording_id}")
def handle_save_transcription(
    request: Request,
    recording_id: str,
    transcription_text: str = Form(...),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote as url_quote
    from app.schemas.transcription import TranscriptionCreate
    from app.services import transcription as transcription_service

    rec_uuid = UUID(recording_id)
    rec = recording_service.get_recording_by_id(db, rec_uuid)
    session_lang = (
        rec.session.language
        if rec and rec.session and rec.session.language
        else settings.DEFAULT_LANGUAGE
    )
    t_in = TranscriptionCreate(
        recording_id=rec_uuid,
        transcription_text=transcription_text,
        transcriber=current_user.full_name,
        language_code=session_lang,
        status="draft",
        notes=(notes.strip()[:1000] or None) if notes else None,
    )
    created = transcription_service.create_transcription(db, t_in, author=current_user)
    audit_service.record_audit(
        db=db,
        action="transcription.create",
        actor=current_user,
        target_type="transcription",
        target_id=created.id,
        details={"recording_id": recording_id, "version": created.version},
        ip_address=get_client_ip(request),
    )
    ok_msg = url_quote(f"Version v{created.version} enregistrée (en attente de validation par un autre réviseur).")
    return RedirectResponse(url=f"/transcriptions/{recording_id}?msg={ok_msg}", status_code=303)


@web_router.post("/transcriptions/{recording_id}/versions/{transcription_id}/review")
def handle_review_transcription(
    request: Request,
    recording_id: str,
    transcription_id: UUID,
    decision: str = Form(...),
    comment: Optional[str] = Form(None),
    corrected_text: Optional[str] = Form(None),
    current_user: User = Depends(auth_service.require_web_roles(*REVIEWER_ROLES)),
    db: Session = Depends(get_db),
):
    from urllib.parse import quote as url_quote
    from app.services import transcription as transcription_service

    try:
        res = transcription_service.review_transcription(
            db=db,
            transcription_id=transcription_id,
            reviewer=current_user,
            decision=decision,
            comment=comment,
            corrected_text=corrected_text,
        )
    except (LookupError, PermissionError, ValueError) as e:
        return RedirectResponse(
            url=f"/transcriptions/{recording_id}?error={url_quote(str(e))}",
            status_code=303,
        )

    audit_action = (
        "transcription.approve" if decision == "approved" else "transcription.propose_correction"
    )
    audit_service.record_audit(
        db=db,
        action=audit_action,
        actor=current_user,
        target_type="transcription",
        target_id=transcription_id,
        details={
            "recording_id": recording_id,
            "approvals_count": res["approvals_count"],
            "required_approvals": res["required_approvals"],
            "created_version": res["created_version"].version if res["created_version"] else None,
        },
        ip_address=get_client_ip(request),
    )

    if res["created_version"]:
        info = f"Version corrigée v{res['created_version'].version} créée ! Elle devra être validée par un autre utilisateur."
    elif res["transcription"].transcription_status == "accepted":
        info = f"Version v{res['transcription'].version} acceptée ({res['approvals_count']}/{res['required_approvals']} validations atteintes) !"
    else:
        info = f"Validation enregistrée ({res['approvals_count']}/{res['required_approvals']} approbations)."

    return RedirectResponse(url=f"/transcriptions/{recording_id}?msg={url_quote(info)}", status_code=303)


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
