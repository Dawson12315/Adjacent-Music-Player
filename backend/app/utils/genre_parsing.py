import re
from typing import List, Optional

# Genres whose name contains a separator. "Drum & Bass" split into "Drum" and
# "Bass"; only R&B was protected.
PROTECTED_GENRES = (
    "R&B",
    "Rhythm & Blues",
    "Rhythm and Blues",
    "Drum & Bass",
    "Drum and Bass",
    "Rock & Roll",
    "Rock and Roll",
    "Rock 'n' Roll",
    "Country & Western",
    "Folk, World, & Country",
    "Pop/Rock",
    "Hip-Hop/Rap",
    "Hip Hop/Rap",
    "Soul/R&B",
    "Jazz/Blues",
    "Singer/Songwriter",
    "AC/DC",
    "Bass & Beats",
    "Blues & Soul",
    "Hip-Hop & Rap",
)

_PLACEHOLDER = "\u0000{}\u0000"


def split_genre_names(genre_value: Optional[str]) -> List[str]:
    if not genre_value:
        return []

    raw_value = genre_value.strip()
    if not raw_value:
        return []

    # Hide the protected names behind placeholders, split, then put them back.
    protected = raw_value
    restore: dict[str, str] = {}

    for index, name in enumerate(sorted(PROTECTED_GENRES, key=len, reverse=True)):
        pattern = re.compile(re.escape(name), flags=re.IGNORECASE)
        if pattern.search(protected):
            token = _PLACEHOLDER.format(index)
            restore[token] = name
            protected = pattern.sub(token, protected)

    parts = re.split(r"\s*,\s*|\s*/\s*|\s*;\s*|\s+&\s+", protected)

    cleaned: List[str] = []
    seen = set()

    for part in parts:
        name = part.strip()
        for token, original in restore.items():
            name = name.replace(token, original)
        name = name.strip()
        if not name:
            continue

        dedupe_key = name.casefold()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        cleaned.append(name)

    return cleaned
