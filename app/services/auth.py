from typing import List, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    SESSION_COOKIE_NAME,
    VALID_ROLES,
    hash_password,
    verify_password,
    verify_token,
)
from app.models import User


class WebAuthRedirect(Exception):
    """Raised on protected HTML pages when the user needs to sign in."""

    def __init__(self, next_url: str = "/dashboard"):
        self.next_url = next_url


class WebForbiddenError(Exception):
    """Raised on protected HTML pages when an authenticated user lacks the required role."""

    def __init__(self, user: User, detail: str = "Accès réservé à un rôle supérieur."):
        self.user = user
        self.detail = detail


def default_home_for_user(user: Optional[User]) -> str:
    """Return the role-appropriate landing page inside the platform."""
    if not user:
        return "/login"
    return "/record" if user.role == "collector" else "/dashboard"


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_id(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def list_users(db: Session) -> List[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def create_user(
    db: Session,
    email: str,
    full_name: str,
    password: str,
    role: str = "collector",
) -> User:
    clean_email = email.strip().lower()
    clean_role = role if role in VALID_ROLES else "collector"
    if get_user_by_email(db, clean_email):
        raise ValueError("Un compte avec cet e-mail existe déjà")

    user = User(
        email=clean_email,
        full_name=full_name.strip(),
        password_hash=hash_password(password),
        role=clean_role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, str(user.password_hash)):
        return None
    return user


def toggle_user_active(db: Session, user_id: UUID) -> Optional[User]:
    user = get_user_by_id(db, user_id)
    if user:
        user.is_active = not user.is_active
        db.commit()
        db.refresh(user)
    return user


def update_user_role(db: Session, user_id: UUID, new_role: str) -> Optional[User]:
    if new_role not in VALID_ROLES:
        return None
    user = get_user_by_id(db, user_id)
    if user:
        user.role = new_role
        db.commit()
        db.refresh(user)
    return user


def ensure_default_admin(db: Session) -> Optional[User]:
    """Idempotently bootstrap the initial admin account from settings if no admin exists."""
    existing_admin = db.query(User).filter(User.role == "admin").first()
    if existing_admin:
        return existing_admin

    existing_by_email = get_user_by_email(db, settings.ADMIN_EMAIL)
    if existing_by_email:
        existing_by_email.role = "admin"
        existing_by_email.is_active = True
        db.commit()
        db.refresh(existing_by_email)
        return existing_by_email

    if not settings.ADMIN_PASSWORD or not settings.ADMIN_PASSWORD.strip():
        print(
            "[ALORA Auth Warning] No admin user exists and ADMIN_PASSWORD is not set. "
            "Set ADMIN_PASSWORD in environment or run scripts/create_admin.py."
        )
        return None

    return create_user(
        db=db,
        email=settings.ADMIN_EMAIL,
        full_name=settings.ADMIN_FULL_NAME,
        password=settings.ADMIN_PASSWORD,
        role="admin",
    )


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
) -> Optional[User]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    payload = verify_token(token)
    if not payload or "uid" not in payload:
        return None
    try:
        uid = UUID(payload["uid"])
    except ValueError:
        return None
    user = get_user_by_id(db, uid)
    if not user or not user.is_active:
        return None
    return user


def require_web_roles(*allowed_roles: str):
    def _dep(
        request: Request,
        user: Optional[User] = Depends(get_current_user_optional),
    ) -> User:
        if not user:
            next_path = request.url.path
            if request.url.query:
                next_path = f"{next_path}?{request.url.query}"
            raise WebAuthRedirect(next_url=next_path)
        if allowed_roles and user.role not in allowed_roles:
            raise WebForbiddenError(
                user=user,
                detail="Accès réservé à un rôle supérieur.",
            )
        return user

    return _dep


def require_api_roles(*allowed_roles: str):
    def _dep(
        user: Optional[User] = Depends(get_current_user_optional),
    ) -> User:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentification requise.",
            )
        if allowed_roles and user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Droits insuffisants pour cette action.",
            )
        return user

    return _dep
