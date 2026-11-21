"""
Pytest session isolation for ALORA.

Ensures tests NEVER write to the developer's main PostgreSQL database or MinIO bucket:
  - Uses TEST_DATABASE_URL (CI) or derives an isolated `<db>_test` database on the local Postgres server.
  - Forces STORAGE_BACKEND=local into a temporary directory cleaned up after the test session.
"""

import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from sqlalchemy import create_engine, text


def _read_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _resolve_test_database_url() -> str:
    if os.environ.get("TEST_DATABASE_URL"):
        url = os.environ["TEST_DATABASE_URL"].strip()
        return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url

    env_file = _read_dotenv()
    base_url = os.environ.get("DATABASE_URL") or env_file.get("DATABASE_URL")
    if base_url:
        if base_url.startswith("postgres://"):
            base_url = "postgresql://" + base_url[len("postgres://"):]
        parsed = urlparse(base_url)
        db_name = parsed.path.lstrip("/") or "alora_db"
        test_db = db_name if db_name.endswith("_test") else f"{db_name}_test"
        return urlunparse(parsed._replace(path=f"/{test_db}"))

    user = os.environ.get("POSTGRES_USER") or env_file.get("POSTGRES_USER", "alora_user")
    password = os.environ.get("POSTGRES_PASSWORD") or env_file.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_SERVER") or env_file.get("POSTGRES_SERVER", "localhost")
    port = os.environ.get("POSTGRES_PORT") or env_file.get("POSTGRES_PORT", "5432")
    db_name = os.environ.get("POSTGRES_DB") or env_file.get("POSTGRES_DB", "alora_db")
    test_db = db_name if db_name.endswith("_test") else f"{db_name}_test"
    return f"postgresql://{user}:{password}@{host}:{port}/{test_db}"


# Configure isolated environment BEFORE any `app.*` module is imported
_TMP_STORAGE_DIR = tempfile.mkdtemp(prefix="alora_pytest_storage_")
_TEST_DB_URL = _resolve_test_database_url()

os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = _TMP_STORAGE_DIR


def _ensure_test_database_exists(db_url: str) -> None:
    parsed = urlparse(db_url)
    target_db = parsed.path.lstrip("/")
    if not target_db:
        return
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            ).scalar()
            if not exists:
                safe_ident = target_db.replace('"', '""')
                conn.execute(text(f'CREATE DATABASE "{safe_ident}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def isolated_test_environment():
    """Creates a clean schema on the isolated test database and cleans up temp storage afterward."""
    _ensure_test_database_exists(_TEST_DB_URL)

    from app.core.database import Base, engine
    import app.models  # noqa: F401 — register all ORM models

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        shutil.rmtree(_TMP_STORAGE_DIR, ignore_errors=True)
