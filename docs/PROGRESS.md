# ALORA — Suivi d'Avancement du Projet

**Dernière mise à jour :** 3 septembre 2026

Ce document permet de suivre l'état d'avancement des tâches réalisées et restant à accomplir dans le cadre du projet ALORA, conformément aux directives établies dans `docs/ALORA_AGENT_BRIEF.md`.

---

## 📊 Résumé de la progression

- [x] **Lecture et analyse du brief** (`docs/ALORA_AGENT_BRIEF.md`)
- [x] **Phase 0 : Initialisation & Environnement (`uv` Python 3.12 + Git)**
- [x] **Phase 1 : Infrastructure & Modèles PostgreSQL + Alembic (Priorités 1 & 2)**
- [x] **Phase 2 : FastAPI & Service de Stockage MinIO (Priorités 2 & 3)**
- [ ] **Phase 3 : Gestion des Locuteurs, Sessions et Prompts (Priorité 4)**
- [ ] **Phase 4 : Collecte Audio & Upload Browser (Priorité 5)**
- [ ] **Phase 5 : Interface & API de Validation Audio (Priorité 6)**
- [ ] **Phase 6 : Interface & API de Transcription (Priorité 7)**
- [ ] **Phase 7 : Tableaux de Bord (Dashboard) (Priorité 8)**
- [ ] **Phase 8 : Finitions UI/CSS & Validation Complète (Priorité 9)**

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
- Installation des dépendances majeures : `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `minio`, `jinja2`, `python-multipart`, `pydantic-settings`.

### 3. Infrastructure Docker & Schéma de Base de Données (Phase 1)
- Création du fichier `docker-compose.yml` avec services PostgreSQL 16 (port 5434) et MinIO (ports 9000 & 9001).
- Configuration centralisée des paramètres de l'application dans `app/core/config.py` et moteur SQLAlchemy dans `app/core/database.py`.
- Création des 8 modèles SQLAlchemy (`speakers`, `sessions`, `prompts`, `recordings`, `transcriptions`, `quality_annotations`, `segments`, `word_annotations`).
- Initialisation d'Alembic et exécution de la première migration SQL (`defe874d90ca_initial_schema.py`).

### 4. FastAPI & Service de Stockage MinIO (Phase 2)
- Implémentation du service S3/MinIO (`app/services/storage.py`) gérant la création automatique du bucket `alora-storage` et l'organisation des objets sous `raw/YYYY/MM/DD/REC_code.wav`.
- Structure de l'application FastAPI (`app/main.py`) avec gestion du cycle de vie (lifespan), endpoint de santé (`/health`), fichiers statiques CSS (`static/css/style.css`) et layout Jinja2 (`app/templates/base.html`).

---

## ⏳ Ce qui reste à faire

### 1. Initialisation du projet
- [x] Initialiser le dépôt Git (`git init`).
- [x] Initialiser le projet Python avec `uv` (Python 3.12).
- [x] Créer le fichier `.gitignore` et la structure initiale des dossiers.
- [x] Premier commit Git.

### 2. Infrastructure & Base de données
- [x] Créer `docker-compose.yml` (PostgreSQL 16 + MinIO).
- [x] Configurer la connexion SQLAlchemy dans `app/core/database.py` et les variables d'environnement dans `app/core/config.py`.
- [x] Définir les 8 modèles SQLAlchemy (`speakers`, `sessions`, `prompts`, `recordings`, `transcriptions`, `quality_annotations`, `segments`, `word_annotations`).
- [x] Initialiser Alembic et générer la première migration SQL.
- [x] Commiter l'infrastructure DB.

### 3. API FastAPI & MinIO
- [x] Structurer l'application FastAPI (`app/main.py`).
- [x] Développer le service de stockage S3/MinIO (`app/services/storage.py`) pour la gestion des audios sous `raw/YYYY/MM/DD/REC_xxx.wav`.
- [x] Tester l'interconnexion FastAPI - MinIO - PostgreSQL.
- [x] Commiter la couche API & MinIO.

### 4. Entités Métier (Locuteurs, Sessions, Prompts)
- [ ] Créer les schémas Pydantic et endpoints API CRUD pour Speakers, Sessions, Prompts.
- [ ] Implémenter les templates HTML Jinja2 (`/speakers`, `/sessions`, `/prompts`).
- [ ] Commiter par module (Speakers, Sessions, Prompts).

### 5. Collecte & Upload Audio
- [ ] Créer la page web de collecte `/record` (Enregistreur navigateur Web Audio API, chronomètre, prévisualisation).
- [ ] Endpoint `POST /api/recordings` (upload audio MinIO + enregistrement métadonnées PostgreSQL).
- [ ] Commiter la fonctionnalité de collecte.

### 6. Validation & Qualité Audio
- [ ] Développer la page `/recordings` et `/recordings/{id}` (Lecteur audio, formulaire de notation de qualité).
- [ ] Endpoints de validation/rejet (`POST /api/recordings/{id}/validate`, `POST /api/recordings/{id}/reject`).
- [ ] Commiter la fonctionnalité de validation.

### 7. Transcription & Versionnement
- [ ] Développer la page `/transcriptions/{recording_id}` (Interface de saisie et gestion du versionnement des transcriptions).
- [ ] Endpoints API associés.
- [ ] Commiter la fonctionnalité de transcription.

### 8. Dashboard & Expérience Utilisateur
- [ ] Développer le tableau de bord `/` avec métriques du corpus (nombre de locuteurs, heures d'enregistrement, statut des traitements).
- [ ] Peaufiner le CSS Vanilla pour un usage fluide sur le terrain (tablettes/laptops).
- [ ] Effectuer le test d'intégration de bout en bout ("Definition of Done").
