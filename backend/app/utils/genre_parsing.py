import re
from typing import List, Optional


def split_genre_names(genre_value: Optional[str]) -> List[str]:
    if not genre_value:
        return []

    raw_value = genre_value.strip()
    if not raw_value:
        return []

    protected = raw_value.replace("R&B", "__RNB__")

    parts = re.split(r"\s*,\s*|\s*/\s*|\s*;\s*|\s+&\s+", protected)

    cleaned: List[str] = []
    seen = set()

    for part in parts:
        name = part.strip().replace("__RNB__", "R&B")
        if not name:
            continue

        dedupe_key = name.casefold()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        cleaned.append(name)

    return cleaned