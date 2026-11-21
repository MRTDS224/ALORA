from collections import Counter
from typing import Any, Dict, List, Optional, Set
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Prompt, Recording, Session as SessionModel
from app.schemas.prompt import PromptCreate, PromptUpdate
from app.services.storage import storage_service

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def generate_prompt_code(db: Session) -> str:
    last = (
        db.query(Prompt.prompt_code)
        .filter(Prompt.prompt_code.like("PRM_%"))
        .order_by(Prompt.prompt_code.desc())
        .first()
    )
    next_num = 1
    if last and last[0]:
        try:
            next_num = int(str(last[0]).split("_", 1)[1]) + 1
        except (ValueError, IndexError):
            next_num = (db.query(func.count(Prompt.id)).scalar() or 0) + 1
    return f"PRM_{next_num:06d}"


def create_prompt(
    db: Session,
    prompt_in: PromptCreate,
    created_by_user_id: Optional[UUID] = None,
) -> Prompt:
    code = prompt_in.prompt_code or generate_prompt_code(db)
    min_dur = prompt_in.min_duration_seconds
    if min_dur is None and prompt_in.prompt_type == "image":
        min_dur = 15.0

    db_prompt = Prompt(
        prompt_code=code,
        prompt_type=prompt_in.prompt_type,
        title=prompt_in.title,
        description=prompt_in.description,
        content=prompt_in.content,
        media_object_key=prompt_in.media_object_key,
        media_content_type=prompt_in.media_content_type,
        media_license=prompt_in.media_license,
        media_attribution=prompt_in.media_attribution,
        min_duration_seconds=min_dur,
        created_by_user_id=created_by_user_id,
        language=prompt_in.language,
        topic=prompt_in.topic,
        difficulty=prompt_in.difficulty,
        active=prompt_in.active,
    )
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt


def attach_prompt_media(
    db: Session,
    prompt_id: UUID,
    image_bytes: bytes,
    content_type: str,
) -> Prompt:
    prompt = get_prompt_by_id(db, prompt_id)
    if not prompt:
        raise ValueError("Prompt non trouvé")

    ct_clean = (content_type or "").split(";")[0].strip().lower()
    if ct_clean not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Format d'image non supporté (JPEG, PNG ou WebP uniquement)")
    if not image_bytes:
        raise ValueError("Le fichier image est vide")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("L'image dépasse la taille maximale autorisée (5 Mo)")

    ext = ALLOWED_IMAGE_TYPES[ct_clean]
    object_key = storage_service.generate_prompt_media_key(
        prompt_code=str(prompt.prompt_code),
        file_extension=ext,
    )
    storage_service.upload_file(
        file_bytes=image_bytes,
        object_key=object_key,
        content_type=ct_clean,
    )

    prompt.media_object_key = object_key
    prompt.media_content_type = ct_clean
    if prompt.min_duration_seconds is None and prompt.prompt_type == "image":
        prompt.min_duration_seconds = 15.0

    db.commit()
    db.refresh(prompt)
    return prompt


def get_prompts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    prompt_type: Optional[str] = None,
) -> List[Prompt]:
    q = db.query(Prompt)
    if active_only:
        q = q.filter(Prompt.active == True)
    if prompt_type:
        q = q.filter(Prompt.prompt_type == prompt_type)
    return q.order_by(Prompt.created_at.desc()).offset(skip).limit(limit).all()


def get_prompt_by_id(db: Session, prompt_id: UUID) -> Optional[Prompt]:
    return db.query(Prompt).filter(Prompt.id == prompt_id).first()


def toggle_prompt_active(db: Session, prompt_id: UUID) -> Optional[Prompt]:
    prompt = get_prompt_by_id(db, prompt_id)
    if prompt:
        prompt.active = not prompt.active
        db.commit()
        db.refresh(prompt)
    return prompt


