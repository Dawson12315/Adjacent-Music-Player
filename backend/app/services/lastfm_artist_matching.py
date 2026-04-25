from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.utils.artist_normalization import normalize_artist_name


def build_local_artist_lookup(db: Session) -> Dict[str, List[str]]:
    lookup: Dict[str, List[str]] = {}

    def add_artist(artist_name: str | None):
        if not artist_name:
            return

        artist_name = artist_name.strip()
        if not artist_name:
            return

        normalized_key = normalize_artist_name(artist_name)
        if not normalized_key:
            return

        lookup.setdefault(normalized_key, [])

        if artist_name not in lookup[normalized_key]:
            lookup[normalized_key].append(artist_name)

    track_artist_rows = (
        db.query(Track.artist)
        .filter(Track.artist.isnot(None))
        .all()
    )

    for row in track_artist_rows:
        add_artist(row[0])

    track_credit_rows = (
        db.query(TrackArtist.artist_name)
        .filter(TrackArtist.artist_name.isnot(None))
        .all()
    )

    for row in track_credit_rows:
        add_artist(row[0])

    return lookup


def match_similar_artist_to_local_artists(
    db: Session,
    similar_artist_name: str,
) -> Dict:
    normalized_key = normalize_artist_name(similar_artist_name)

    if not similar_artist_name or not normalized_key:
        return {
            "success": False,
            "reason": "invalid_artist_name",
            "input_artist_name": similar_artist_name,
            "normalized_key": normalized_key,
            "matched_artists": [],
        }

    lookup = build_local_artist_lookup(db)
    matched_artists = lookup.get(normalized_key, [])

    return {
        "success": True,
        "reason": "ok",
        "input_artist_name": similar_artist_name,
        "normalized_key": normalized_key,
        "matched_artists": matched_artists,
        "match_count": len(matched_artists),
    }