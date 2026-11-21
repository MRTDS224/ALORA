import array
import io
import math
import uuid
import wave

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password, sign_token, verify_token
from app.main import app
from app.services import auth as auth_service


def _make_clean_wav(duration_sec: float = 3.0) -> bytes:
    sr = 16000
    samples = array.array(
        "h",
        [int(12000 * math.sin(2.0 * math.pi * 440.0 * i / sr)) for i in range(int(sr * duration_sec))],
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


def test_password_hashing_and_signed_tokens():
    sample_input = uuid.uuid4().hex
    other_input = uuid.uuid4().hex
    h = hash_password(sample_input)
    assert h.startswith("scrypt$")
    assert verify_password(sample_input, h) is True
    assert verify_password(other_input, h) is False

    token = sign_token({"uid": "abc", "role": "collector"})
    decoded = verify_token(token)
    assert decoded is not None
    assert decoded["uid"] == "abc"
    assert verify_token(token + "tamper") is None


def test_rbac_access_matrix():
    ephemeral_cred = uuid.uuid4().hex
    db = SessionLocal()
    try:
        col_email = f"collector_{uuid.uuid4().hex[:6]}@alora.local"
        rev_email = f"reviewer_{uuid.uuid4().hex[:6]}@alora.local"
        adm_email = f"admin_{uuid.uuid4().hex[:6]}@alora.local"
        auth_service.create_user(db, col_email, "Enquêteur Test", ephemeral_cred, role="collector")
        auth_service.create_user(db, rev_email, "Réviseur Test", ephemeral_cred, role="reviewer")
        auth_service.create_user(db, adm_email, "Admin Test", ephemeral_cred, role="admin")
    finally:
        db.close()

    # 1. Anonymous user: public routes allowed, staff routes redirect or 401
    anon = TestClient(app)
    home_res = anon.get("/")
    assert home_res.status_code == 200
    assert home_res.headers.get("x-content-type-options") == "nosniff"
    assert home_res.headers.get("x-frame-options") == "DENY"
    assert anon.get("/contribuer").status_code == 200
    assert anon.get("/login").status_code == 200
    assert anon.get("/dashboard", follow_redirects=False).status_code == 303
    assert anon.get("/record", follow_redirects=False).status_code == 303
    assert anon.get("/prompts", follow_redirects=False).status_code == 303
    assert anon.get("/admin/users", follow_redirects=False).status_code == 303
    assert anon.get("/api/speakers").status_code == 401
    assert anon.get("/api/export/corpus").status_code == 401

    # 2. Collector: can access /record, /speakers, /sessions, /prompts, NOT /dashboard or /admin/users or export
    col = TestClient(app)
    assert col.post("/login", data={"email": col_email, "password": ephemeral_cred}, follow_redirects=False).status_code == 303
    assert col.get("/record").status_code == 200
    assert col.get("/prompts").status_code == 200
    assert col.get("/speakers").status_code == 200
    assert col.get("/sessions").status_code == 200
    assert col.get("/dashboard").status_code == 403
    assert col.get("/admin/users").status_code == 403
    assert col.get("/api/export/corpus").status_code == 403

    # 3. Reviewer: can access /dashboard, /recordings, /transcriptions, NOT /admin/users or export
    rev = TestClient(app)
    assert rev.post("/login", data={"email": rev_email, "password": ephemeral_cred}, follow_redirects=False).status_code == 303
    assert rev.get("/dashboard").status_code == 200
    assert rev.get("/recordings").status_code == 200
    assert rev.get("/transcriptions").status_code == 200
    assert rev.get("/admin/users").status_code == 403
    assert rev.get("/api/export/corpus").status_code == 403

    # 4. Admin: full access
    adm = TestClient(app)
    assert adm.post(
        "/login",
        data={"email": adm_email, "password": ephemeral_cred},
        follow_redirects=False,
    ).status_code == 303
    assert adm.get("/dashboard").status_code == 200
    assert adm.get("/admin/users").status_code == 200
    assert adm.get("/api/export/corpus").status_code == 200


def test_public_voluntary_contributor_flow():
    """Zero-friction flow: anonymous user on /contribuer creates profile, gets prompt, uploads audio."""
    pub = TestClient(app)

    # Before onboarding -> has_profile = False, next-prompt = 401
    assert pub.get("/api/public/me").json()["has_profile"] is False
    assert pub.get("/api/public/next-prompt").status_code == 401

    # Step 1: Anonymous onboarding (30s form)
    ob = pub.post(
        "/api/public/onboarding",
        json={
            "gender": "male",
            "age_group": "26-35",
            "region": "Conakry",
            "native_language": "Susu",
            "consent_accepted": True,
        },
    )
    assert ob.status_code == 201
    ob_data = ob.json()
    assert ob_data["has_profile"] is True
    assert ob_data["speaker_code"].startswith("SPK_")

    # Step 2: Fetch next rotated prompt
    nxt = pub.get("/api/public/next-prompt")
    assert nxt.status_code == 200
    nxt_data = nxt.json()
    prompt_id = nxt_data["prompt"]["id"] if nxt_data["prompt"] else ""

    # If image prompt has media, anonymous user MUST be able to load the image!
    if nxt_data["prompt"] and nxt_data["prompt"].get("media_object_key"):
        img_res = pub.get(f"/api/prompts/{prompt_id}/media")
        assert img_res.status_code == 200
        assert len(img_res.content) > 0

    # Step 3: Upload recording without staff login
    wav_bytes = _make_clean_wav(3.0)
    up = pub.post(
        "/api/public/recordings",
        data={"prompt_id": prompt_id, "duration_seconds": "3.0"},
        files={"file": ("voix.wav", wav_bytes, "audio/wav")},
    )
    assert up.status_code == 201
    up_data = up.json()
    assert up_data["recording_code"].startswith("REC_")
    assert up_data["completed_count"] == 1

    # Step 4: Public user still CANNOT access staff APIs
    assert pub.get("/api/speakers").status_code == 401
    assert pub.get("/api/export/corpus").status_code == 401

    # Step 5: Reset profile ("Autre personne")
    assert pub.post("/api/public/reset-profile").status_code == 200
    assert pub.get("/api/public/me").json()["has_profile"] is False


def test_public_contact_form_and_admin_inbox():
    pub = TestClient(app)
    res = pub.post(
        "/api/public/contact",
        json={
            "sender_name": "Prof. Linguiste",
            "sender_contact": "linguiste@universite.gn",
            "profile_type": "chercheur",
            "message": "Bonjour, intéressé par le corpus soussou.",
        },
    )
    assert res.status_code == 201
    assert res.json()["status"] == "ok"

    # Admin can view messages on /admin/messages
    ephemeral_cred = uuid.uuid4().hex
    adm_email = f"admin_inbox_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, adm_email, "Admin Inbox Test", ephemeral_cred, role="admin")
    finally:
        db.close()

    adm = TestClient(app)
    adm.post(
        "/login",
        data={"email": adm_email, "password": ephemeral_cred},
        follow_redirects=False,
    )
    inbox = adm.get("/admin/messages")
    assert inbox.status_code == 200
    assert "Prof. Linguiste" in inbox.text
    assert "linguiste@universite.gn" in inbox.text


def test_prompt_view_edit_and_safe_delete():
    cred = uuid.uuid4().hex
    adm_email = f"admin_prm_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, adm_email, "Admin Prompt Edit", cred, role="admin")
    finally:
        db.close()

    adm = TestClient(app)
    assert adm.post("/login", data={"email": adm_email, "password": cred}, follow_redirects=False).status_code == 303

    # Create a prompt via API
    create_res = adm.post(
        "/api/prompts",
        json={
            "prompt_type": "image",
            "title": "Marché initial",
            "content": "Décrivez ce marché.",
            "topic": "Marché",
            "min_duration_seconds": 15.0,
        },
    )
    assert create_res.status_code == 201
    p_id = create_res.json()["id"]

    # 1. View detail page
    detail = adm.get(f"/prompts/{p_id}")
    assert detail.status_code == 200
    assert "Marché initial" in detail.text

    # 2. Edit via Web form
    edit_res = adm.post(
        f"/prompts/{p_id}/edit",
        data={
            "title": "Marché de Madina",
            "content": "Racontez cette scène de marché en soussou.",
            "prompt_type": "image",
            "description": "Note terrain Conakry",
            "topic": "Commerce",
            "difficulty": "medium",
            "min_duration_seconds": "20",
            "media_license": "CC-BY-4.0",
            "media_attribution": "Équipe ALORA",
            "active": "on",
        },
        follow_redirects=False,
    )
    assert edit_res.status_code == 303
    assert f"/prompts/{p_id}?saved=1" in edit_res.headers["location"]

    # 3. Verify updated fields via API & PATCH
    fetched = adm.get(f"/api/prompts/{p_id}").json()
    assert fetched["title"] == "Marché de Madina"
    assert fetched["topic"] == "Commerce"
    assert fetched["min_duration_seconds"] == 20.0

    patch_res = adm.patch(f"/api/prompts/{p_id}", json={"difficulty": "hard"})
    assert patch_res.status_code == 200
    assert patch_res.json()["difficulty"] == "hard"

    # 4. Safe delete succeeds when 0 recordings are attached
    del_res = adm.delete(f"/api/prompts/{p_id}")
    assert del_res.status_code == 204
    assert adm.get(f"/api/prompts/{p_id}").status_code == 404
