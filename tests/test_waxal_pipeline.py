import array
import io
import json
import math
import uuid
import wave
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from app.services.audio_qa import analyze_wav_bytes
from app.services.export import assign_speaker_disjoint_splits


def _make_wav(
    duration_sec: float,
    sample_rate: int = 16000,
    signal_amp: int = 12000,
    noise_amp: int = 150,
    silence_ratio: float = 0.25,
) -> bytes:
    """Generates a deterministic 16kHz mono 16-bit PCM WAV buffer for testing."""
    n_samples = int(duration_sec * sample_rate)
    silence_samples = int(n_samples * silence_ratio)
    samples = array.array("h")
    for i in range(n_samples):
        # Deterministic pseudo-noise
        noise = int(noise_amp * math.sin(i * 1.73))
        if i < silence_samples:
            val = noise
        else:
            tone = int(signal_amp * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            val = tone + noise
        val = max(-32768, min(32767, val))
        samples.append(val)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_audio_qa_clean_long_asr_image():
    wav_bytes = _make_wav(duration_sec=16.0, signal_amp=14000, noise_amp=100, silence_ratio=0.25)
    qa = analyze_wav_bytes(wav_bytes, target_task="asr", prompt_type="image")
    assert qa.duration_seconds == pytest.approx(16.0, abs=0.05)
    assert qa.sample_rate == 16000
    assert qa.channels == 1
    assert qa.clipping_detected is False
    assert qa.snr_db is not None and qa.snr_db >= 20.0
    assert qa.speech_ratio is not None and qa.speech_ratio > 0.5
    assert qa.flags == []


def test_audio_qa_short_image_flags_too_short():
    wav_bytes = _make_wav(duration_sec=4.0, signal_amp=12000, noise_amp=100, silence_ratio=0.25)
    qa = analyze_wav_bytes(wav_bytes, target_task="asr", prompt_type="image")
    assert "too_short" in qa.flags
    assert "silence_only" not in qa.flags


def test_audio_qa_clipped_signal_detected():
    wav_bytes = _make_wav(duration_sec=3.0, signal_amp=45000, noise_amp=100, silence_ratio=0.2)
    qa = analyze_wav_bytes(wav_bytes, target_task="asr", prompt_type="sentence")
    assert qa.clipping_detected is True
    assert "clipping" in qa.flags


def test_audio_qa_silence_detected():
    wav_bytes = _make_wav(duration_sec=3.0, signal_amp=0, noise_amp=5, silence_ratio=1.0)
    qa = analyze_wav_bytes(wav_bytes, target_task="asr", prompt_type="sentence")
    assert "silence_only" in qa.flags


def test_audio_qa_low_snr_tts_vs_asr():
    # High noise floor (~3500) vs moderate speech (~8000) -> SNR ~7 dB
    wav_bytes = _make_wav(duration_sec=3.0, signal_amp=6000, noise_amp=3000, silence_ratio=0.25)
    qa_tts = analyze_wav_bytes(wav_bytes, target_task="tts", prompt_type="sentence")
    assert "low_snr" in qa_tts.flags


def test_speaker_disjoint_splits_no_leakage():
    """Verify WAXAL ASR_v2 guarantee: no speaker ever appears in more than one split."""
    speakers = [
        SimpleNamespace(id=uuid.uuid4(), speaker_code=f"SPK_{i:06d}", gender="female" if i % 2 == 0 else "male")
        for i in range(1, 11)
    ]
    recordings = []
    for spk in speakers:
        sess = SimpleNamespace(id=uuid.uuid4(), speaker=spk, target_task="asr")
        for _ in range(4):
            recordings.append(SimpleNamespace(id=uuid.uuid4(), session_id=sess.id, session=sess))

    splits, is_disjoint = assign_speaker_disjoint_splits(recordings)
    assert is_disjoint is True
    assert len(splits) == len(recordings)

    # Check zero speaker leakage across splits
    speaker_to_splits = {}
    for rec in recordings:
        spk_id = str(rec.session.speaker.id)
        speaker_to_splits.setdefault(spk_id, set()).add(splits[str(rec.id)])

    for spk_id, assigned_splits in speaker_to_splits.items():
        assert len(assigned_splits) == 1, f"Speaker {spk_id} leaked across {assigned_splits}"

    used_splits = set(splits.values())
    assert {"train", "validation", "test"}.issubset(used_splits)

    train_count = sum(1 for v in splits.values() if v == "train")
    val_count = sum(1 for v in splits.values() if v == "validation")
    test_count = sum(1 for v in splits.values() if v == "test")
    assert train_count >= val_count and train_count >= test_count


def test_speaker_disjoint_small_corpus_stays_in_train():
    spk = SimpleNamespace(id=uuid.uuid4(), speaker_code="SPK_000001", gender="female")
    sess = SimpleNamespace(id=uuid.uuid4(), speaker=spk, target_task="asr")
    recs = [SimpleNamespace(id=uuid.uuid4(), session_id=sess.id, session=sess) for _ in range(5)]

    splits, is_disjoint = assign_speaker_disjoint_splits(recs)
    assert is_disjoint is True
    assert set(splits.values()) == {"train"}


def test_e2e_waxal_image_elicitation_rotation_consent_and_export():
    """End-to-end API test covering image prompts, rotation, oral consent, QA metrics, and validated export."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Create Speaker & upload oral consent audio
    spk_res = client.post("/api/speakers", json={
        "age_group": "26-35",
        "gender": "female",
        "region": "Kindia",
        "native_language": "Susu",
        "consent_status": "pending",
    })
    assert spk_res.status_code == 201
    spk = spk_res.json()
    spk_id = spk["id"]

    consent_wav = _make_wav(duration_sec=2.0, signal_amp=10000, noise_amp=100)
    consent_res = client.post(
        f"/api/speakers/{spk_id}/consent-audio",
        files={"file": ("consent.wav", consent_wav, "audio/wav")},
    )
    assert consent_res.status_code == 200
    assert consent_res.json()["consent_status"] == "granted"
    assert consent_res.json()["consent_audio_object_key"]

    stream_consent = client.get(f"/api/speakers/{spk_id}/consent-audio")
    assert stream_consent.status_code == 200
    assert len(stream_consent.content) > 44

    # 2. Create ASR Session
    ses_res = client.post("/api/sessions", json={
        "speaker_id": spk_id,
        "target_task": "asr",
        "environment": "outdoor",
        "device": "smartphone_browser",
    })
    assert ses_res.status_code == 201
    sess_id = ses_res.json()["id"]
    assert ses_res.json()["target_task"] == "asr"

    # 3. Create Image Prompt + upload PNG media
    # Minimal valid 1x1 PNG bytes
    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    p_res = client.post("/api/prompts", json={
        "title": "Scène marché Kindia",
        "content": "Décrivez librement cette image en soussou.",
        "prompt_type": "image",
        "topic": f"topic_test_{uuid.uuid4().hex[:6]}",
        "language": "sus",
    })
    assert p_res.status_code == 201
    p_id = p_res.json()["id"]
    assert p_res.json()["min_duration_seconds"] == 15.0

    media_res = client.post(
        f"/api/prompts/{p_id}/media",
        files={"file": ("market.png", tiny_png, "image/png")},
    )
    assert media_res.status_code == 200
    assert media_res.json()["media_object_key"]

    media_get = client.get(f"/api/prompts/{p_id}/media")
    assert media_get.status_code == 200
    assert media_get.content == tiny_png

    # 4. Upload short audio for this image prompt -> auto QA flags 'too_short'
    short_wav = _make_wav(duration_sec=3.0, signal_amp=12000, noise_amp=100)
    rec_res = client.post(
        "/api/recordings",
        data={"session_id": sess_id, "prompt_id": p_id, "duration_seconds": "3.0"},
        files={"file": ("take.wav", short_wav, "audio/wav")},
    )
    assert rec_res.status_code == 201
    rec = rec_res.json()
    assert rec["duration_seconds"] == pytest.approx(3.0, abs=0.2)
    assert rec["snr_db"] is not None
    assert "too_short" in (rec["auto_quality_flags"] or "")

    # 5. Rotation API must NOT return the prompt already recorded by this speaker
    rot_res = client.get(f"/api/prompts/next?session_id={sess_id}")
    assert rot_res.status_code == 200
    rot_data = rot_res.json()
    assert rot_data["completed_in_session"] >= 1
    if rot_data["prompt"] is not None:
        assert rot_data["prompt"]["id"] != p_id

    # 6. Reject this recording -> must NOT appear in default validated-only ZIP export
    rej_res = client.post(f"/api/recordings/{rec['id']}/reject", data={"notes": "Trop court"})
    assert rej_res.status_code == 200
    assert rej_res.json()["recording_status"] == "rejected"

    zip_res = client.get("/api/export/corpus")
    assert zip_res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(zip_res.content), "r") as zf:
        names = zf.namelist()
        assert "metadata/export_manifest.json" in names
        assert "metadata/prompts.csv" in names
        assert "README_CORPUS.md" in names
        manifest = json.loads(zf.read("metadata/export_manifest.json").decode("utf-8"))
        assert manifest["license"] == "CC-BY-4.0"
        assert manifest["speaker_disjoint"] is True
        rec_csv = zf.read("metadata/recordings.csv").decode("utf-8")
        assert rec["recording_code"] not in rec_csv

