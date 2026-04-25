from collections import defaultdict
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.lastfm_artist_matching import build_local_artist_lookup
from app.utils.artist_normalization import normalize_artist_name


def resolve_similar_artists_to_local_tracks(
    db: Session,
    source_artist_name: str,
    min_match_score: float = 0.0,
) -> Dict[str, Any]:
    source_artist_key = normalize_artist_name(source_artist_name)

    if not source_artist_name or not source_artist_key:
        return {
            "success": False,
            "reason": "invalid_artist_name",
            "source_artist_name": source_artist_name,
            "source_artist_key": source_artist_key,
            "resolved_artists": [],
            "resolved_tracks": [],
        }

    local_artist_lookup = build_local_artist_lookup(db)

    rows = (
        db.query(ArtistLastfmSimilarity)
        .filter(ArtistLastfmSimilarity.source_artist_key == source_artist_key)
        .all()
    )

    resolved_artists = []
    track_score_map: dict[int, float] = defaultdict(float)
    track_artist_map: dict[int, set[str]] = defaultdict(set)

    for row in rows:
        row_match_score = float(row.match_score or 0.0)
        if row_match_score < min_match_score:
            continue

        matched_local_artists = local_artist_lookup.get(row.similar_artist_key, [])
        if not matched_local_artists:
            continue

        resolved_artists.append(
            {
                "similar_artist_name": row.similar_artist_name,
                "similar_artist_key": row.similar_artist_key,
                "match_score": row_match_score,
                "matched_local_artists": matched_local_artists,
            }
        )

        local_tracks = (
            db.query(Track.id, TrackArtist.artist_name)
            .join(TrackArtist, TrackArtist.track_id == Track.id)
            .filter(TrackArtist.artist_name.in_(matched_local_artists))
            .all()
        )

        for track_id, artist_name in local_tracks:
            track_score_map[track_id] += row_match_score
            if artist_name:
                track_artist_map[track_id].add(artist_name)

    resolved_tracks = [
        {
            "track_id": track_id,
            "score": score,
            "matched_artists": sorted(track_artist_map.get(track_id, set())),
        }
        for track_id, score in sorted(
            track_score_map.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return {
        "success": True,
        "reason": "ok",
        "source_artist_name": source_artist_name,
        "source_artist_key": source_artist_key,
        "resolved_artists": resolved_artists,
        "resolved_tracks": resolved_tracks,
    }