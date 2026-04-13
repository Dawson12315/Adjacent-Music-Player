def normalize_genre(value):
    if not value:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    aliases = {
        "pop": "Pop",
        "r&b": "R&B",
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

    lowered = cleaned.lower()
    return aliases.get(lowered, cleaned)