#!/usr/bin/env sh
set -e

echo "[ALORA Entrypoint] Running Alembic migrations..."
uv run --no-sync alembic upgrade head

echo "[ALORA Entrypoint] Launching idempotent prompt seeding in background..."
(PYTHONPATH=. uv run --no-sync python scripts/seed_prompts.py || echo "[ALORA Entrypoint] Seeding warning (non-fatal)") &

echo "[ALORA Entrypoint] Starting Uvicorn on 0.0.0.0:${PORT:-8000}..."
exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
