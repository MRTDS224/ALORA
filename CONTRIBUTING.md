# Guide de Contribution — ALORA

Merci de votre intérêt pour **ALORA** (*Automatic Learning for Oral Resource-poor African Languages*) ! Que vous soyez développeur, linguiste, enquêteur terrain ou locuteur natif du soussou, ce guide explique comment contribuer efficacement.

> Avant de modifier le code, consultez **[ARCHITECTURE.md](ARCHITECTURE.md)** : il contient la carte « Où modifier quoi ? », les schémas UML et les pièges déjà résolus.

---

## 1. Trois façons de contribuer

1. **Locuteur natif soussou (aucune compétence technique requise)**
   - Rendez-vous sur `/contribuer` (depuis un smartphone ou un ordinateur) pour décrire des photos du quotidien en soussou (15 à 30 secondes par image).
2. **Linguiste, Enquêteur ou Réviseur**
   - Ajouter des stimuli visuels libres de droits ou des phrases TTS via `/prompts` (compte `collector`+).
   - Valider la qualité audio (`/recordings`) et transcrire en orthographe soussou (`/transcriptions`, compte `reviewer`+).
3. **Développeur / Chercheur IA**
   - Corriger des bugs, améliorer l'ergonomie mobile, enrichir le pipeline QA/export ML ou isoler l'environnement de tests.

---

## 2. Mise en place de l'environnement développeur

```bash
# 1. Cloner & installer les dépendances Python 3.12 via uv
cp .env.example .env
uv sync

# 2. Démarrer PostgreSQL 16 (port 5434) et MinIO (ports 9000/9001)
docker compose up -d

# 3. Appliquer les migrations & charger les 72 images + 10 phrases de base
uv run alembic upgrade head
uv run python scripts/seed_prompts.py

# 4. Lancer l'application en mode rechargement automatique
uv run uvicorn app.main:app --reload --port 8000
```

Pour créer votre compte administrateur local, renseignez `ADMIN_EMAIL` et `ADMIN_PASSWORD` dans votre fichier `.env` local (jamais commité), ou exécutez :
```bash
uv run python scripts/create_admin.py --email admin@alora.local --password "<votre-mot-de-passe>" --role admin
```

---

## 3. Recettes rapides (tâches courantes)

### Ajouter ou modifier une table / colonne SQLAlchemy
1. Modifier le modèle dans `app/models/__init__.py` et les schémas Pydantic correspondants dans `app/schemas/`.
2. Générer une migration Alembic :
   ```bash
   uv run alembic revision --autogenerate -m "description_courte"
   ```
3. Relire le fichier créé dans `migrations/versions/` puis l'appliquer :
   ```bash
   uv run alembic upgrade head
   ```

### Ajouter une route Web ou API protégée par rôle
- Utiliser les dépendances dans `app/services/auth.py` :
  - **API REST** (`401` / `403` JSON) : `Depends(require_api_roles("collector", "reviewer", "admin"))`
  - **Page Web** (redirection vers `/login?next=...`) : `Depends(require_web_roles("reviewer", "admin"))`
- Toute nouvelle ressource statique CSS/JS dans un template Jinja2 doit passer par `{{ static_url('css/mon_fichier.css') }}` pour bénéficier du cache-busting automatique.

### Enrichir le catalogue d'images de base
- Les images de base doivent provenir de sources **libres de droits** (`CC0`, `CC-BY`, `CC-BY-SA`) avec `license` et `attribution` renseignés.
- Pour étendre `seed_data/prompts_catalog.csv` depuis Wikimedia Commons :
  ```bash
  uv run python scripts/fetch_seed_images.py --per-topic 6
  uv run python scripts/seed_prompts.py
  ```
- **Ne jamais commiter `seed_data/images/`** (le dossier est volontairement ignoré dans `.gitignore`).

### Tester sur smartphone Android avec le micro actif
```bash
adb reverse tcp:8000 tcp:8000
# Puis ouvrir http://localhost:8000/contribuer dans Chrome ou Firefox sur le téléphone
```

### Lancer les tests automatisés
```bash
uv run pytest -v
```
> **Attention :** les tests d'intégration utilisent actuellement le PostgreSQL et le MinIO configurés dans `.env`. Évitez de lancer `pytest` contre une base contenant de vraies collectes terrain.

---

## 4. Règles Git & Pull Requests

- **Branches :** créez une branche dédiée depuis `main` :
  - `feat/<nom-court>` (nouvelle fonctionnalité)
  - `fix/<nom-court>` (correction de bug)
  - `docs/<nom-court>` (documentation)
- **Commits conventionnels :** ex. `feat(record): ...`, `fix(audio): ...`, `docs: ...`, `test: ...`.
- **Fichiers à ne JAMAIS commiter :**
  - `.env` (secrets locaux)
  - `seed_data/images/` (binaires d'images téléchargés)
  - `docs/` (notes locales / livrables internes)
  - `postgres_data/`, `minio_data/`
- **Checklist avant PR :**
  - [ ] `uv run pytest -v` passe sans erreur.
  - [ ] Si l'UI a changé : affichage vérifié sur **desktop** et **mobile (`360px`)**.
  - [ ] Si l'architecture, une route ou un flux a changé : mise à jour de `ARCHITECTURE.md` / `README.md`.

---

## 5. Licences des contributions

- **Code source** : licence **MIT** (voir [LICENSE](LICENSE)).
- **Corpus, prompts & documentation** :
  <a href="https://github.com/MRTDS224/ALORA">ALORA</a> © 2026 by <a href="https://www.linkedin.com/in/mamadou-tahirou-diallo-27361032b/">Diallo Mamadou Tahirou</a> is licensed under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a><img src="https://mirrors.creativecommons.org/presskit/icons/cc.svg" alt="" style="max-width: 1em;max-height:1em;margin-left: .2em;"><img src="https://mirrors.creativecommons.org/presskit/icons/by.svg" alt="" style="max-width: 1em;max-height:1em;margin-left: .2em;">
