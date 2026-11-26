"""
Central language registry for ALORA.
Allows the platform to run with Susu ('sus') as the pilot language while staying
cleanly extensible to other under-resourced African languages via ACTIVE_LANGUAGES.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from app.core.config import settings


# All 33 prefectures of Guinea + Conakry (sorted alphabetically), followed by "Autre"
GUINEA_REGIONS: Tuple[str, ...] = (
    "Beyla",
    "Boffa",
    "Boké",
    "Conakry",
    "Coyah",
    "Dabola",
    "Dalaba",
    "Dinguiraye",
    "Dubréka",
    "Faranah",
    "Forécariah",
    "Fria",
    "Gaoual",
    "Guéckédou",
    "Kankan",
    "Kérouané",
    "Kindia",
    "Kissidougou",
    "Koubia",
    "Koundara",
    "Kouroussa",
    "Labé",
    "Lélouma",
    "Lola",
    "Macenta",
    "Mali",
    "Mamou",
    "Mandiana",
    "Nzérékoré",
    "Pita",
    "Siguiri",
    "Télimélé",
    "Tougué",
    "Yomou",
    "Autre",
)

# Languages spoken in Guinea + vehicular languages (sorted alphabetically), followed by "Autre"
NATIVE_LANGUAGES: Tuple[str, ...] = (
    "Anglais",
    "Arabe",
    "Badiaranké",
    "Baga",
    "Bassari",
    "Coniagui",
    "Djalonké",
    "Français",
    "Guerzé (Kpelle)",
    "Kissi",
    "Kono",
    "Kouranko",
    "Landouma",
    "Lele",
    "Limba",
    "Malinké",
    "Manon",
    "Mikiforé",
    "Nalu",
    "Pular",
    "Soussou",
    "Tenda",
    "Toma (Loma)",
    "Autre",
)

AGE_GROUPS: Tuple[str, ...] = ("18-25", "26-35", "36-50", "50+")
GENDERS: Tuple[str, ...] = ("female", "male", "other")
CONSENT_STATUSES: Tuple[str, ...] = ("granted", "pending", "revoked")
ENVIRONMENTS: Tuple[str, ...] = ("quiet_room", "indoor", "outdoor", "noisy")
TARGET_TASKS: Tuple[str, ...] = ("asr", "tts")
DEVICES: Tuple[str, ...] = (
    "smartphone_mic",
    "smartphone_headset",
    "laptop_mic",
    "usb_mic",
    "studio_mic",
    "voice_recorder",
    "other",
)


def normalize_choice(value: Optional[str], allowed: Sequence[str], default: str) -> str:
    """Return value if it matches an allowed choice (exact or case-insensitive), else default."""
    if not value:
        return default
    cleaned = value.strip()
    if cleaned in allowed:
        return cleaned
    lower_map = {item.lower(): item for item in allowed}
    return lower_map.get(cleaned.lower(), default)


def normalize_multi_choice(values: Optional[Sequence[str]], allowed: Sequence[str]) -> Optional[str]:
    """Validate a multi-select list against an allowlist, deduplicate, sort and join by ', '."""
    if not values:
        return None
    lower_map = {item.lower(): item for item in allowed}
    order_index = {item: idx for idx, item in enumerate(allowed)}
    selected: List[str] = []
    seen = set()
    for raw in values:
        if not raw:
            continue
        # Support either individual list entries or comma-separated strings
        for part in str(raw).split(","):
            canon = lower_map.get(part.strip().lower())
            if canon and canon not in seen:
                seen.add(canon)
                selected.append(canon)
    if not selected:
        return None
    selected.sort(key=lambda item: order_index.get(item, 999))
    return ", ".join(selected)


@dataclass(frozen=True)
class LanguageSpec:
    code: str          # ISO 639-3 code (e.g. "sus", "fuf", "emk")
    name: str          # Display name in French (e.g. "Soussou")
    native_name: str   # Endonym (e.g. "Sosoxui")
    country: str       # Primary country/region


SUPPORTED_LANGUAGES: Dict[str, LanguageSpec] = {
    "sus": LanguageSpec(code="sus", name="Soussou", native_name="Sosoxui", country="Guinée"),
    "fuf": LanguageSpec(code="fuf", name="Pular", native_name="Pular", country="Guinée"),
    "emk": LanguageSpec(code="emk", name="Malinké", native_name="Maninkakan", country="Guinée"),
    "kqs": LanguageSpec(code="kqs", name="Kissi", native_name="Kisi", country="Guinée"),
    "kpv": LanguageSpec(code="kpv", name="Guerzé (Kpelle)", native_name="Kpɛlɛɛ", country="Guinée"),
    "tod": LanguageSpec(code="tod", name="Toma (Loma)", native_name="Lɔɔma", country="Guinée"),
}


def get_active_languages() -> List[LanguageSpec]:
    raw = (settings.ACTIVE_LANGUAGES or settings.DEFAULT_LANGUAGE or "sus").strip()
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    active = [SUPPORTED_LANGUAGES[c] for c in codes if c in SUPPORTED_LANGUAGES]
    return active or [SUPPORTED_LANGUAGES["sus"]]


def get_language_spec(code: str) -> LanguageSpec:
    clean = (code or settings.DEFAULT_LANGUAGE or "sus").strip().lower()
    return SUPPORTED_LANGUAGES.get(clean, SUPPORTED_LANGUAGES["sus"])
