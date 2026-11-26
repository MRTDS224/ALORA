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


def test_audit_logs_and_admin_page():
    cred = uuid.uuid4().hex
    adm_email = f"admin_aud_{uuid.uuid4().hex[:6]}@alora.local"
    rev_email = f"rev_aud_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, adm_email, "Admin Audit", cred, role="admin")
        auth_service.create_user(db, rev_email, "Reviewer Audit", cred, role="reviewer")
    finally:
        db.close()

    adm = TestClient(app)
    assert adm.post("/login", data={"email": adm_email, "password": cred}, follow_redirects=False).status_code == 303
    audit_page = adm.get("/admin/audit")
    assert audit_page.status_code == 200
    assert "auth.login_success" in audit_page.text
    assert adm_email in audit_page.text
    assert audit_page.headers.get("x-request-id")

    rev = TestClient(app)
    assert rev.post("/login", data={"email": rev_email, "password": cred}, follow_redirects=False).status_code == 303
    assert rev.get("/admin/audit").status_code == 403


def test_transcription_multi_reviewer_peer_validation():
    cred = uuid.uuid4().hex
    e_a = f"rev_a_{uuid.uuid4().hex[:6]}@alora.local"
    e_b = f"rev_b_{uuid.uuid4().hex[:6]}@alora.local"
    e_c = f"rev_c_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, e_a, "Linguiste A", cred, role="reviewer")
        auth_service.create_user(db, e_b, "Linguiste B", cred, role="reviewer")
        auth_service.create_user(db, e_c, "Linguiste C", cred, role="reviewer")
    finally:
        db.close()

    c_a, c_b, c_c = TestClient(app), TestClient(app), TestClient(app)
    for client, email in ((c_a, e_a), (c_b, e_b), (c_c, e_c)):
        assert client.post("/login", data={"email": email, "password": cred}, follow_redirects=False).status_code == 303

    # Setup speaker + session + recording via Linguiste A
    spk = c_a.post("/api/speakers", json={"age_group": "26-35", "gender": "female", "region": "Kindia"}).json()
    ses = c_a.post("/api/sessions", json={"speaker_id": spk["id"], "target_task": "asr"}).json()
    rec = c_a.post(
        "/api/recordings",
        data={"session_id": ses["id"], "duration_seconds": "3.0"},
        files={"file": ("peer.wav", _make_clean_wav(3.0), "audio/wav")},
    ).json()

    # 1. A creates v1 (always starts as draft)
    v1 = c_a.post(
        "/api/transcriptions",
        json={"recording_id": rec["id"], "transcription_text": "N na sigafe makiti.", "status": "accepted"},
    )
    assert v1.status_code == 201
    v1_data = v1.json()
    assert v1_data["version"] == 1
    assert v1_data["transcription_status"] == "draft"

    # 2. A CANNOT self-approve v1 -> 403
    self_app = c_a.post(f"/api/transcriptions/{v1_data['id']}/review", json={"decision": "approved"})
    assert self_app.status_code == 403

    # 3. B proposes a corrected version -> creates v2 authored by B
    corr = c_b.post(
        f"/api/transcriptions/{v1_data['id']}/review",
        json={
            "decision": "changes_requested",
            "comment": "Orthographe ajustée",
            "corrected_text": "N na sigafe makiti to.",
        },
    )
    assert corr.status_code == 200
    v2_info = corr.json()["created_version"]
    assert v2_info is not None
    assert v2_info["version"] == 2
    assert v2_info["status"] == "draft"

    # 4. B CANNOT self-approve v2 (their own correction) -> 403
    assert c_b.post(f"/api/transcriptions/{v2_info['id']}/review", json={"decision": "approved"}).status_code == 403

    # 5. A approves v2 -> 1/2 -> reviewed
    r1 = c_a.post(f"/api/transcriptions/{v2_info['id']}/review", json={"decision": "approved"})
    assert r1.status_code == 200
    assert r1.json()["approvals_count"] == 1
    assert r1.json()["status"] == "reviewed"

    # 6. A CANNOT vote twice on v2 -> 400
    assert c_a.post(f"/api/transcriptions/{v2_info['id']}/review", json={"decision": "approved"}).status_code == 400

    # 7. C approves v2 -> 2/2 -> accepted automatically!
    r2 = c_c.post(f"/api/transcriptions/{v2_info['id']}/review", json={"decision": "approved"})
    assert r2.status_code == 200
    assert r2.json()["approvals_count"] == 2
    assert r2.json()["status"] == "accepted"


