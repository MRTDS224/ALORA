import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "ALORA"
    APP_ENV: str = "development"
    SECRET_KEY: str = "supersecretkey"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Optional full database URL (used by Render / Neon / Railway / Supabase)
    DATABASE_URL: Optional[str] = None

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "alora_user"
    POSTGRES_PASSWORD: str = "alora_password"
    POSTGRES_DB: str = "alora_db"

    # Storage backend: "minio" (MinIO / S3 / Cloudflare R2) or "local" (disk fallback for demos)
    STORAGE_BACKEND: str = "minio"
    LOCAL_STORAGE_DIR: str = "/tmp/alora-storage"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "alora-storage"
    MINIO_SECURE: bool = False

    # Initial Admin Bootstrap & Auth
    ADMIN_EMAIL: str = "admin@alora.local"
    ADMIN_PASSWORD: str = "alora-admin-2026"
    ADMIN_FULL_NAME: str = "Administrateur ALORA"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
