import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models import AuditLog, User

logger = get_logger("audit")

_SENSITIVE_KEYS = {"password", "password_hash", "secret", "secret_key", "token", "cookie"}


def _sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[str]:
    if not details:
        return None
    clean: Dict[str, Any] = {}
    for k, v in details.items():
        if any(s in str(k).lower() for s in _SENSITIVE_KEYS):
            continue
        clean[str(k)] = v
    return json.dumps(clean, ensure_ascii=False, default=str)[:2000] if clean else None


def record_audit(
    db: Session,
    action: str,
    actor: Optional[User] = None,
    actor_email: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> Optional[AuditLog]:
    """Append-only audit trail entry persisted in PostgreSQL and mirrored to structured JSON logs."""
    resolved_email = (actor.email if actor else actor_email) or "anonymous"
    resolved_role = actor.role if actor else "public"
    target_id_str = str(target_id) if target_id is not None else None
    details_json = _sanitize_details(details)

    try:
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_email=resolved_email[:255],
            actor_role=resolved_role[:30],
            action=action[:80],
            target_type=target_type[:50] if target_type else None,
            target_id=target_id_str[:100] if target_id_str else None,
            details=details_json,
            ip_address=ip_address[:64] if ip_address else None,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist audit log for %s: %s", action, exc)
        entry = None

    logger.info(
        "audit %s by %s (%s) target=%s:%s",
        action,
        resolved_email,
        resolved_role,
        target_type or "-",
        target_id_str or "-",
        extra={
            "action": action,
            "actor": resolved_email,
            "target": f"{target_type}:{target_id_str}" if target_type else None,
            "ip": ip_address,
        },
    )
    return entry


def list_audit_logs(
    db: Session,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    limit: int = 150,
) -> List[AuditLog]:
    q = db.query(AuditLog)
    if action and action.strip():
        q = q.filter(AuditLog.action == action.strip())
    if actor_email and actor_email.strip():
        q = q.filter(AuditLog.actor_email.ilike(f"%{actor_email.strip()}%"))
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()


def list_distinct_actions(db: Session) -> List[str]:
    rows = db.query(AuditLog.action).distinct().order_by(AuditLog.action.asc()).all()
    return [r[0] for r in rows if r[0]]
