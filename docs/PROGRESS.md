# ALORA — Suivi d'Avancement du Projet

**Dernière mise à jour :** 3 septembre 2026

Ce document permet de suivre l'état d'avancement des tâches réalisées et restant à accomplir dans le cadre du projet ALORA, conformément aux directives établies dans `docs/ALORA_AGENT_BRIEF.md`.

---

## 📊 Résumé de la progression

- [x] **Lecture et analyse du brief** (`docs/ALORA_AGENT_BRIEF.md`)
- [x] **Phase 0 : Initialisation & Environnement (`uv` Python 3.12 + Git)**
- [x] **Phase 1 : Infrastructure & Modèles PostgreSQL + Alembic (Priorités 1 & 2)**
- [x] **Phase 2 : FastAPI & Service de Stockage MinIO (Priorités 2 & 3)**
- [x] **Phase 3 : Gestion des Locuteurs, Sessions et Prompts (Priorité 4)**
- [x] **Phase 4 : Collecte Audio & Upload Browser (Priorité 5)**
- [x] **Phase 5 : Interface & API de Validation Audio (Priorité 6)**
- [x] **Phase 6 : Interface & API de Transcription (Priorité 7)**
- [x] **Phase 7 : Tableaux de Bord (Dashboard) (Priorité 8)**
- [x] **Phase 8 : Finitions UI/CSS & Validation Complète (Priorité 9)**
- [x] **Phase 9 : Prétraitement FFmpeg & Normalisation Audio (WAV 16kHz Mono)**
- [x] **Phase 10 : Module de Segmentation & Export Praat TextGrid (`.TextGrid`)**
- [x] **Phase 11 : Module d'Exportation du Corpus ML/ASR (ZIP & Splits Train/Val/Test)**

---

## ✅ Ce qui a été fait

### 1. Analyse et Cadrage Initial
- Lecture intégrale du cahier des charges et de l'architecture scientifique (`ALORA_AGENT_BRIEF.md`).
- Vérification de la disponibilité de `uv` (v0.12.3 disponible) et Python 3.12.
- Élaboration du plan d'implémentation par phases avec commits atomiques après chaque petite tâche.
- Création du fichier de suivi (`docs/PROGRESS.md`).

### 2. Initialisation de l'Environnement (Phase 0)
- Initialisation du dépôt Git (`main`).
- Initialisation du projet Python 3.12 avec `uv` (`pyproject.toml`, `uv.lock`).
- Configuration de `.gitignore` et `.env.example`.
- Installation des dépendances majeures : `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `minio`, `jinja2`, `python-multipart`, `pydantic-settings`, `pytest`, `httpx`, `ffmpeg-python`.

### 3. Infrastructure Docker & Schéma de Base de Données (Phase 1)
- Création du fichier `docker-compose.yml` avec services PostgreSQL 16 (port 5434) et MinIO (ports 9000 & 9001).
- Configuration centralisée des paramètres de l'application dans `app/core/config.py` et moteur SQLAlchemy dans `app/core/database.py`.
- Création des 8 modèles SQLAlchemy (`speakers`, `sessions`, `prompts`, `recordings`, `transcriptions`, `quality_annotations`, `segments`, `word_annotations`).
- Initialisation d'Alembic et exécution de la première migration SQL (`defe874d90ca_initial_schema.py`).

### 4. FastAPI & Service de Stockage MinIO (Phase 2)
- Implémentation du service S3/MinIO (`app/services/storage.py`) gérant la création automatique du bucket `alora-storage` et l'organisation des objets sous `raw/YYYY/MM/DD/REC_code.wav`.
- Structure de l'application FastAPI (`app/main.py`) avec gestion du cycle de vie (lifespan), endpoint de santé (`/health`), fichiers statiques CSS (`static/css/style.css`) et layout Jinja2 (`app/templates/base.html`).

### 5. Entités Métier — Locuteurs, Sessions, Prompts (Phase 3)
- Création des schémas Pydantic (`app/schemas/speaker.py`, `app/schemas/session.py`, `app/schemas/prompt.py`).
- Implémentation des services CRUD avec génération automatique des codes pseudonymisés (`SPK_xxxxxx`, `SES_xxxxxx`, `PRM_xxxxxx`).
- Création des routes API (`/api/speakers`, `/api/sessions`, `/api/prompts`) et interfaces Web Jinja2 (`/speakers`, `/sessions`, `/prompts`).

### 6. Collecte Audio & Enregistreur Web (Phase 4)
- Création de l'enregistreur Web Audio API navigateur (`static/js/recorder.js`) avec enregistrement live, chronomètre et prévisualisation.
- Implémentation du service d'enregistrement (`app/services/recording.py`) et des endpoints API (`POST /api/recordings` et `GET /api/recordings/{id}/stream`).
- Interface de collecte web (`/record`) permettant de lier session, prompt et fichier audio vers MinIO S3 + métadonnées PostgreSQL.

### 7. Validation & Évaluation de Qualité Audio (Phase 5)
- Schémas Pydantic (`app/schemas/quality.py`) et service d'annotation de qualité (`app/services/quality.py`).
- API de validation et de rejet (`POST /api/recordings/{id}/validate` et `/reject`).
- Interfaces web de listing filtré (`/recordings`) et fiche d'évaluation détaillée (`/recordings/{id}`) avec streaming audio et historique des revues.

### 8. Transcription & Historique des Versions (Phase 6)
- Schémas Pydantic (`app/schemas/transcription.py`) et service de versionnement des transcriptions (`app/services/transcription.py`).
- API REST (`/api/transcriptions`).
- Studio de transcription (`/transcriptions/{recording_id}`) avec synchronisation audio, texte de référence, enregistrement des versions et statuts (`draft`, `reviewed`, `accepted`).

### 9. Tableau de Bord & Exportation (Phase 7 & 11)
- Service de calcul des statistiques globales du corpus (`app/services/stats.py`).
- Interface de garde (`/`) avec indicateurs clés et bouton **"📦 Exporter le Corpus (.ZIP)"**.

### 10. Prétraitement FFmpeg, Segmentation & Export Praat (Phase 9, 10 & 11)
- **Normalisation FFmpeg :** Ré-échantillonnage automatique de tout enregistrement reçu en **WAV 16 kHz Mono PCM 16-bit** (`app/services/recording.py`).
- **Générateur Praat `.TextGrid` :** Exportation des segments et annotations de mots sous forme de fichier d'annotation Praat (`GET /api/recordings/{id}/textgrid`).
- **Exportateur Dataset ML :** Génération à la volée de l'archive ZIP du corpus complet avec découpage en jeux `train` (80%), `validation` (10%), `test` (10%) (`GET /api/export/corpus`).

---

## ⏳ Suivi des Phasing

- [x] Initialisation & Dépôt Git (`main`).
- [x] Infrastructure Docker (PostgreSQL 16 & MinIO S3).
- [x] Schéma SQLAlchemy & Migrations Alembic.
- [x] Métier (Locuteurs, Sessions, Prompts, Audios, Quality, Transcriptions, Segments).
- [x] Pipeline de Prétraitement FFmpeg 16kHz Mono.
- [x] Générateur d'Annotation Linguistique Praat TextGrid.
- [x] Module d'Exportation ZIP (Splits Train / Validation / Test).
- [x] Banc de Tests d'Intégration d'End-to-End validé à 100%.
- [x] Peaufiner le CSS Vanilla pour un usage fluide sur le terrain (tablettes/laptops).
- [x] Effectuer le test d'intégration de bout en bout ("Definition of Done").
