"""
Fetch 60-80 open-licensed (CC0 / CC-BY / CC-BY-SA) West African & Guinean everyday scene images
from the Wikimedia Commons API, download 800px thumbnails to seed_data/images/ (gitignored),
and write the reproducible catalog to seed_data/prompts_catalog.csv (versioned in Git).

Usage:
    uv run python scripts/fetch_seed_images.py --per-topic 6
"""

import argparse
import csv
import html
import re
import time
from pathlib import Path
from typing import Dict, List, Set

import httpx

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": "ALORA-Research-Corpus/0.4 (https://github.com/MRTDS224/ALORA; research corpus)"
}

ALLOWED_LICENSES = ("cc0", "public domain", "cc by", "cc-by")
BLOCKED_TITLE_WORDS = (
    "map", "carte", "flag", "drapeau", "logo", "coat of arms", "blason",
    "diagram", "chart", "stamp", "timbre", "seal", "emblem", "locator",
    "signature", "coin", "banknote", "pdf", "svg", "icon", "poster",
)

# 12 everyday Guinean / West African themes for rich, culturally grounded ASR elicitation
TOPICS: List[Dict[str, str]] = [
    {
        "topic": "Marché & commerce",
        "slug": "marche",
        "queries": "Conakry market Guinea|West Africa fruit vegetable market|African street market stalls",
        "label": "Scène de marché",
    },
    {
        "topic": "Cuisine & alimentation",
        "slug": "cuisine",
        "queries": "West African cooking pot food|Guinea mango banana fruit stall|African outdoor cooking rice",
        "label": "Cuisine et repas",
    },
    {
        "topic": "Transport & déplacements",
        "slug": "transport",
        "queries": "Conakry street taxi traffic Guinea|West Africa motorcycle taxi road|African bus station transport",
        "label": "Transports et déplacements",
    },
    {
        "topic": "Agriculture & pêche",
        "slug": "agriculture",
        "queries": "Guinea fishing boat pirogue|West Africa rice field farming|African farmers harvest field",
        "label": "Agriculture et pêche",
    },
    {
        "topic": "Vie quotidienne & famille",
        "slug": "quotidien",
        "queries": "Guinea village daily life|West Africa children playing courtyard|African women carrying water",
        "label": "Vie quotidienne",
    },
    {
        "topic": "École & apprentissage",
        "slug": "ecole",
        "queries": "Guinea school classroom students|West Africa school children books|African classroom blackboard",
        "label": "À l'école",
    },
    {
        "topic": "Santé & hygiène",
        "slug": "sante",
        "queries": "West Africa health clinic hospital|Africa hand washing water pump|African pharmacy health care",
        "label": "Santé et hygiène",
    },
    {
        "topic": "Métiers & artisanat",
        "slug": "metiers",
        "queries": "African tailor sewing|African artisan craft workshop|West Africa fishing net carpentry|Africa pottery market",
        "label": "Métiers et artisanat",
    },
    {
        "topic": "Nature & météo",
        "slug": "nature",
        "queries": "Guinea landscape river|West Africa tropical forest palm|African waterfall savanna|Guinea beach sunset",
        "label": "Nature et paysages",
    },
    {
        "topic": "Sport & loisirs",
        "slug": "sport",
        "queries": "West Africa football soccer youth|Conakry beach Guinea ocean|Africa children playing football",
        "label": "Sport et loisirs",
    },
    {
        "topic": "Culture & musique",
        "slug": "culture",
        "queries": "Guinea djembe balafon musician|West Africa traditional dance festival|African traditional fabric clothes",
        "label": "Culture et musique",
    },
    {
        "topic": "Ville & village",
        "slug": "ville",
        "queries": "Conakry Guinea street|West Africa village houses|Dakar Abidjan street market|African mosque town",
        "label": "Ville et village",
    },
]


def strip_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def is_clean_photo(title: str, info: dict) -> bool:
    low = title.lower()
    if any(bad in low for bad in BLOCKED_TITLE_WORDS):
        return False
    mime = (info.get("mime") or "").lower()
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        return False
    w = info.get("width") or 0
    h = info.get("height") or 0
    if w < 500 or h < 350:
        return False
    # Avoid extreme panoramas or tall thin strips
    ratio = w / float(h)
    if ratio < 0.55 or ratio > 2.4:
        return False
    ext = info.get("extmetadata") or {}
    lic = strip_html((ext.get("LicenseShortName") or {}).get("value", "")).lower()
    if not any(ok in lic for ok in ALLOWED_LICENSES):
        return False
    return True


