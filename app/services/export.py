import csv
import datetime
import io
import json
import zipfile
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Recording, Speaker, Session as SessionModel, Prompt, Transcription
from app.services.storage import storage_service
from app.services.segmentation import generate_praat_textgrid

VALIDATED_EXPORT_STATUSES = {"validated", "transcribed", "reviewed", "accepted"}


def assign_speaker_disjoint_splits(recordings: List[Recording]) -> Tuple[Dict[str, str], bool]:
    """
    Assigns each recording to 'train', 'validation', or 'test' with strict speaker-disjoint
    partitioning (WAXAL ASR_v2 protocol), stratified by speaker gender.

    Returns:
        (recording_id_to_split, is_speaker_disjoint)
    """
    if not recordings:
        return {}, True

    speaker_groups: Dict[str, List[Recording]] = defaultdict(list)
    speaker_meta: Dict[str, Tuple[str, str]] = {}

    for rec in recordings:
        if rec.session and rec.session.speaker:
            spk_key = str(rec.session.speaker.id)
            gender = (rec.session.speaker.gender or "unknown").lower()
            code = rec.session.speaker.speaker_code or spk_key
        else:
            spk_key = f"session:{rec.session_id}"
            gender = "unknown"
            code = spk_key
        speaker_groups[spk_key].append(rec)
        speaker_meta[spk_key] = (gender, code)

    unique_speakers = list(speaker_groups.keys())

    # With fewer than 3 unique speakers, keep all in train to avoid speaker leakage
    if len(unique_speakers) < 3:
        return {str(rec.id): "train" for rec in recordings}, True

    # Sort speakers per gender deterministically by recording count (descending) then code
    by_gender: Dict[str, List[str]] = defaultdict(list)
    for spk_key in unique_speakers:
        gender, _ = speaker_meta[spk_key]
        by_gender[gender].append(spk_key)

    ordered_speakers: List[str] = []
    for gender in sorted(by_gender.keys()):
        by_gender[gender].sort(
            key=lambda k: (-len(speaker_groups[k]), speaker_meta[k][1])
        )

    # Interleave genders so validation/test receive balanced gender representation
    max_bucket = max(len(v) for v in by_gender.values())
    sorted_genders = sorted(by_gender.keys())
    for idx in range(max_bucket):
        for gender in sorted_genders:
            if idx < len(by_gender[gender]):
                ordered_speakers.append(by_gender[gender][idx])

    total_recs = len(recordings)
    target_val = max(1, round(total_recs * 0.1))
    target_test = max(1, round(total_recs * 0.1))

    # Reserve at least 1 speaker for train first (the largest speaker), then fill val/test
    speaker_split: Dict[str, str] = {}
    split_counts = {"train": 0, "validation": 0, "test": 0}
    split_speakers = {"train": 0, "validation": 0, "test": 0}

    # Assign largest speaker to train
    first_spk = ordered_speakers[0]
    speaker_split[first_spk] = "train"
    split_counts["train"] += len(speaker_groups[first_spk])
    split_speakers["train"] += 1

    # Assign remaining speakers, preferring smaller speakers for val/test first so train keeps ~80%
    remaining = ordered_speakers[1:]
    # Process smallest speakers first for val/test slots while preserving gender diversity
    val_candidates = list(reversed(remaining))

    for spk_key in val_candidates:
        rec_count = len(speaker_groups[spk_key])
        if split_speakers["validation"] == 0 or (
            split_counts["validation"] < target_val
            and split_counts["validation"] <= split_counts["test"]
            and (split_counts["train"] + sum(len(speaker_groups[k]) for k in remaining if k not in speaker_split) - rec_count) >= max(1, total_recs // 2)
        ):
            speaker_split[spk_key] = "validation"
            split_counts["validation"] += rec_count
            split_speakers["validation"] += 1
        elif split_speakers["test"] == 0 or (
            split_counts["test"] < target_test
            and (split_counts["train"] + sum(len(speaker_groups[k]) for k in remaining if k not in speaker_split) - rec_count) >= max(1, total_recs // 2)
        ):
            speaker_split[spk_key] = "test"
            split_counts["test"] += rec_count
            split_speakers["test"] += 1
        else:
            speaker_split[spk_key] = "train"
            split_counts["train"] += rec_count
            split_speakers["train"] += 1

    recording_splits: Dict[str, str] = {}
    for spk_key, recs in speaker_groups.items():
        assigned = speaker_split[spk_key]
        for rec in recs:
            recording_splits[str(rec.id)] = assigned

    return recording_splits, True


def export_corpus_zip(
    db: Session,
    include_unvalidated: bool = False,
    target_task: Optional[str] = None,
) -> Tuple[bytes, str]:
    """
    Generates a structured ZIP archive containing the Susu oral corpus formatted
    following WAXAL ASR_v2 best practices:
      - Filters out rejected/unvalidated audio by default
      - Speaker-disjoint train/validation/test splits
      - Complete metadata CSVs, export_manifest.json, Praat TextGrids, and CC-BY-4.0 notice
    """
    rec_query = db.query(Recording)
    if not include_unvalidated:
        rec_query = rec_query.filter(Recording.recording_status.in_(VALIDATED_EXPORT_STATUSES))
    if target_task:
        rec_query = rec_query.join(SessionModel).filter(SessionModel.target_task == target_task)

    recordings = rec_query.order_by(Recording.created_at.asc()).all()

    exported_rec_ids = {r.id for r in recordings}
    exported_session_ids = {r.session_id for r in recordings}
    exported_prompt_ids = {r.prompt_id for r in recordings if r.prompt_id is not None}

    sessions = (
        db.query(SessionModel).filter(SessionModel.id.in_(exported_session_ids)).all()
        if exported_session_ids
        else []
    )
    exported_speaker_ids = {s.speaker_id for s in sessions}
    speakers = (
        db.query(Speaker).filter(Speaker.id.in_(exported_speaker_ids)).all()
        if exported_speaker_ids
        else []
    )
    prompts = (
        db.query(Prompt).filter(Prompt.id.in_(exported_prompt_ids)).all()
        if exported_prompt_ids
        else []
    )
    transcriptions = (
        db.query(Transcription).filter(Transcription.recording_id.in_(exported_rec_ids)).all()
        if exported_rec_ids
        else []
    )

    recording_splits, is_speaker_disjoint = assign_speaker_disjoint_splits(recordings)

    # Manifest tracking
    split_stats = {
        "train": {"recordings": 0, "duration_seconds": 0.0, "speakers": set(), "gender": defaultdict(int)},
        "validation": {"recordings": 0, "duration_seconds": 0.0, "speakers": set(), "gender": defaultdict(int)},
        "test": {"recordings": 0, "duration_seconds": 0.0, "speakers": set(), "gender": defaultdict(int)},
    }

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Metadata: speakers.csv
        speaker_buf = io.StringIO()
        spk_writer = csv.writer(speaker_buf)
        spk_writer.writerow([
            "id", "speaker_code", "age_group", "gender", "region",
            "location", "native_language", "other_languages",
            "consent_status", "has_consent_audio"
        ])
        for s in speakers:
            spk_writer.writerow([
                s.id, s.speaker_code, s.age_group, s.gender, s.region,
                s.location, s.native_language, s.other_languages,
                s.consent_status, bool(s.consent_audio_object_key)
            ])
        zip_file.writestr("metadata/speakers.csv", speaker_buf.getvalue())

        # 2. Metadata: sessions.csv
        session_buf = io.StringIO()
        ses_writer = csv.writer(session_buf)
        ses_writer.writerow([
            "id", "session_code", "speaker_id", "target_task",
            "environment", "device", "location", "collector", "created_at"
        ])
        for s in sessions:
            ses_writer.writerow([
                s.id, s.session_code, s.speaker_id, s.target_task,
                s.environment, s.device, s.location, s.collector, s.created_at
            ])
        zip_file.writestr("metadata/sessions.csv", session_buf.getvalue())

        # 3. Metadata: prompts.csv
        prompt_buf = io.StringIO()
        prm_writer = csv.writer(prompt_buf)
        prm_writer.writerow([
            "id", "prompt_code", "prompt_type", "title", "content",
            "description", "topic", "difficulty", "language",
            "min_duration_seconds", "has_media"
        ])
        for p in prompts:
            prm_writer.writerow([
                p.id, p.prompt_code, p.prompt_type, p.title, p.content,
                p.description, p.topic, p.difficulty, p.language,
                p.min_duration_seconds, bool(p.media_object_key)
            ])
        zip_file.writestr("metadata/prompts.csv", prompt_buf.getvalue())

        # 4. Metadata: recordings.csv + Audio files + TextGrids
        rec_buf = io.StringIO()
        rec_writer = csv.writer(rec_buf)
        rec_writer.writerow([
            "id", "recording_code", "session_id", "speaker_code", "target_task",
            "prompt_id", "duration_seconds", "sample_rate", "channels", "format",
            "snr_db", "peak_amplitude", "clipping_detected", "speech_ratio",
            "auto_quality_flags", "recording_status", "split"
        ])

        for r in recordings:
            split = recording_splits.get(str(r.id), "train")
            speaker_code = r.session.speaker.speaker_code if (r.session and r.session.speaker) else ""
            speaker_gender = (r.session.speaker.gender or "unknown") if (r.session and r.session.speaker) else "unknown"
            sess_task = r.session.target_task if r.session else "asr"

            split_stats[split]["recordings"] += 1
            split_stats[split]["duration_seconds"] += float(r.duration_seconds or 0.0)
            if speaker_code:
                if speaker_code not in split_stats[split]["speakers"]:
                    split_stats[split]["speakers"].add(speaker_code)
                    split_stats[split]["gender"][speaker_gender] += 1

            rec_writer.writerow([
                r.id, r.recording_code, r.session_id, speaker_code, sess_task,
                r.prompt_id, r.duration_seconds, r.sample_rate, r.channels, r.format,
                r.snr_db, r.peak_amplitude, r.clipping_detected, r.speech_ratio,
                r.auto_quality_flags or "", r.recording_status, split
            ])

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

        # 5. Metadata: transcriptions.csv
        t_buf = io.StringIO()
        t_writer = csv.writer(t_buf)
        t_writer.writerow(["id", "recording_code", "version", "text", "transcriber", "language", "status"])
        for t in transcriptions:
            rec_code = t.recording.recording_code if t.recording else ""
            t_writer.writerow([t.id, rec_code, t.version, t.text, t.transcriber, t.language, t.transcription_status])
        zip_file.writestr("metadata/transcriptions.csv", t_buf.getvalue())

        # 6. Metadata: export_manifest.json
        total_duration_sec = sum(s["duration_seconds"] for s in split_stats.values())
        manifest = {
            "corpus": "ALORA Susu (sus) Oral Speech Corpus",
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "license": "CC-BY-4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "license_notice": "ALORA © 2026 by Diallo Mamadou Tahirou is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/",
            "filters": {
                "include_unvalidated": include_unvalidated,
                "included_statuses": "all" if include_unvalidated else sorted(VALIDATED_EXPORT_STATUSES),
                "target_task": target_task or "all",
            },
            "speaker_disjoint": is_speaker_disjoint,
            "totals": {
                "recordings": len(recordings),
                "speakers": len(speakers),
                "sessions": len(sessions),
                "prompts": len(prompts),
                "transcriptions": len(transcriptions),
                "duration_seconds": round(total_duration_sec, 2),
                "duration_minutes": round(total_duration_sec / 60.0, 2),
            },
            "splits": {
                name: {
                    "recordings": data["recordings"],
                    "speakers": len(data["speakers"]),
                    "duration_seconds": round(data["duration_seconds"], 2),
                    "gender_distribution": dict(data["gender"]),
                }
                for name, data in split_stats.items()
            },
        }
        zip_file.writestr("metadata/export_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

        # 7. README_CORPUS.md
        readme_text = f"""# ALORA Susu (sus) Oral Speech Corpus Export

This archive contains the exported **Soussou / Susu (`sus`)** oral speech corpus produced by the **ALORA** platform (*Automatic Learning for Oral Resource-poor African Languages*), structured for Speech Recognition (ASR), Text-to-Speech (TTS), and computational linguistics research.

## License
ALORA © 2026 by Diallo Mamadou Tahirou is licensed under CC BY 4.0. To view a copy of this license, visit https://creativecommons.org/licenses/by/4.0/

You are free to share and adapt the material for any purpose, provided you give appropriate credit to the ALORA project and its contributors.

## Split Protocol (WAXAL ASR_v2-inspired)
- **Speaker-disjoint partitioning**: Speakers are never shared across `train`, `validation`, and `test` splits (when >= 3 speakers are present).
- **Status filtering**: `include_unvalidated={include_unvalidated}` (`target_task={target_task or 'all'}`).
- Detailed statistics per split and gender distribution are provided in `metadata/export_manifest.json`.

## Archive Structure
- `audio/train/`, `audio/validation/`, `audio/test/`: Normalized 16 kHz, mono, 16-bit PCM WAV files.
- `metadata/speakers.csv`: Pseudonymized speaker demographics (`SPK_xxxxxx`) and consent flags.
- `metadata/sessions.csv`: Recording environments, devices, and `target_task` (`asr` / `tts`).
- `metadata/prompts.csv`: Textual and visual elicitation prompts.
- `metadata/recordings.csv`: Durations, acoustic QA metrics (`snr_db`, `clipping_detected`, `auto_quality_flags`), statuses, and split assignments.
- `metadata/transcriptions.csv`: Versioned orthographic Susu transcriptions.
- `metadata/export_manifest.json`: Machine-readable summary of corpus metrics and splits.
- `annotations/textgrid/`: Praat `.TextGrid` interval files for phonetic alignment.
"""
        zip_file.writestr("README_CORPUS.md", readme_text)

    zip_buffer.seek(0)
    suffix = f"_{target_task}" if target_task else ""
    filename = f"alora_susu_corpus{suffix}.zip"
    return zip_buffer.getvalue(), filename
