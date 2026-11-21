"""
Create or update an ALORA admin/staff account from the command line.

Usage:
    PYTHONPATH=. uv run python scripts/create_admin.py
    PYTHONPATH=. uv run python scripts/create_admin.py --email user@alora.org --password secret --role collector --name "Enquêteur Kindia"
"""

import argparse

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.services import auth as auth_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update an ALORA user account.")
    parser.add_argument("--email", default=settings.ADMIN_EMAIL)
    parser.add_argument("--password", default=settings.ADMIN_PASSWORD)
    parser.add_argument("--name", default=settings.ADMIN_FULL_NAME)
    parser.add_argument("--role", default="admin", choices=["collector", "reviewer", "admin"])
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = auth_service.get_user_by_email(db, args.email)
        if existing:
            existing.full_name = args.name
            existing.role = args.role
            existing.password_hash = hash_password(args.password)
            existing.is_active = True
            db.commit()
            print(f"[UPDATED] {existing.email} (role={existing.role})")
        else:
            user = auth_service.create_user(
                db=db,
                email=args.email,
                full_name=args.name,
                password=args.password,
                role=args.role,
            )
            print(f"[CREATED] {user.email} (role={user.role})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
