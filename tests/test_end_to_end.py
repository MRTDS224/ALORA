import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.services.storage import storage_service

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_full_corpus_lifecycle():
    # 1. Ensure MinIO bucket exists
    storage_service.ensure_bucket_exists()

    # 2. Create Speaker via API
    speaker_payload = {
        "age_group": "18-25",
        "gender": "female",
        "region": "Kindia",
        "location": "Damakania",
        "native_language": "Susu",
        "consent_status": "granted"
    }
    res = client.post("/api/speakers", json=speaker_payload)
    assert res.status_code == 201
    speaker = res.json()
    assert "SPK_" in speaker["speaker_code"]
    speaker_id = speaker["id"]

    # 3. Create Session via API
    session_payload = {
        "speaker_id": speaker_id,
        "environment": "quiet_room",
        "device": "browser_mic",
        "location": "Kindia Field Station"
    }
    res = client.post("/api/sessions", json=session_payload)
    assert res.status_code == 201
    session_data = res.json()
    assert "SES_" in session_data["session_code"]
    session_id = session_data["id"]

    # 4. Create Prompt via API
    prompt_payload = {
        "title": "E2E Susu Prompt",
        "content": "I mama nfa? Tanu keli Kindia.",
        "prompt_type": "sentence",
        "language": "sus"
    }
    res = client.post("/api/prompts", json=prompt_payload)
    assert res.status_code == 201
    prompt_data = res.json()
    assert "PRM_" in prompt_data["prompt_code"]
    prompt_id = prompt_data["id"]

    # 5. Upload Audio Recording via API
    dummy_wav = b'RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3e\x00\x00\x00\x7d\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00'
    files = {"file": ("test_audio.wav", dummy_wav, "audio/wav")}
    data = {
        "session_id": session_id,
        "prompt_id": prompt_id,
        "duration_seconds": "2.5",
        "sample_rate": "16000",
        "channels": "1"
    }
    res = client.post("/api/recordings", data=data, files=files)
    assert res.status_code == 201
    rec_data = res.json()
    assert "REC_" in rec_data["recording_code"]
    recording_id = rec_data["id"]
    assert rec_data["recording_status"] == "uploaded"

    # 6. Stream Audio back from MinIO
    res = client.get(f"/api/recordings/{recording_id}/stream")
    assert res.status_code == 200
    assert len(res.content) > 0

    # 7. Validate Audio Quality
    val_data = {
        "audio_quality": "good",
        "noise_level": "low",
        "reviewer": "Dr. Diallo",
        "notes": "Excellent acoustic condition"
    }
    res = client.post(f"/api/recordings/{recording_id}/validate", data=val_data)
    assert res.status_code == 200
    updated_rec = res.json()
    assert updated_rec["recording_status"] == "validated"

    # 8. Create Transcription Version 1
    t1_payload = {
        "recording_id": recording_id,
        "transcription_text": "I mama nfa? Tanu keli Kindia.",
        "transcriber": "Linguist A",
        "status": "draft"
    }
    res = client.post("/api/transcriptions", json=t1_payload)
    assert res.status_code == 201
    t1_data = res.json()
    assert t1_data["version"] == 1

    # 9. Create Transcription Version 2 (Accepted)
    t2_payload = {
        "recording_id": recording_id,
        "transcription_text": "I mama nfa? Tan u keli Kindia.",
        "transcriber": "Senior Linguist B",
        "status": "accepted"
    }
    res = client.post("/api/transcriptions", json=t2_payload)
    assert res.status_code == 201
    t2_data = res.json()
    assert t2_data["version"] == 2

    # 10. Test Praat TextGrid Generation
    res = client.get(f"/api/recordings/{recording_id}/textgrid")
    assert res.status_code == 200
    assert "ooTextFile" in res.text
    assert "TextGrid" in res.text

    # 11. Test Corpus ZIP Export
    res = client.get("/api/export/corpus")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert len(res.content) > 100

    # 12. Check Web Interface Routes (HTML 200 OK)
    assert client.get("/").status_code == 200
    assert client.get("/speakers").status_code == 200
    assert client.get("/sessions").status_code == 200
    assert client.get("/prompts").status_code == 200
    assert client.get("/record").status_code == 200
    assert client.get("/recordings").status_code == 200
    assert client.get(f"/recordings/{recording_id}").status_code == 200
    assert client.get("/transcriptions").status_code == 200
    assert client.get(f"/transcriptions/{recording_id}").status_code == 200
