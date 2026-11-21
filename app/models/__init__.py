import uuid
import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float, BigInteger, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

def generate_uuid():
    return uuid.uuid4()

def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)

class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    speaker_code = Column(String(50), unique=True, nullable=False, index=True)
    age_group = Column(String(20), nullable=True)  # e.g., '18-25', '26-35', '36-50', '50+'
    gender = Column(String(20), nullable=True)     # e.g., 'female', 'male', 'other'
    region = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    native_language = Column(String(50), nullable=True, default="Susu")
    other_languages = Column(String(255), nullable=True)
    consent_status = Column(String(20), nullable=False, default="granted") # granted, pending, revoked
    consent_audio_object_key = Column(String(500), nullable=True) # Optional oral consent recording in MinIO
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    sessions = relationship("Session", back_populates="speaker", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    session_code = Column(String(50), unique=True, nullable=False, index=True)
    speaker_id = Column(UUID(as_uuid=True), ForeignKey("speakers.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    location = Column(String(100), nullable=True)
    environment = Column(String(100), nullable=True) # e.g. indoor, quiet_room, outdoor
    target_task = Column(String(20), nullable=False, default="asr") # asr (field/spontaneous) or tts (studio/scripted)
    device = Column(String(100), nullable=True)      # e.g. browser_mic, smartphone
    collector = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    speaker = relationship("Speaker", back_populates="sessions")
    recordings = relationship("Recording", back_populates="session", cascade="all, delete-orphan")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    prompt_code = Column(String(50), unique=True, nullable=False, index=True)
    prompt_type = Column(String(50), nullable=False, default="sentence") # image, question, topic, sentence, story, free_speech
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    media_object_key = Column(String(500), nullable=True) # Image key in MinIO for visual elicitation
    media_content_type = Column(String(100), nullable=True)
    min_duration_seconds = Column(Float, nullable=True) # Recommended minimum duration (e.g., 15.0s for ASR images)
    language = Column(String(20), nullable=False, default="sus") # Susu
    topic = Column(String(100), nullable=True)
    difficulty = Column(String(20), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    recordings = relationship("Recording", back_populates="prompt")


class Recording(Base):
    __tablename__ = "recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    recording_code = Column(String(50), unique=True, nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True, index=True)
    audio_object_key = Column(String(500), nullable=False) # e.g. raw/2026/09/03/REC_000001.wav
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    format = Column(String(20), nullable=True, default="wav")
    file_size_bytes = Column(BigInteger, nullable=True)
    snr_db = Column(Float, nullable=True)
    peak_amplitude = Column(Float, nullable=True)
    clipping_detected = Column(Boolean, default=False, nullable=False)
    speech_ratio = Column(Float, nullable=True)
    auto_quality_flags = Column(String(255), nullable=True) # comma-separated: too_short,low_snr,clipping,silence_only
    recording_status = Column(String(50), nullable=False, default="uploaded", index=True)
    # Status workflow: uploaded, validating, validated, transcribed, reviewed, accepted, rejected

    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    session = relationship("Session", back_populates="recordings")
    prompt = relationship("Prompt", back_populates="recordings")
    transcriptions = relationship("Transcription", back_populates="recording", cascade="all, delete-orphan")
    quality_annotations = relationship("QualityAnnotation", back_populates="recording", cascade="all, delete-orphan")
    segments = relationship("Segment", back_populates="recording", cascade="all, delete-orphan")
    word_annotations = relationship("WordAnnotation", back_populates="recording", cascade="all, delete-orphan")


class Transcription(Base):
    __tablename__ = "transcriptions"
    __table_args__ = (
        UniqueConstraint("recording_id", "version", name="uq_recording_version"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    language = Column(String(20), nullable=False, default="sus")
    transcription_type = Column(String(50), nullable=False, default="manual") # manual, automatic
    transcription_status = Column(String(50), nullable=False, default="draft") # draft, reviewed, final
    transcriber = Column(String(100), nullable=True)
    reviewer = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    recording = relationship("Recording", back_populates="transcriptions")
    word_annotations = relationship("WordAnnotation", back_populates="transcription")


class QualityAnnotation(Base):
    __tablename__ = "quality_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True)
    audio_quality = Column(String(20), nullable=True)  # good, fair, poor
    noise_level = Column(String(20), nullable=True)    # low, medium, high
    clipping = Column(Boolean, default=False, nullable=False)
    speech_present = Column(Boolean, default=True, nullable=False)
    multiple_speakers = Column(Boolean, default=False, nullable=False)
    reviewer = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    recording = relationship("Recording", back_populates="quality_annotations")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_code = Column(String(50), unique=True, nullable=False, index=True)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    audio_object_key = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)

    recording = relationship("Recording", back_populates="segments")


class WordAnnotation(Base):
    __tablename__ = "word_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id", ondelete="CASCADE"), nullable=False, index=True)
    transcription_id = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="SET NULL"), nullable=True)
    word = Column(String(255), nullable=False)
    start_time = Column(Float, nullable=True)
    end_time = Column(Float, nullable=True)
    normalized_form = Column(String(255), nullable=True)
    annotation_type = Column(String(50), nullable=True) # POS, code_switch, language, etc.
    value = Column(String(255), nullable=True)
    annotator = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc, nullable=False)

    recording = relationship("Recording", back_populates="word_annotations")
    transcription = relationship("Transcription", back_populates="word_annotations")
