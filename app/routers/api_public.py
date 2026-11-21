"""
Public zero-friction API for voluntary Susu speakers on /contribuer.
Uses an HMAC-signed anonymous contributor cookie (speaker_id + session_id) so visitors
never need an account and can never view or access any other speaker's data.
"""

from typing import Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    CONTRIBUTOR_COOKIE_NAME,
    check_rate_limit,
    sign_token,
    verify_token,
)
from app.models import ContactMessage
from app.schemas.prompt import PromptRead
from app.schemas.session import SessionCreate
from app.schemas.speaker import SpeakerCreate
from app.services import prompt as prompt_service
from app.services import recording as recording_service
from app.services import session as session_service
from app.services import speaker as speaker_service

router = APIRouter(prefix="/api/public", tags=["Public Contributor"])

MAX_PUBLIC_AUDIO_BYTES = 8 * 1024 * 1024  # 8 MB


class PublicOnboardingRequest(BaseModel):
    age_group: str = "18-25"
    gender: str = "female"
    region: str = "Conakry"
    native_language: str = "Susu"
    consent_accepted: bool = True


class PublicProfileStatus(BaseModel):
    has_profile: bool
    speaker_code: Optional[str] = None
    region: Optional[str] = None
    completed_count: int = 0


class PublicNextPromptResponse(BaseModel):
    prompt: Optional[PromptRead] = None
    completed_count: int
    remaining_count: int


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _get_contributor_ids(request: Request) -> Optional[tuple[UUID, UUID]]:
    token = request.cookies.get(CONTRIBUTOR_COOKIE_NAME)
    payload = verify_token(token, max_age_seconds=60 * 60 * 24 * 30)  # 30 days
    if not payload:
        return None
    try:
        return UUID(payload["sid"]), UUID(payload["ses"])
    except Exception:
        return None


@router.get("/me", response_model=PublicProfileStatus)
def public_profile_status(request: Request, db: Session = Depends(get_db)):
    ids = _get_contributor_ids(request)
    if not ids:
        return PublicProfileStatus(has_profile=False)

    speaker_id, session_id = ids
    spk = speaker_service.get_speaker_by_id(db, speaker_id)
    sess = session_service.get_session_by_id(db, session_id)
    if not spk or not sess:
        return PublicProfileStatus(has_profile=False)

    recs = recording_service.get_recordings(db, session_id=session_id, limit=500)
    return PublicProfileStatus(
        has_profile=True,
        speaker_code=str(spk.speaker_code),
        region=spk.region,
        completed_count=len(recs),
    )


