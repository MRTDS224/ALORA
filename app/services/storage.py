import io
import datetime
from pathlib import Path
from typing import Iterator, Optional
from minio import Minio
from app.core.config import settings


class LocalObjectStream:
    """File-backed stream with the same .read() and .stream() interface as MinIO responses."""

    def __init__(self, path: Path):
        self._path = path

    def read(self) -> bytes:
        return self._path.read_bytes()

    def stream(self, amt: int = 32768) -> Iterator[bytes]:
        with self._path.open("rb") as f:
            while True:
                chunk = f.read(amt)
                if not chunk:
                    break
                yield chunk

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


class StorageService:
    def __init__(self):
        self.backend = (settings.STORAGE_BACKEND or "minio").strip().lower()
        self.local_root = Path(settings.LOCAL_STORAGE_DIR).resolve()
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.secure = settings.MINIO_SECURE

        self._client: Optional[Minio] = None

    @property
    def is_local(self) -> bool:
        return self.backend == "local"

    def _local_path(self, object_key: str) -> Path:
        clean_key = object_key.lstrip("/")
        target = (self.local_root / clean_key).resolve()
        if self.local_root not in target.parents and target != self.local_root:
            raise ValueError("Invalid storage object key")
        return target

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
        if self.is_local:
            self.local_root.mkdir(parents=True, exist_ok=True)
            print(f"[StorageService] Local storage directory ready: {self.local_root}")
            return

        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                print(f"[StorageService] Created MinIO bucket: {self.bucket_name}")
            else:
                print(f"[StorageService] Bucket '{self.bucket_name}' already exists.")
        except Exception as e:
            print(f"[StorageService Error] Failed to ensure bucket exists: {e}")

    def generate_object_key(self, recording_code: str, file_extension: str = "wav", prefix: str = "raw") -> str:
        now = datetime.datetime.now(datetime.timezone.utc)
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        return f"{prefix}/{year}/{month}/{day}/{recording_code}.{file_extension.lstrip('.')}"

    def generate_prompt_media_key(self, prompt_code: str, file_extension: str = "jpg") -> str:
        return f"prompts/images/{prompt_code}.{file_extension.lstrip('.')}"

    def generate_consent_audio_key(self, speaker_code: str, file_extension: str = "wav") -> str:
        return f"consents/{speaker_code}_consent.{file_extension.lstrip('.')}"

    def object_exists(self, object_key: str) -> bool:
        if not object_key:
            return False
        if self.is_local:
            return self._local_path(object_key).is_file()
        try:
            self.client.stat_object(self.bucket_name, object_key)
            return True
        except Exception:
            return False

    def upload_file(
        self,
        file_bytes: bytes,
        object_key: str,
        content_type: str = "audio/wav",
    ) -> str:
        if self.is_local:
            target = self._local_path(object_key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file_bytes)
            return object_key

        self.ensure_bucket_exists()
        file_stream = io.BytesIO(file_bytes)
        file_size = len(file_bytes)

        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_key,
            data=file_stream,
            length=file_size,
            content_type=content_type,
        )
        return object_key

    def get_presigned_url(self, object_key: str, expires_hours: int = 24) -> str:
        if self.is_local:
            return ""
        try:
            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                expires=datetime.timedelta(hours=expires_hours),
            )
        except Exception as e:
            print(f"[StorageService Error] Failed to generate presigned URL: {e}")
            return ""

    def get_object_stream(self, object_key: str):
        if self.is_local:
            target = self._local_path(object_key)
            if not target.is_file():
                raise FileNotFoundError(f"Local storage object not found: {object_key}")
            return LocalObjectStream(target)
        return self.client.get_object(self.bucket_name, object_key)


storage_service = StorageService()