def search_commons(client: httpx.Client, query: str, limit: int = 20) -> List[dict]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": "6",  # File: namespace
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": "800",
    }
    resp = client.get(COMMONS_API, params=params, timeout=20.0)
    resp.raise_for_status()
    data = resp.json()
    pages = (data.get("query") or {}).get("pages") or {}
    return list(pages.values())


def fetch_catalog(per_topic: int, output_dir: Path, catalog_csv: Path) -> None:
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    seen_urls: Set[str] = set()
    rows: List[Dict[str, str]] = []

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        for t in TOPICS:
            topic_name = t["topic"]
            slug = t["slug"]
            label = t["label"]
            collected = 0

            for sub_query in t["queries"].split("|"):
                if collected >= per_topic:
                    break
                try:
                    pages = search_commons(client, sub_query.strip(), limit=25)
                except Exception as exc:
                    print(f"[WARN] Search failed for '{sub_query}': {exc}")
                    continue

                for page in pages:
                    if collected >= per_topic:
                        break
                    title = page.get("title", "")
                    infos = page.get("imageinfo") or []
                    if not infos:
                        continue
                    info = infos[0]
                    if not is_clean_photo(title, info):
                        continue

                    thumb_url = info.get("thumburl") or info.get("url")
                    desc_url = info.get("descriptionurl") or thumb_url
                    if not thumb_url or desc_url in seen_urls:
                        continue

                    # Download 800px optimized thumbnail
                    try:
                        img_resp = client.get(thumb_url, timeout=25.0)
                        img_resp.raise_for_status()
                        img_bytes = img_resp.content
                        if len(img_bytes) < 12_000 or len(img_bytes) > 4_500_000:
                            continue
                    except Exception as exc:
                        print(f"[WARN] Download failed for {title}: {exc}")
                        continue

                    ct = (img_resp.headers.get("content-type") or "image/jpeg").split(";")[0].strip().lower()
                    if ct not in {"image/jpeg", "image/png", "image/webp"}:
                        continue
                    ext_name = "jpg" if ct == "image/jpeg" else ("png" if ct == "image/png" else "webp")

                    collected += 1
                    seen_urls.add(desc_url)

                    filename = f"{slug}_{collected:02d}.{ext_name}"
                    (images_dir / filename).write_bytes(img_bytes)

                    extmeta = info.get("extmetadata") or {}
                    lic = strip_html((extmeta.get("LicenseShortName") or {}).get("value", "CC-BY-SA"))
                    artist = strip_html((extmeta.get("Artist") or {}).get("value", "Wikimedia Commons contributor"))[:160]
                    short_desc = strip_html((extmeta.get("ImageDescription") or {}).get("value", ""))[:180]

                    rows.append({
                        "slug": f"{slug}_{collected:02d}",
                        "title": f"{label} #{collected}",
                        "topic": topic_name,
                        "prompt_type": "image",
                        "content": "Racontez en soussou ce que vous voyez sur cette photo.",
                        "description": short_desc or f"Scène du quotidien ({topic_name})",
                        "min_duration_seconds": "15",
                        "difficulty": "easy",
                        "image_filename": filename,
                        "content_type": ct,
                        "thumb_url": thumb_url,
                        "source_url": desc_url,
                        "license": lic,
                        "attribution": f"{artist} (Wikimedia Commons)",
                    })
                    time.sleep(0.35)  # Polite rate limit for Wikimedia API

            time.sleep(0.6)
            print(f"[OK] {topic_name}: {collected}/{per_topic} images téléchargées")

    catalog_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "slug", "title", "topic", "prompt_type", "content", "description",
        "min_duration_seconds", "difficulty", "image_filename", "content_type",
        "thumb_url", "source_url", "license", "attribution",
    ]
    with catalog_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] {len(rows)} images enregistrées dans {images_dir}")
    print(f"[DONE] Catalogue écrit dans {catalog_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch WAXAL-style seed images for ALORA from Wikimedia Commons.")
    parser.add_argument("--per-topic", type=int, default=6, help="Images per topic (12 topics * 6 = 72 images)")
    parser.add_argument("--output-dir", type=Path, default=Path("seed_data"))
    args = parser.parse_args()

    fetch_catalog(
        per_topic=args.per_topic,
        output_dir=args.output_dir,
        catalog_csv=args.output_dir / "prompts_catalog.csv",
    )


if __name__ == "__main__":
    main()
