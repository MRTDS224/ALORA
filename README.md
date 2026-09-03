# 🌍 ALORA — Automatic Learning for Oral Resource-poor African Languages

**ALORA** est une plateforme scientifique et modulaire dédiée à la collecte, à la validation acoustique, au stockage et à la transcription orthographique de corpus oraux pour les langues africaines peu dotées, avec une première implémentation ciblée sur la langue **Susu (Soso)** de Guinée.

---

## 🎯 Objectifs de la Plateforme

- **Pseudonymisation & Rigueur Scientifique :** Gestion des locuteurs avec respect du consentement et anonymisation via des identifiants uniques (`SPK_xxxxxx`).
- **Architecture Data First :** Séparation stricte entre les métadonnées relationnelles (PostgreSQL 16) et les fichiers binaires audio (MinIO S3).
- **Studio de Collecte Web :** Enregistreur audio temps réel basé sur la Web Audio API navigateur sans dépendance externe.
- **Workflow de Validation Qualité :** Grille d'évaluation acoustique (bruit ambiant, distorsion, clipping) avec processus de validation/rejet.
- **Studio de Transcription Versionné :** Historisation et versionnement auto-incrémenté (`v1`, `v2`, etc.) des transcriptions orthographiques Susu.
- **Tableau de Bord Analytics :** Indicateurs synthétiques en temps réel sur les heures d'enregistrement, les locuteurs et le pipeline de traitement.

---

## 🛠️ Stack Technique

- **Langage & Gestionnaire de Dépendances :** Python 3.12, [`uv`](https://github.com/astral-sh/uv)
- **Framework Web & API :** [FastAPI](https://fastapi.tiangolo.com/), Pydantic v2, Jinja2 Templates
- **Base de Données & ORM :** PostgreSQL 16, [SQLAlchemy 2.0](https://www.sqlalchemy.org/), [Alembic](https://alembic.sqlalchemy.org/)
- **Stockage Objets S3 :** [MinIO](https://min.io/) (Client Python `minio`)
- **Frontend & Audio :** HTML5, Vanilla CSS, JS Web Audio API (enregistreur micro navigateur)
- **Tests Automatises :** `pytest`, `httpx`

---

## 📂 Structure du Projet

```text
ALORA/
├── app/
│   ├── core/           # Configuration (.env), Moteur Database & Sécurité
│   ├── models/         # Modèles ORM SQLAlchemy (8 entités métier)
│   ├── schemas/        # Validation Pydantic v2 (DTOs API)
│   ├── services/       # Couche Métier (CRUD, S3 Storage, FFmpeg, Praat, Export ZIP)
│   ├── routers/        # Enrouteurs API REST et Pages Web Jinja2
│   ├── templates/      # Interface Utilisateur HTML5 (Templates Jinja2)
│   └── main.py         # Point d'entrée de l'application FastAPI
├── static/
│   ├── css/style.css   # System Design CSS Vanilla
│   └── js/recorder.js  # Enregistreur Web Audio API (Micro Browser)
├── tests/              # Suite de tests d'intégration End-to-End (Pytest)
├── docker-compose.yml  # Services PostgreSQL (5434) & MinIO (9000/9001)
├── pyproject.toml      # Dépendances Python gérées par uv
└── pyrightconfig.json  # Configuration d'analyse statique Pyright
```

---

## 🚀 Guide de Démarrage Rapide

### 1. Prérequis
- Python 3.12+
- `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker & Docker Compose

### 2. Installation des Dépendances
```bash
uv sync
```

### 3. Lancer les Infrastructure Docker (PostgreSQL & MinIO)
```bash
docker-compose up -d
```

> **Services accessibles :**
> - **PostgreSQL 16 :** `localhost:5434` (DB: `alora_db`, User: `alora_user`, Pass: `alora_pass`)
> - **MinIO S3 API :** `localhost:9000`
> - **Console Web MinIO :** `http://localhost:9001` (`minioadmin` / `minioadmin`)

### 4. Appliquer les Migrations de Base de Données
```bash
uv run alembic upgrade head
```

### 5. Démarrer le Serveur Web FastAPI
```bash
uv run uvicorn app.main:app --reload --port 8000
```

---

## 🌐 Cartographie des Interfaces Web & API

| Route Web / API | Rôle & Description |
| :--- | :--- |
| **`GET /`** | 📊 **Tableau de bord** (Durée cumulée, statistiques locuteurs, état du pipeline) |
| **`GET /record`** | 🎙️ **Studio de collecte Web** (Capture micro live, chronomètre, prévisualisation & upload) |
| **`GET /recordings`** | 🎧 **Registre des enregistrements** & filtrage par statut |
| **`GET /recordings/{id}`** | 🔍 **Fiche d'évaluation qualité** (Lecteur audio stream MinIO, formulaire validation/rejet) |
| **`GET /transcriptions`** | ✍️ **Module de transcription** orthographique Susu |
| **`GET /transcriptions/{id}`** | 📝 **Studio de transcription** avec historisation des versions (`v1`, `v2`...) |
| **`GET /speakers`** | 🗣️ **Gestion des locuteurs** pseudonymisés & consentement |
| **`GET /sessions`** | 📅 **Sessions de collecte** (environnement, équipement, météo) |
| **`GET /prompts`** | 📜 **Prompts & phrases de référence** en langue Susu |
| **`GET /api/export/corpus`** | 📦 **Exportation Dataset ML (.ZIP)** (Audios 16kHz + metadata CSV + Praat TextGrid + splits train/val/test) |
| **`GET /api/recordings/{id}/textgrid`** | 🏷️ **Export Praat TextGrid** (IntervalTier pour phrases et annotations de mots) |
| **`GET /docs`** | 📖 **Documentation Swagger API interactive** |

---

## 🧪 Exécution des Tests Automatises

Pour valider l'ensemble du cycle de vie du corpus (création du locuteur -> session -> prompt -> enregistrement audio -> upload MinIO -> streaming -> validation -> transcription multi-versions) :

```bash
PYTHONPATH=. uv run pytest -v
```

---

## 📜 Licence & Crédits

Projet développé dans le cadre de la recherche sur le traitement automatique des langues (TAL) et le développement de ressources pour les langues africaines peu dotées.
