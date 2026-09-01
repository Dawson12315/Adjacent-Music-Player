from collections import defaultdict
import random

from sqlalchemy.orm import Session

from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_user_stats import TrackUserStats
from app.services.lastfm_artist_matching import build_local_artist_lookup
from app.services.recommendations.rec_cache import get_or_build
from app.services.recommendations.types import RetrievedCandidate
from app.utils.artist_normalization import normalize_artist_name


def get_cached_local_artist_lookup(db: Session) -> dict:
    return get_or_build("local_artist_lookup", lambda: build_local_artist_lookup(db))


def get_cached_artist_track_map(db: Session) -> dict[str, list[int]]:
    """artist_key -> track ids, built once per library change instead of
    loading the whole track_artists table on every request."""

    def build():
        artist_to_track_ids: dict[str, list[int]] = defaultdict(list)

        rows = (
            db.query(Track.id, TrackArtist.artist_name)
            .join(TrackArtist, TrackArtist.track_id == Track.id)
            .all()
        )

        for track_id, artist_name in rows:
            if not artist_name:
                continue
            artist_key = normalize_artist_name(artist_name)
            if not artist_key:
                continue

            artist_to_track_ids[artist_key].append(track_id)

        return dict(artist_to_track_ids)

    return get_or_build("artist_track_map", build)


def retrieve_lastfm_artist_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 300,
    refresh: int = 0,
    playlist_id: int | None = None,
    min_match_score: float = 0.40,
    max_tracks_per_artist: int = 2,
    user_id: int | None = None,
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

    local_artist_lookup = get_cached_local_artist_lookup(db)
    artist_to_track_ids = get_cached_artist_track_map(db)
    excluded_ids = set(playlist_track_ids)
    rng = random.Random(f"lastfm_artist:{playlist_id}:{refresh}")

    # Which of a similar artist's tracks to surface: the ones the user
    # actually plays and finishes, not a random pick. Unplayed tracks still
    # get in through the shuffled tail so new material is not shut out.
    candidate_artist_keys = set()
    for row in similarity_rows:
        matched = local_artist_lookup.get(row.similar_artist_key, [])
        for local_artist_name in matched:
            candidate_artist_keys.add(normalize_artist_name(local_artist_name))

    all_candidate_track_ids = [
        track_id
        for artist_key in candidate_artist_keys
        for track_id in artist_to_track_ids.get(artist_key, [])
    ]

    stats_by_track: dict[int, float] = {}
    if all_candidate_track_ids and user_id is not None:
        stats_query = db.query(
            TrackUserStats.track_id,
            TrackUserStats.play_count,
            TrackUserStats.completion_count,
            TrackUserStats.like_count,
        ).filter(TrackUserStats.user_id == user_id)

        # Chunk the IN list to stay under SQLite's parameter ceiling.
        for start in range(0, len(all_candidate_track_ids), 500):
            chunk = all_candidate_track_ids[start : start + 500]
            for track_id, plays, completions, likes in stats_query.filter(
                TrackUserStats.track_id.in_(chunk)
            ).all():
                stats_by_track[track_id] = (
                    float(plays or 0)
                    + float(completions or 0) * 2.0
                    + float(likes or 0) * 3.0
                )

    def pick_tracks_for_artist(artist_key: str) -> list[int]:
        track_ids = [
            track_id
            for track_id in dict.fromkeys(artist_to_track_ids.get(artist_key, []))
            if track_id not in excluded_ids
        ]
        if not track_ids:
            return []

        rng.shuffle(track_ids)
        track_ids.sort(key=lambda track_id: stats_by_track.get(track_id, 0.0), reverse=True)
        return track_ids[:max_tracks_per_artist]

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

            for track_id in pick_tracks_for_artist(local_artist_key):
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
