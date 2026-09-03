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
- Installation des dépendances majeures : `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `minio`, `jinja2`, `python-multipart`, `pydantic-settings`, `pytest`, `httpx`.

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

### 9. Tableau de Bord (Dashboard) (Phase 7)
- Service de calcul des statistiques globales du corpus (`app/services/stats.py`).
- Interface de garde (`/`) avec indicateurs clés (locuteurs, durée cumulée, volumes audio, état du pipeline et activité récente).

### 10. Tests d'Intégration & Recette ("Definition of Done") (Phase 8)
- Rédaction du banc de tests automatisés de bout en bout (`tests/test_end_to_end.py`).
- Validation complète de la "Definition of Done" (PostgreSQL, MinIO S3, API REST, Web App FastAPI Jinja2).

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
- [x] Créer les schémas Pydantic et endpoints API CRUD pour Speakers, Sessions, Prompts.
- [x] Implémenter les templates HTML Jinja2 (`/speakers`, `/sessions`, `/prompts`).
- [x] Commiter par module (Speakers, Sessions, Prompts).

### 5. Collecte & Upload Audio
- [x] Créer la page web de collecte `/record` (Enregistreur navigateur Web Audio API, chronomètre, prévisualisation).
- [x] Endpoint `POST /api/recordings` (upload audio MinIO + enregistrement métadonnées PostgreSQL).
- [x] Commiter la fonctionnalité de collecte.

### 6. Validation & Qualité Audio
- [x] Développer la page `/recordings` et `/recordings/{id}` (Lecteur audio, formulaire de notation de qualité).
- [x] Implémenter le service d'annotation de qualité (`app/services/quality.py`) et les endpoints API `/validate` et `/reject`.
- [x] Commiter l'interface de validation.

### 7. Transcription & Versionnement
- [x] Développer la page `/transcriptions/{recording_id}` (Interface de saisie et gestion du versionnement des transcriptions).
- [x] Implémenter les endpoints API de transcription et la sauvegarde des versions.
- [x] Commiter le module de transcription.

### 8. Dashboard & Expérience Utilisateur
- [x] Développer le tableau de bord `/` avec métriques du corpus (nombre de locuteurs, heures d'enregistrement, statut des traitements).
- [x] Peaufiner le CSS Vanilla pour un usage fluide sur le terrain (tablettes/laptops).
- [x] Effectuer le test d'intégration de bout en bout ("Definition of Done").
