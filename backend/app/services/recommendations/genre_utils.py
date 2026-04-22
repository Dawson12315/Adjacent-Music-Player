import re

from app.models.track import Track


GENRE_SYNONYMS = {
    "hip-hop": "hip hop",
    "hiphop": "hip hop",
    "hip_hop": "hip hop",
    "rap music": "rap",
    "rnb": "r&b",
    "rhythm and blues": "r&b",
    "dance pop": "dance-pop",
    "dance-pop": "dance-pop",
    "electro house": "electro house",
    "future bass": "future bass",
    "drum and bass": "drum and bass",
    "dnb": "drum and bass",
    "alt rock": "alternative rock",
    "indie rock": "indie rock",
    "pop rock": "pop rock",
    "neo soul": "neo soul",
    "new jack swing": "new jack swing",
    "quiet storm": "quiet storm",
    "americana": "americana",
    "bluegrass": "bluegrass",
    "edm": "edm",
    "electronic": "electronic",
    "electropop": "electropop",
    "synth-pop": "synthpop",
    "synthwave": "synthwave",
    "lo-fi": "lofi",
    "lo fi": "lofi",
}

FAMILY_ALIASES = {
    "hip_hop": {
        "hip hop",
        "rap",
        "trap",
        "drill",
        "grime",
        "boom bap",
        "southern hip hop",
    },
    "dance_electronic": {
        "dance",
        "dance-pop",
        "edm",
        "electronic",
        "electropop",
        "electro",
        "electro house",
        "house",
        "future bass",
        "drum and bass",
        "dubstep",
        "garage",
        "uk garage",
        "2-step",
        "techno",
        "trance",
        "synthwave",
    },
    "rnb_soul": {
        "r&b",
        "soul",
        "neo soul",
        "quiet storm",
        "new jack swing",
        "funk",
    },
    "rock_alt": {
        "rock",
        "alternative",
        "alternative rock",
        "indie",
        "indie rock",
        "pop rock",
        "punk",
        "grunge",
        "metal",
    },
    "pop": {
        "pop",
        "bedroom pop",
        "art pop",
    },
    "country_folk": {
        "country",
        "folk",
        "americana",
        "bluegrass",
        "blues",
    },
    "jazz_blues": {
        "jazz",
        "blues",
        "swing",
        "bebop",
    },
    "ambient_chill": {
        "ambient",
        "chill",
        "chillout",
        "lofi",
        "downtempo",
    },
    "gospel_spiritual": {
        "gospel",
        "spiritual",
    },
}


def get_track_genres(track: Track) -> list[str]:
    """
    Returns all genres associated with a track.
    Prefers normalized track_genres relationship,
    falls back to raw track.genre.
    """
    if track.track_genres:
        seen = set()
        genres: list[str] = []

        for item in track.track_genres:
            if not item.genre:
                continue

            genre = item.genre.strip()
            if not genre:
                continue

            normalized = normalize_genre_name(genre)
            if normalized in seen:
                continue

            seen.add(normalized)
            genres.append(genre)

        if genres:
            return genres

    if track.genre and track.genre.strip():
        return [track.genre.strip()]

    return []


def normalize_genre_name(value: str) -> str:
    """
    Normalize genre string for consistent comparison.
    """
    normalized = value.strip().casefold()
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = GENRE_SYNONYMS.get(normalized, normalized)
    return normalized


def map_genre_to_family(genre: str) -> str:
    """
    Map raw genre -> broader family bucket.
    Falls back to normalized genre when no family alias exists.
    """
    normalized = normalize_genre_name(genre)

    for family, aliases in FAMILY_ALIASES.items():
        if normalized in aliases:
            return family

    return normalized


def get_track_families(track: Track) -> list[str]:
    """
    Convert track genres -> unique family buckets.
    """
    families: list[str] = []
    seen = set()

    for genre in get_track_genres(track):
        family = map_genre_to_family(genre)
        if family in seen:
            continue

        seen.add(family)
        families.append(family)

    return families


def get_track_primary_family(track: Track) -> str | None:
    """
    Best single family for a track, if available.
    """
    families = get_track_families(track)
    if not families:
        return None

    return families[0]