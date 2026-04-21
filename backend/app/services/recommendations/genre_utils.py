from app.models.track import Track


def get_track_genres(track: Track) -> list[str]:
    """
    Returns all genres associated with a track.
    Prefers normalized track_genres relationship,
    falls back to raw track.genre.
    """
    if track.track_genres:
        return [item.genre for item in track.track_genres if item.genre]

    if track.genre:
        return [track.genre]

    return []


def normalize_genre_name(value: str) -> str:
    """
    Normalize genre string for consistent comparison.
    """
    return value.strip().casefold()


def map_genre_to_family(genre: str) -> str:
    """
    Map raw genre → simplified family bucket.

    NOTE:
    This is intentionally simple for now.
    In Phase 4 this becomes a real normalization system.
    """
    normalized = normalize_genre_name(genre)

    if normalized in {"hip-hop", "hip hop", "rap", "trap"}:
        return "hip_hop"

    if normalized in {"dance", "pop"}:
        return "dance_pop"

    if normalized in {"country", "folk", "blues"}:
        return "country"

    return normalized


def get_track_families(track: Track) -> list[str]:
    """
    Convert track genres → unique family buckets.
    """
    families = []

    for genre in get_track_genres(track):
        family = map_genre_to_family(genre)

        if family not in families:
            families.append(family)

    return families