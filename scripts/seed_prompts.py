"""
Idempotently seed ALORA PostgreSQL + MinIO with:
  1. All image prompts from seed_data/prompts_catalog.csv (re-downloading from thumb_url if local image missing)
  2. Starter Susu sentences for TTS / read-speech testing.

Usage:
    PYTHONPATH=. uv run python scripts/seed_prompts.py
"""

import csv
from pathlib import Path
from typing import List, Dict

import httpx

from app.core.database import SessionLocal
from app.models import Prompt
from app.schemas.prompt import PromptCreate
from app.services import prompt as prompt_service
from app.services.storage import storage_service

HEADERS = {
    "User-Agent": "ALORA-Research-Corpus/0.4 (https://github.com/MRTDS224/ALORA; research corpus)"
}

STARTER_TTS_SENTENCES: List[Dict[str, str]] = [
    {
        "title": "Salutation du matin",
        "content": "I kɛna, tanante a mu na.",
        "description": "Bonjour, il n'y a pas de mal (tout va bien).",
        "topic": "Salutations",
    },
    {
        "title": "Origine Kindia",
        "content": "N keli Kindia, n xili na ALORA.",
        "description": "Je viens de Kindia, je m'appelle ALORA.",
        "topic": "Présentation",
    },
    {
        "title": "Aller au marché",
        "content": "N na sigafe makiti to.",
        "description": "Je vais au marché aujourd'hui.",
        "topic": "Marché & commerce",
    },
    {
        "title": "Demander des nouvelles",
        "content": "I xa denbaya tanante na?",
        "description": "Est-ce que ta famille va bien ?",
        "topic": "Vie quotidienne & famille",
    },
    {
        "title": "Préparer le riz",
        "content": "N nga na maale sɔɔfe xɔnyi ma.",
        "description": "Ma mère prépare le riz à la cuisine.",
        "topic": "Cuisine & alimentation",
    },
    {
        "title": "La pluie arrive",
        "content": "Tule na fafe to kɔɛra.",
        "description": "La pluie arrive cet après-midi.",
        "topic": "Nature & météo",
    },
    {
        "title": "Les enfants à l'école",
        "content": "Dimɛdie na sigafe karandɛ to.",
        "description": "Les enfants vont à l'école aujourd'hui.",
        "topic": "École & apprentissage",
    },
    {
        "title": "Prendre la route de Conakry",
        "content": "Won na sigafe Konakiri tina.",
        "description": "Nous partons à Conakry demain.",
        "topic": "Transport & déplacements",
    },
    {
        "title": "Remerciement",
        "content": "I nu wali, Ala xa baraka sa.",
        "description": "Merci beaucoup, que Dieu te bénisse.",
        "topic": "Salutations",
    },
    {
        "title": "Partage du repas",
        "content": "Wo fa won xa donse don.",
        "description": "Venez manger avec nous.",
        "topic": "Cuisine & alimentation",
    },
]


def seed_all(seed_dir: Path = Path("seed_data")) -> None:
    storage_service.ensure_bucket_exists()
    db = SessionLocal()

    catalog_csv = seed_dir / "prompts_catalog.csv"
    images_dir = seed_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    created_images = 0
    skipped_images = 0
    created_tts = 0
    skipped_tts = 0

    try:
        # 1. Seed Image Prompts from CSV
        if catalog_csv.is_file():
            with catalog_csv.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
                    for row in reader:
                        title = row["title"].strip()
                        existing = (
                            db.query(Prompt)
                            .filter(Prompt.title == title, Prompt.prompt_type == "image")
                            .first()
                        )
                        if existing:
                            skipped_images += 1
                            continue

                        img_path = images_dir / row["image_filename"]
                        img_bytes = None
                        if img_path.is_file():
                            img_bytes = img_path.read_bytes()
                        elif row.get("thumb_url"):
                            try:
                                r = client.get(row["thumb_url"], timeout=25.0)
                                r.raise_for_status()
                                img_bytes = r.content
                                img_path.write_bytes(img_bytes)
                            except Exception as exc:
                                print(f"[WARN] Could not re-download {title}: {exc}")
                                continue

                        if not img_bytes:
                            continue

                        p_in = PromptCreate(
                            prompt_type="image",
                            title=title,
                            content=row["content"].strip(),
                            description=row.get("description", "").strip() or None,
                            topic=row.get("topic", "").strip() or None,
                            difficulty=row.get("difficulty", "easy").strip() or "easy",
                            min_duration_seconds=float(row.get("min_duration_seconds") or 15.0),
                            media_license=row.get("license", "").strip() or None,
                            media_attribution=row.get("attribution", "").strip() or None,
                            active=True,
                        )
                        created = prompt_service.create_prompt(db, p_in)
                        prompt_service.attach_prompt_media(
                            db=db,
                            prompt_id=created.id,
                            image_bytes=img_bytes,
                            content_type=row.get("content_type") or "image/jpeg",
                        )
                        created_images += 1
        else:
            print(f"[WARN] Catalogue introuvable : {catalog_csv}. Exécutez d'abord scripts/fetch_seed_images.py")

        # 2. Seed Starter TTS Susu Sentences
        for item in STARTER_TTS_SENTENCES:
            existing = (
                db.query(Prompt)
                .filter(Prompt.title == item["title"], Prompt.prompt_type == "sentence")
                .first()
            )
            if existing:
                skipped_tts += 1
                continue

            prompt_service.create_prompt(
                db,
                PromptCreate(
                    prompt_type="sentence",
                    title=item["title"],
                    content=item["content"],
                    description=item["description"],
                    topic=item["topic"],
                    difficulty="easy",
                    min_duration_seconds=2.0,
                    language="sus",
                    active=True,
                ),
            )
            created_tts += 1

        print(
            f"[SEED DONE] Images: +{created_images} créés ({skipped_images} déjà présents) | "
            f"Phrases TTS: +{created_tts} créées ({skipped_tts} déjà présentes)"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
