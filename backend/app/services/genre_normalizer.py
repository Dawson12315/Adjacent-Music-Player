def normalize_genre(value):
    if not value:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    lowered = cleaned.lower()

    aliases = {
        "pop": "Pop",
        "r&b": "R&B",
        "rnb": "R&B",
        "hip-hop": "Hip-Hop",
        "rap": "Rap",
        "rock": "Rock",
        "country": "Country",
        "indie": "Indie",
        "folk": "Folk",
        "acoustic": "Acoustic",
        "house": "House",
        "ska": "Ska",
        "hardcore": "Hardcore",
        "alternative": "Alternative",
    }

    if lowered in aliases:
        return aliases[lowered]
    return cleaned.title()