@router.post("/onboarding", response_model=PublicProfileStatus, status_code=status.HTTP_201_CREATED)
def public_onboarding(
    body: PublicOnboardingRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if not check_rate_limit(f"onboard:{_client_ip(request)}", max_requests=30, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Trop de demandes. Veuillez réessayer un peu plus tard.")

    if not body.consent_accepted:
        raise HTTPException(
            status_code=400,
            detail="Veuillez accepter le consentement anonyme avant de commencer.",
        )

    spk = speaker_service.create_speaker(
        db,
        SpeakerCreate(
            age_group=body.age_group,
            gender=body.gender,
            region=body.region,
            native_language=body.native_language or "Susu",
            consent_status="granted",
        ),
    )
    sess = session_service.create_session(
        db,
        SessionCreate(
            speaker_id=spk.id,
            location=body.region,
            environment="indoor",
            target_task="asr",
            source="public_web",
            device="smartphone_mic",
            collector="volontaire_web",
        ),
    )

    token = sign_token({"sid": str(spk.id), "ses": str(sess.id)})
    response.set_cookie(
        key=CONTRIBUTOR_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )

    return PublicProfileStatus(
        has_profile=True,
        speaker_code=str(spk.speaker_code),
        region=spk.region,
        completed_count=0,
    )


@router.post("/reset-profile")
def public_reset_profile(response: Response):
    response.delete_cookie(key=CONTRIBUTOR_COOKIE_NAME)
    return {"status": "ok"}


@router.get("/next-prompt", response_model=PublicNextPromptResponse)
def public_next_prompt(
    request: Request,
    exclude_ids: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    ids = _get_contributor_ids(request)
    if not ids:
        raise HTTPException(status_code=401, detail="Profil contributeur non initialisé.")
    _, session_id = ids

    parsed_excludes: Set[UUID] = set()
    if exclude_ids:
        for raw in exclude_ids.split(","):
            raw = raw.strip()
            if raw:
                try:
                    parsed_excludes.add(UUID(raw))
                except ValueError:
                    pass

    try:
        rot = prompt_service.get_next_prompt_for_session(
            db, session_id=session_id, exclude_ids=parsed_excludes
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Session expirée, veuillez recommencer.")

    return PublicNextPromptResponse(
        prompt=rot["prompt"],
        completed_count=rot["completed_in_session"],
        remaining_count=rot["remaining_for_speaker"],
    )


@router.post("/recordings", status_code=status.HTTP_201_CREATED)
async def public_upload_recording(
    request: Request,
    file: UploadFile = File(...),
    prompt_id: Optional[str] = Form(None),
    duration_seconds: Optional[float] = Form(None),
    db: Session = Depends(get_db),
):
    if not check_rate_limit(f"upload:{_client_ip(request)}", max_requests=60, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Limite d'envois atteinte pour cette heure. Merci beaucoup !")

    ids = _get_contributor_ids(request)
    if not ids:
        raise HTTPException(status_code=401, detail="Veuillez d'abord renseigner votre profil anonyme.")
    _, session_id = ids

    sess = session_service.get_session_by_id(db, session_id)
    if not sess:
        raise HTTPException(status_code=401, detail="Session expirée.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="L'enregistrement est vide.")
    if len(audio_bytes) > MAX_PUBLIC_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="L'enregistrement est trop volumineux (8 Mo max).")

    prompt_uuid = None
    if prompt_id and prompt_id.strip():
        try:
            prompt_uuid = UUID(prompt_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Identifiant d'image invalide.")

    ct = file.content_type or "audio/webm"
    ext = "webm" if "webm" in ct else ("ogg" if "ogg" in ct else ("m4a" if "mp4" in ct else "wav"))

    rec = recording_service.create_recording(
        db=db,
        session_id=session_id,
        prompt_id=prompt_uuid,
        audio_bytes=audio_bytes,
        duration_seconds=duration_seconds,
        file_format=ext,
        content_type=ct,
    )

    total_for_session = len(recording_service.get_recordings(db, session_id=session_id, limit=500))
    return {
        "id": str(rec.id),
        "recording_code": rec.recording_code,
        "duration_seconds": rec.duration_seconds,
        "auto_quality_flags": rec.auto_quality_flags,
        "completed_count": total_for_session,
    }


class PublicContactRequest(BaseModel):
    sender_name: str
    sender_contact: str
    profile_type: str = "chercheur"
    message: str
    website: Optional[str] = None  # Honeypot anti-bot field (must stay empty)


@router.post("/contact", status_code=status.HTTP_201_CREATED)
def public_contact_submit(
    body: PublicContactRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not check_rate_limit(f"contact:{_client_ip(request)}", max_requests=10, window_seconds=3600):
        raise HTTPException(status_code=429, detail="Trop de messages envoyés. Veuillez réessayer plus tard.")

    # Silent accept for bots filling hidden honeypot
    if body.website and body.website.strip():
        return {"status": "ok", "message": "Merci pour votre message !"}

    name = body.sender_name.strip()
    contact = body.sender_contact.strip()
    msg = body.message.strip()
    if len(name) < 2 or len(contact) < 4 or len(msg) < 5:
        raise HTTPException(status_code=400, detail="Merci de renseigner votre nom, un moyen de contact et votre message.")

    entry = ContactMessage(
        sender_name=name[:150],
        sender_contact=contact[:255],
        profile_type=(body.profile_type or "autre")[:60],
        message=msg[:4000],
        is_read=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"status": "ok", "id": str(entry.id), "message": "Merci ! Votre message a bien été transmis."}
