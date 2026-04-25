from collections import defaultdict
import random

from sqlalchemy.orm import Session

from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.lastfm_artist_matching import build_local_artist_lookup
from app.services.recommendations.types import RetrievedCandidate
from app.utils.artist_normalization import normalize_artist_name


def retrieve_lastfm_artist_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 300,
    refresh: int = 0,
    playlist_id: int | None = None,
    min_match_score: float = 0.40,
    max_tracks_per_artist: int = 2,
):
    candidates: dict[int, RetrievedCandidate] = {}

    if not playlist_track_ids:
        return candidates

    playlist_tracks = playlist_profile.get("tracks", [])
    if not playlist_tracks:
        return candidates

    seed_artist_keys = []
    seen_seed_artist_keys = set()

    for track in playlist_tracks:
        artist_name = track.get("artist")
        artist_key = normalize_artist_name(artist_name)

        if not artist_key or artist_key in seen_seed_artist_keys:
            continue

        seen_seed_artist_keys.add(artist_key)
        seed_artist_keys.append(artist_key)

    if not seed_artist_keys:
        return candidates

    similarity_rows = (
        db.query(ArtistLastfmSimilarity)
        .filter(ArtistLastfmSimilarity.source_artist_key.in_(seed_artist_keys))
        .all()
    )

    if not similarity_rows:
        return candidates

    local_artist_lookup = build_local_artist_lookup(db)
    rng = random.Random(f"lastfm_artist:{playlist_id}:{refresh}")

    artist_to_track_ids: dict[str, list[int]] = defaultdict(list)
    track_rows = (
        db.query(Track.id, TrackArtist.artist_name)
        .join(TrackArtist, TrackArtist.track_id == Track.id)
        .filter(~Track.id.in_(playlist_track_ids))
        .all()
    )

    for track_id, artist_name in track_rows:
        if not artist_name:
            continue
        artist_key = normalize_artist_name(artist_name)
        if not artist_key:
            continue
        
        artist_to_track_ids[artist_key].append(track_id)

    for row in similarity_rows:
        match_score = float(row.match_score or 0.0)
        if match_score < min_match_score:
            continue

        matched_local_artists = local_artist_lookup.get(row.similar_artist_key, [])
        if not matched_local_artists:
            continue

        retrieval_score = min(match_score, 1.0) * 2.0

        for local_artist_name in matched_local_artists:
            local_artist_key = normalize_artist_name(local_artist_name)
            artist_track_ids = list(dict.fromkeys(artist_to_track_ids.get(local_artist_key, [])))
            if not artist_track_ids:
                continue

            rng.shuffle(artist_track_ids)
            selected_track_ids = artist_track_ids[:max_tracks_per_artist]

            for track_id in selected_track_ids:
                candidate = candidates.setdefault(
                    track_id,
                    RetrievedCandidate(track_id=track_id),
                )
                candidate.add_score("lastfm_artist", float(retrieval_score))

                if len(candidates) >= limit:
                    break

            if len(candidates) >= limit:
                break

        if len(candidates) >= limit:
            break

    sorted_candidates = sorted(
        candidates.items(),
        key=lambda item: item[1].total_retrieval_score,
        reverse=True,
    )

    return dict(sorted_candidates[:limit])