import csv
import io
import zipfile
from typing import Tuple
from sqlalchemy.orm import Session

from app.models import Recording, Speaker, Session as SessionModel, Prompt, Transcription
from app.services.storage import storage_service
from app.services.segmentation import generate_praat_textgrid

def export_corpus_zip(db: Session) -> Tuple[bytes, str]:
    """
    Generates a structured ZIP archive containing the complete or validated Susu oral corpus
    with audio files, metadata CSVs, Praat TextGrid annotations, and train/val/test splits.
    Returns (zip_bytes, filename).
    """
    recordings = db.query(Recording).all()
    speakers = db.query(Speaker).all()
    sessions = db.query(SessionModel).all()
    prompts = db.query(Prompt).all()
    transcriptions = db.query(Transcription).all()

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Metadata: speakers.csv
        speaker_buf = io.StringIO()
        spk_writer = csv.writer(speaker_buf)
        spk_writer.writerow(["id", "speaker_code", "age_group", "gender", "region", "location", "native_language", "consent_status"])
        for s in speakers:
            spk_writer.writerow([s.id, s.speaker_code, s.age_group, s.gender, s.region, s.location, s.native_language, s.consent_status])
        zip_file.writestr("metadata/speakers.csv", speaker_buf.getvalue())

        # 2. Metadata: sessions.csv
        session_buf = io.StringIO()
        ses_writer = csv.writer(session_buf)
        ses_writer.writerow(["id", "session_code", "speaker_id", "environment", "device", "location", "collector", "created_at"])
        for s in sessions:
            ses_writer.writerow([s.id, s.session_code, s.speaker_id, s.environment, s.device, s.location, s.collector, s.created_at])
        zip_file.writestr("metadata/sessions.csv", session_buf.getvalue())

        # 3. Metadata: recordings.csv
        rec_buf = io.StringIO()
        rec_writer = csv.writer(rec_buf)
        rec_writer.writerow(["id", "recording_code", "session_id", "prompt_id", "duration_seconds", "sample_rate", "channels", "format", "recording_status", "split"])

        # Determine train/val/test splits
        total = len(recordings)
        val_count = max(1, int(total * 0.1)) if total >= 5 else 0
        test_count = max(1, int(total * 0.1)) if total >= 5 else 0

        for idx, r in enumerate(recordings):
            if idx < val_count:
                split = "validation"
            elif idx < val_count + test_count:
                split = "test"
            else:
                split = "train"

            rec_writer.writerow([r.id, r.recording_code, r.session_id, r.prompt_id, r.duration_seconds, r.sample_rate, r.channels, r.format, r.recording_status, split])

            # Fetch Audio file from MinIO and write to split folder
            try:
                audio_stream = storage_service.get_object_stream(str(r.audio_object_key))
                audio_bytes = audio_stream.read()
                audio_filename = f"audio/{split}/{r.recording_code}.{r.format or 'wav'}"
                zip_file.writestr(audio_filename, audio_bytes)
            except Exception as e:
                print(f"[Export Warning] Failed to include audio {r.recording_code}: {e}")

            # Write Praat TextGrid annotation
            try:
                tg_content = generate_praat_textgrid(db, r.id)
                zip_file.writestr(f"annotations/textgrid/{r.recording_code}.TextGrid", tg_content)
            except Exception as e:
                print(f"[Export Warning] Failed to include TextGrid for {r.recording_code}: {e}")

        zip_file.writestr("metadata/recordings.csv", rec_buf.getvalue())

        # 4. Metadata: transcriptions.csv
        t_buf = io.StringIO()
        t_writer = csv.writer(t_buf)
        t_writer.writerow(["id", "recording_code", "version", "text", "transcriber", "language", "status"])
        for t in transcriptions:
            rec_code = t.recording.recording_code if t.recording else ""
            t_writer.writerow([t.id, rec_code, t.version, t.text, t.transcriber, t.language, t.transcription_status])
        zip_file.writestr("metadata/transcriptions.csv", t_buf.getvalue())

        # 5. README_CORPUS.md
        readme_text = """# ALORA Susu Oral Corpus Export
This archive contains the exported Susu (Soso) oral speech corpus formatted for Machine Learning (ASR/TTS) research.

## Structure
- `audio/train/`, `audio/validation/`, `audio/test/`: Normalized 16kHz WAV audio recordings.
- `metadata/`: CSV files containing speaker demographics, collection session parameters, recording attributes, and orthographic transcriptions.
- `annotations/textgrid/`: Praat .TextGrid interval annotations for sentence and word alignments.
"""
        zip_file.writestr("README_CORPUS.md", readme_text)

    zip_buffer.seek(0)
    return zip_buffer.getvalue(), "alora_susu_corpus_export.zip"
