import re
from typing import Optional, List


def split_artist_names(artist_value: Optional[str]) -> List[str]:
    if not artist_value:
        return []

    raw_value = artist_value.strip()
    if not raw_value:
        return []

    # Split on comma or ampersand with optional surrounding whitespace
    parts = re.split(r"\s*&\s*|\s*,\s*", raw_value)

    cleaned: List[str] = []
    seen: set[str] = set()

    for part in parts:
        name = part.strip()
        if not name:
            continue

        dedupe_key = name.casefold()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        cleaned.append(name)

    return cleaned