def test_multilang_prompt_rotation_and_language_export():
    cred = uuid.uuid4().hex
    adm_email = f"admin_ml_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, adm_email, "Admin MultiLang", cred, role="admin")
    finally:
        db.close()

    adm = TestClient(app)
    assert adm.post("/login", data={"email": adm_email, "password": cred}, follow_redirects=False).status_code == 303

    # Create a Susu sentence ('sus') and a shared multilingual image ('mul')
    p_sus = adm.post(
        "/api/prompts",
        json={"prompt_type": "sentence", "title": "Phrase Susu Only", "content": "I kɛna", "language": "sus"},
    ).json()
    p_mul = adm.post(
        "/api/prompts",
        json={"prompt_type": "image", "title": "Image Partagée", "content": "Décrivez", "language": "mul"},
    ).json()

    # Create a Pular ('fuf') session -> should see 'mul' image, NEVER 'sus' sentence
    spk = adm.post("/api/speakers", json={"age_group": "18-25", "gender": "male", "region": "Labé", "native_language": "Pular"}).json()
    ses_fuf = adm.post("/api/sessions", json={"speaker_id": spk["id"], "target_task": "tts", "language": "fuf"}).json()
    nxt = adm.get(f"/api/prompts/next?session_id={ses_fuf['id']}")
    assert nxt.status_code == 200
    chosen = nxt.json()["prompt"]
    assert chosen is not None
    assert chosen["id"] != p_sus["id"]
    assert chosen["language"] in {"mul", "fuf"}

    # Language-filtered export endpoint responds 200 with language in filename
    exp = adm.get("/api/export/corpus?language=sus")
    assert exp.status_code == 200
    assert "alora_corpus_sus.zip" in exp.headers.get("content-disposition", "")


def test_bug_report_public_and_staff_and_client_error():
    cred = uuid.uuid4().hex
    adm_email = f"admin_bug_{uuid.uuid4().hex[:6]}@alora.local"
    db = SessionLocal()
    try:
        auth_service.create_user(db, adm_email, "Admin Bug", cred, role="admin")
    finally:
        db.close()

    # 1. Anonymous bug report from /contribuer
    pub = TestClient(app)
    r_pub = pub.post(
        "/api/public/bug-report",
        json={"message": "Le micro ne s'ouvre pas sur Android", "page_url": "/contribuer"},
    )
    assert r_pub.status_code == 201

    # 2. Client JS error beacon
    r_err = pub.post(
        "/api/public/client-error",
        json={"context": "contribute_mic", "error_name": "NotAllowedError", "error_message": "Permission denied", "page_url": "/contribuer"},
    )
    assert r_err.status_code == 202

    # 3. Logged-in staff bug report + verify both appear in /admin/messages
    adm = TestClient(app)
    assert adm.post("/login", data={"email": adm_email, "password": cred}, follow_redirects=False).status_code == 303
    r_staff = adm.post(
        "/api/public/bug-report",
        json={"message": "Bouton de filtre lent sur /prompts", "page_url": "/prompts"},
    )
    assert r_staff.status_code == 201

    inbox = adm.get("/admin/messages")
    assert inbox.status_code == 200
    assert "Bug / Problème" in inbox.text
    assert "Bouton de filtre lent sur /prompts" in inbox.text
    assert "micro ne s&#39;ouvre pas sur Android" in inbox.text
    assert adm_email in inbox.text
