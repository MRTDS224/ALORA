<p align="center">
  <img src="static/img/alora-logo.png" alt="ALORA — Automatic Learning for Oral Resource-poor African Languages" width="440">
</p>

<p align="center">
  <a href="https://github.com/MRTDS224/ALORA/actions/workflows/ci.yml"><img src="https://github.com/MRTDS224/ALORA/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Code-MIT-blue.svg" alt="MIT License"></a>
  <a href="https://creativecommons.org/licenses/by/4.0/"><img src="https://img.shields.io/badge/Corpus-CC%20BY%204.0-lightgrey.svg" alt="CC BY 4.0"></a>
</p>

# 🌍 ALORA — Automatic Learning for Oral Resource-poor African Languages

**ALORA** est une plateforme scientifique open-source et modulaire dédiée à la collecte collaborative, à la validation acoustique, à la transcription versionnée et à l'exportation de corpus oraux pour les langues africaines peu dotées — inaugurée sur la langue **Soussou (`sus`)** parlée en Guinée.

Initié dans le cadre d'un projet de recherche à l'**INPT Rabat** (Maroc), ALORA adopte une approche **Data-First** inspirée des bonnes pratiques du corpus **WAXAL** (*Google Research*, arXiv:2602.02734).

> 🌐 **Plateforme en ligne (Google Cloud Run) :** [https://alora-git-360095154117.europe-west1.run.app/](https://alora-git-360095154117.europe-west1.run.app/)  
> 🎙️ **Participer en soussou (sans compte, mobile) :** [https://alora-git-360095154117.europe-west1.run.app/contribuer](https://alora-git-360095154117.europe-west1.run.app/contribuer)

---

## ✨ Fonctionnalités Clés (v0.4.0)

- **Vitrine Publique & Parcours Volontaire Sans Friction (`/`, `/contribuer`) :** Page d'accueil grand public avec section À propos / Contact (WhatsApp, e-mail, formulaire intégré) et studio mobile ultra-simple sans compte permettant aux locuteurs natifs de décrire des photos en soussou en quelques secondes.
- **Élicitation par Images & Rotation Anti-Biais (WAXAL) :** Catalogue initial de **72 photos libres de droits** (12 thèmes du quotidien guinéen / ouest-africain) + 10 phrases soussou TTS, rotation automatique évitant toute répétition par locuteur, et import multi-images pour les enquêteurs.
- **Collecte Mobile-First & Résilience Hors-Ligne :** Interface responsive vérifiée sur mobile (`360px`), plancher anti-erreur `2 s`, jauge visuelle `15 s – 30 s`, VU-mètre temps réel, compatibilité `MediaRecorder` Chrome/Firefox/Safari et **file d'attente locale IndexedDB** avec synchronisation automatique au retour du réseau.
- **Normalisation FFmpeg & Contrôle Acoustique Automatique :** Transcodage déterministe en **WAV 16 kHz · Mono · PCM 16-bit** (en-têtes RIFF conformes) avec calcul automatique de la durée réelle, du **SNR estimé (dB)**, du ratio d'activité vocale et de la saturation (*clipping*).
- **Éthique, Pseudonymisation & Consentement Oral :** Locuteurs anonymisés (`SPK_xxxxxx`), séparation sessions **ASR** (terrain spontané) / **TTS** (studio scripté), liste standardisée du matériel d'enregistrement, et capture optionnelle du **consentement vocal** pour les participants non alphabétisés.
- **Rôles & Authentification (RBAC) :** Contrôle d'accès sécurisé (`scrypt` + cookies signés `HttpOnly`) distinguant **Public**, **Enquêteur (`collector`)**, **Réviseur/Linguiste (`reviewer`)** et **Administrateur (`admin`)**, avec gestion des comptes (`/admin/users`) et boîte de réception contact (`/admin/messages`).
- **Transcription Versionnée & Praat `.TextGrid` :** Historique immuable des versions (`v1`, `v2`…), statuts (`draft` → `reviewed` → `accepted`) et génération dynamique de fichiers Praat `.TextGrid`.
- **Export ML Speaker-Disjoint (`.ZIP`) :** Filtrage des audios validés par défaut, partitions `train` / `validation` / `test` **strictement disjointes par locuteur** et équilibrées en genre, manifeste JSON (`export_manifest.json`) et notice **CC-BY-4.0**.

---

## 🛠️ Stack Technique

- **Langage & Environnement :** Python 3.12, [`uv`](https://github.com/astral-sh/uv)
- **Backend & Web :** [FastAPI](https://fastapi.tiangolo.com/), Pydantic v2, Jinja2 Templates
- **Base de Données & Migrations :** PostgreSQL 16, [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [Alembic](https://alembic.sqlalchemy.org/)
- **Stockage Objet S3 :** [MinIO](https://min.io/) (audios WAV, images de prompts, consentements vocaux)
- **Traitement Audio :** FFmpeg (`pcm_s16le` 16 kHz mono) + analyse acoustique Python stdlib (`wave`, `array`)
- **Frontend Mobile-First :** HTML5, Vanilla CSS (cache-busting automatique par hash), Web Audio API, IndexedDB
- **Tests Automatisés :** `pytest`, `httpx` (14 tests unitaires & E2E)

---

## 📂 Structure du Projet

```text
ALORA/
├── app/
│   ├── core/               # Configuration (.env), DB SQLAlchemy, sécurité scrypt/HMAC & rate-limit
│   ├── models/             # Modèles ORM (User, Speaker, Session, Prompt, Recording, QA, Transcription, Segment, WordAnnotation, ContactMessage)
│   ├── schemas/            # DTOs Pydantic v2
│   ├── services/           # Logique métier (Auth, Audio QA, FFmpeg, MinIO, Rotation Prompts, Praat, Export Speaker-Disjoint)
│   ├── routers/            # API REST (/api/*, /api/public/*) et pages Web Jinja2
│   ├── templates/          # Interfaces HTML5 (Accueil, /contribuer, Studio, Validation, Transcription, Admin)
│   └── main.py             # Point d'entrée FastAPI & bootstrap admin
├── migrations/             # Migrations Alembic versionnées
├── scripts/
│   ├── fetch_seed_images.py # Téléchargement de 72 photos libres (Wikimedia Commons, 12 thèmes Guinée)
│   ├── seed_prompts.py      # Seeding idempotent PostgreSQL + MinIO (images + phrases TTS)
│   └── create_admin.py      # CLI de création/mise à jour de comptes équipe
├── seed_data/
│   └── prompts_catalog.csv  # Catalogue versionné avec sources & licences (images/ ignoré par Git)
├── static/
│   ├── css/                 # landing.css, contribute.css, style.css
│   └── js/                  # contribute.js, recorder.js, offline_queue.js
├── tests/                   # Suite pytest (E2E, pipeline WAXAL, RBAC & parcours public)
├── docker-compose.yml       # PostgreSQL 16 (5434) & MinIO (9000/9001)
├── pyproject.toml           # Dépendances et métadonnées gérées par uv
├── ARCHITECTURE.md          # Schémas UML, flux, carte « Où modifier quoi ? » & pièges connus
├── CONTRIBUTING.md          # Guide pratique pour les contributeurs (code, linguistique, voix)
├── CHANGELOG.md             # Journal des versions
└── LICENSE                  # Licence MIT (code source)
```

> 📘 **Pour comprendre le code rapidement :** consultez **[ARCHITECTURE.md](ARCHITECTURE.md)** (schémas UML Mermaid, flux complets et table « Où modifier quoi ? ») et **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## 🚀 Guide de Démarrage Rapide

### 1. Prérequis
- Python 3.12+ & [`uv`](https://github.com/astral-sh/uv)
- `ffmpeg` installé sur le système
- Docker & Docker Compose

### 2. Configuration & Dépendances
```bash
cp .env.example .env
uv sync
```

### 3. Lancer PostgreSQL 16 & MinIO
```bash
docker compose up -d
```

> **Services locaux :**
> - **PostgreSQL 16 :** `localhost:5434` (`alora_db` / `alora_user` / `alora_pass`)
> - **MinIO API :** `localhost:9000` · **Console Web :** `http://localhost:9001` (`minioadmin` / `minioadmin`)

### 4. Appliquer les Migrations & Charger le Catalogue Initial (72 images + 10 phrases TTS)
```bash
uv run alembic upgrade head
uv run python scripts/seed_prompts.py
```
*(Si vous souhaitez régénérer ou enrichir le catalogue depuis Wikimedia Commons : `uv run python scripts/fetch_seed_images.py --per-topic 6`.)*

### 5. Créer / Mettre à jour le Compte Administrateur
Un compte admin par défaut est créé automatiquement au démarrage depuis `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Vous pouvez aussi le créer ou le modifier en CLI :
```bash
uv run python scripts/create_admin.py --email admin@alora.local --password votre-mot-de-passe --role admin
```

### 6. Démarrer le Serveur FastAPI
```bash
uv run uvicorn app.main:app --reload --port 8000
```

### 📱 Tester sur Smartphone Android (avec Microphone actif)
Sur mobile, les navigateurs n'autorisent le micro que sur `localhost` ou `HTTPS` :
```bash
# Avec le téléphone branché en USB (Débogage USB activé) :
adb reverse tcp:8000 tcp:8000
# Puis ouvrir http://localhost:8000/contribuer sur le téléphone
```
*(Ou via tunnel HTTPS temporaire : `cloudflared tunnel --url http://127.0.0.1:8000`.)*

### ☁️ Déploiement Cloud (Google Cloud Run / Docker)
ALORA inclut un [Dockerfile](Dockerfile) (Python 3.12 + `uv` + `ffmpeg`), un script d'entrée [scripts/entrypoint.sh](scripts/entrypoint.sh) (migrations Alembic + seeding idempotent) et un Blueprint [render.yaml](render.yaml). En production sur **Google Cloud Platform** :
- **Serveur Web :** Cloud Run (`europe-west1`, HTTPS automatique, port `8080`).
- **Base de données :** Cloud SQL for PostgreSQL via `DATABASE_URL`.
- **Stockage objet :** Google Cloud Storage (`STORAGE_BACKEND=minio`, `MINIO_ENDPOINT=storage.googleapis.com`, clés HMAC, `MINIO_SECURE=true`).

---

## 🌐 Cartographie des Routes & Rôles

| Route Web / API | Accès | Rôle & Description |
| :--- | :---: | :--- |
| **`GET /`** | Public | 🌍 **Page d'accueil** (Présentation ALORA, équipe INPT Rabat, WhatsApp & formulaire de contact) |
| **`GET /contribuer`** | Public | 🎙️ **Parcours volontaire sans compte** (Onboarding 30 s, photos à décrire, jauge `15 s – 30 s`, hors-ligne) |
| **`POST /api/public/*`** | Public | 🔌 **API publique isolée** (onboarding anonyme, rotation d'images, upload audio, contact anti-spam) |
| **`GET /login`** | Public | 🔐 **Connexion équipe** (`collector`, `reviewer`, `admin`) |
| **`GET /record`** | `collector`+ | 🎚️ **Studio enquêteur terrain** (ASR/TTS, rotation WAXAL, diagnostic QA immédiat, IndexedDB) |
| **`GET /speakers`** | `collector`+ | 🗣️ **Locuteurs pseudonymisés** (`SPK_xxxxxx`) & enregistrement du **consentement vocal** |
| **`GET /sessions`** | `collector`+ | 📅 **Sessions de collecte** (ASR vs TTS, environnement, liste fixe de matériel) |
| **`GET /prompts`** | `collector`+ | 🖼️ **Catalogue de stimuli** (images individuelles, import multi-images, scripts TTS) |
| **`GET /dashboard`** | `reviewer`+ | 📊 **Tableau de bord** (parité H/F, sessions ASR/TTS, alertes QA auto, pipeline) |
| **`GET /recordings`** | `reviewer`+ | 🎧 **Validation acoustique** (streaming MinIO, métriques SNR/clipping, validation/rejet) |
| **`GET /transcriptions`** | `reviewer`+ | ✍️ **Studio de transcription** orthographique soussou avec versions (`v1`, `v2`…) |
| **`GET /admin/messages`** | `reviewer`+ | ✉️ **Boîte de réception** des messages envoyés via le formulaire de contact |
| **`GET /admin/users`** | `admin` | 👥 **Gestion des comptes collaborateurs** (création & activation/désactivation) |
| **`GET /admin/audit`** | `admin` | 🛡️ **Journal d'audit immuable** (traçabilité des connexions, validations, exports & modifications) |
| **`GET /api/export/corpus`** | `admin` | 📦 **Export Dataset ML (`.ZIP`)** (validés par défaut, splits speaker-disjoint, TextGrid, `CC-BY-4.0`) |
| **`GET /docs`** | Public | 📖 **Documentation OpenAPI / Swagger interactive** |

---

## 🧪 Tests Automatisés

```bash
uv run pytest -v
```

La suite valide l'intégralité du système (14 tests) : cycle de vie complet, normalisation FFmpeg & métriques acoustiques (`audio_qa`), garantie 0 % de fuite de locuteurs dans l'export, matrice RBAC, parcours public `/contribuer` et formulaire de contact.

---

## 📜 Licences & Crédits

- **Code source de la plateforme :** Licence **MIT** (voir [LICENSE](LICENSE)).
- **Corpus oral, prompts & documentation :**  
  <a href="https://github.com/MRTDS224/ALORA">ALORA</a> © 2026 by <a href="https://www.linkedin.com/in/mamadou-tahirou-diallo-27361032b/">Diallo Mamadou Tahirou</a> is licensed under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a><img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" alt="" style="max-width: 1em;max-height:1em;margin-left: .2em;"><img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" alt="" style="max-width: 1em;max-height:1em;margin-left: .2em;">
- **Images de base (`seed_data/prompts_catalog.csv`) :** Issues de Wikimedia Commons sous licences ouvertes (`CC0`, `CC-BY`, `CC-BY-SA`) avec attribution conservée pour chaque image.

**Initié par :** Diallo Mamadou Tahirou — Élève-Ingénieur Data Science & Machine Learning, **INPT Rabat** ([LinkedIn](https://www.linkedin.com/in/mamadou-tahirou-diallo-27361032b/) · [GitHub](https://github.com/MRTDS224) · `mrtdsow@outlook.com`)  
**Encadrement scientifique :** Prof. Ibn Elhaj Hassan — Enseignant-Chercheur, **INPT Rabat**
