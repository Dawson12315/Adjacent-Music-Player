import re
import unicodedata
from typing import Optional


def normalize_artist_name(value: Optional[str]) -> str:
    if not value:
        return ""

    normalized = value.strip()
    if not normalized:
        return ""

    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = normalized.casefold()

    normalized = normalized.replace("&", " and ")

    normalized = re.sub(r"[‘’`´]", "'", normalized)
    normalized = re.sub(r"[\.\-_/]+", " ", normalized)
    normalized = re.sub(r"[^\w\s']", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()