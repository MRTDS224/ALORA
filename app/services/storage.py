import io
import datetime
from typing import BinaryIO, Optional
from minio import Minio
from minio.error import S3Error
from app.core.config import settings

class StorageService:
    def __init__(self):
        self.endpoint = settings.MINIO_ENDPOINT
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self.secure = settings.MINIO_SECURE

        self._client: Optional[Minio] = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure
            )
        return self._client

    def ensure_bucket_exists(self) -> None:
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

    def upload_file(
        self,
        file_bytes: bytes,
        object_key: str,
        content_type: str = "audio/wav"
    ) -> str:
        self.ensure_bucket_exists()
        file_stream = io.BytesIO(file_bytes)
        file_size = len(file_bytes)

        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_key,
            data=file_stream,
            length=file_size,
            content_type=content_type
        )
        return object_key

    def get_presigned_url(self, object_key: str, expires_hours: int = 24) -> str:
        try:
            return self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                expires=datetime.timedelta(hours=expires_hours)
            )
        except Exception as e:
            print(f"[StorageService Error] Failed to generate presigned URL: {e}")
            return ""

    def get_object_stream(self, object_key: str):
        return self.client.get_object(self.bucket_name, object_key)

storage_service = StorageService()