def update_prompt(
    db: Session,
    prompt_id: UUID,
    prompt_in: PromptUpdate,
) -> Optional[Prompt]:
    prompt = get_prompt_by_id(db, prompt_id)
    if not prompt:
        return None

    updates = prompt_in.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if isinstance(value, str) and field in {"title", "content", "description", "topic", "media_license", "media_attribution"}:
            cleaned = value.strip()
            if field in {"description", "topic", "media_license", "media_attribution"}:
                value = cleaned or None
            else:
                value = cleaned
        setattr(prompt, field, value)

    db.commit()
    db.refresh(prompt)
    return prompt


def count_prompt_recordings(db: Session, prompt_id: UUID) -> int:
    return int(
        db.query(func.count(Recording.id))
        .filter(Recording.prompt_id == prompt_id)
        .scalar()
        or 0
    )


def delete_prompt(db: Session, prompt_id: UUID) -> bool:
    prompt = get_prompt_by_id(db, prompt_id)
    if not prompt:
        return False
    rec_count = count_prompt_recordings(db, prompt_id)
    if rec_count > 0:
        raise ValueError(
            f"Impossible de supprimer ce prompt : {rec_count} enregistrement(s) y sont déjà rattachés. Désactivez-le plutôt."
        )
    db.delete(prompt)
    db.commit()
    return True


def get_next_prompt_for_session(
    db: Session,
    session_id: UUID,
    exclude_ids: Optional[Set[UUID]] = None,
) -> Dict[str, Any]:
    """
    WAXAL-inspired stimulus rotation:
      - Never repeats a prompt already recorded by the same speaker.
      - Matches session target_task (image elicitation first for ASR, scripted sentences first for TTS).
      - Balances topic coverage by favoring least-used topics in the current session.
    """
    sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not sess:
        raise ValueError("Session non trouvée")

    target_task = sess.target_task or "asr"

    # Prompts already recorded by this speaker across all sessions
    seen_rows = (
        db.query(Recording.prompt_id)
        .join(SessionModel, Recording.session_id == SessionModel.id)
        .filter(SessionModel.speaker_id == sess.speaker_id, Recording.prompt_id.isnot(None))
        .all()
    )
    seen_prompt_ids: Set[UUID] = {row[0] for row in seen_rows if row[0] is not None}

    # Recordings completed in this session & topic distribution
    session_recs = (
        db.query(Recording)
        .filter(Recording.session_id == session_id)
        .all()
    )
    completed_in_session = len(session_recs)

    topic_counts: Counter = Counter()
    for rec in session_recs:
        if rec.prompt and rec.prompt.topic:
            topic_counts[rec.prompt.topic.strip().lower()] += 1

    active_prompts = db.query(Prompt).filter(Prompt.active == True).all()

    skipped = set(exclude_ids or set())
    unseen = [p for p in active_prompts if p.id not in seen_prompt_ids and p.id not in skipped]

    if not unseen:
        return {
            "prompt": None,
            "completed_in_session": completed_in_session,
            "remaining_for_speaker": 0,
            "target_task": target_task,
        }

    def priority_key(p: Prompt):
        topic_key = (p.topic or "").strip().lower()
        topic_usage = topic_counts.get(topic_key, 0) if topic_key else 0

        if target_task == "tts":
            type_rank = 0 if p.prompt_type == "sentence" else 1
            media_rank = 0
        else:
            # ASR favors visual image elicitation (with actual media) first, then spontaneous prompts
            if p.prompt_type == "image" and p.media_object_key:
                type_rank = 0
                media_rank = 0
            elif p.prompt_type == "image":
                type_rank = 1
                media_rank = 1
            elif p.prompt_type in {"question", "topic", "story", "free_speech"}:
                type_rank = 2
                media_rank = 1
            else:
                type_rank = 3
                media_rank = 1

        return (type_rank, media_rank, topic_usage, p.prompt_code)

    unseen.sort(key=priority_key)
    chosen = unseen[0]

    return {
        "prompt": chosen,
        "completed_in_session": completed_in_session,
        "remaining_for_speaker": len(unseen),
        "target_task": target_task,
    }
