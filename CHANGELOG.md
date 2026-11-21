# Changelog — ALORA

Historique des principales évolutions de la plateforme **ALORA**.

---

## [0.4.0] — 2026-11-21

### Ajouté
- **Parcours public volontaire (`/contribuer`) :** studio mobile ultra-simple sans compte (onboarding en 2 étapes, cookie signé `alora_contributor`, rotation anti-répétition des photos, jauge visuelle `15 s – 30 s`, plancher dur anti-erreur `2 s`, file hors-ligne IndexedDB).
- **Catalogue de base de 72 images + 10 phrases TTS soussou :** script de récupération Wikimedia Commons (`scripts/fetch_seed_images.py`), catalogue CSV versionné avec licences/attributions (`seed_data/prompts_catalog.csv`) et seeding idempotent (`scripts/seed_prompts.py`).
- **Import multi-images** sur `/prompts` pour les enquêteurs et collaborateurs.
- **Authentification & RBAC :** hachage `scrypt`, cookies `HttpOnly` signés HMAC-SHA256, rôles `collector`, `reviewer`, `admin`, page `/login` (avec bouton afficher/masquer le mot de passe), gestion des comptes (`/admin/users`) et CLI `scripts/create_admin.py`.
- **Section À propos & Contact :** profil de l'équipe INPT Rabat, boutons WhatsApp & e-mail, formulaire de contact intégré (`POST /api/public/contact` avec honeypot & rate-limit) et boîte de réception `/admin/messages`.
- **Documentation mainteneur :** ajout de `ARCHITECTURE.md` (avec schémas UML Mermaid), `CONTRIBUTING.md`, `CHANGELOG.md` et `LICENSE` (MIT + notice CC BY 4.0).

### Modifié & Corrigé
- Liste déroulante standardisée du matériel d'enregistrement dans `/sessions`.
- Menu hamburger responsive sur la page d'accueil mobile (`/`) et contraste du bouton CTA.
- Cache-busting automatique par hash MD5 (`static_url`) sur les CSS/JS et dimensions explicites des SVG inline (fix rendu Firefox).
- **Correction FFmpeg :** écriture dans un fichier temporaire seekable (`tempfile`) au lieu de `pipe:1` pour produire des en-têtes WAV RIFF valides.
- **Calibration QA audio :** affinage de la détection de silence en environnement bruité dans `app/services/audio_qa.py`.

---

## [0.3.0] — 2026-11-21 (Alignement protocole WAXAL)

### Ajouté
- **Vitrine publique (`GET /`)** dédiée aux visiteurs non techniques et chercheurs ; tableau de bord déplacé vers `/dashboard`.
- **Élicitation par images** (stockage MinIO, streaming, rotation par locuteur) et séparation sessions **ASR** vs **TTS**.
- **Consentement oral** enregistrable et réécoutable sur chaque fiche locuteur (`consents/`).
- **Analyse acoustique automatique (`audio_qa.py`) :** durée réelle, SNR estimé (dB), clipping, ratio vocal et drapeaux QA.
- **Mode hors-ligne (`offline_queue.js`)** basé sur IndexedDB dans `/record`.
- **Export ML speaker-disjoint (`export.py`) :** filtrage des audios validés par défaut, partitions `train` / `validation` / `test` sans fuite de locuteur et stratifiées par genre, `export_manifest.json` et `README_CORPUS.md`.

---

## [0.2.0] — 2026-09-03

### Ajouté
- Pipeline de normalisation audio **FFmpeg** (WAV 16 kHz mono PCM 16-bit).
- Générateur **Praat `.TextGrid`** et endpoints de segmentation / annotations de mots (`api_segmentation.py`).
- Export archive `.ZIP` du corpus (`api_export.py`) intégré au tableau de bord.
- Suite de tests end-to-end (`tests/test_end_to_end.py`).

---

## [0.1.0] — 2026-09-03

### Ajouté
- Fondation FastAPI + SQLAlchemy 2.0 + PostgreSQL 16 + Alembic + MinIO.
- Gestion des locuteurs pseudonymisés (`SPK_xxxxxx`), sessions, prompts, enregistrements, annotations qualité et transcriptions versionnées.
- Interface web Jinja2 initiale et studio d'enregistrement navigateur.
