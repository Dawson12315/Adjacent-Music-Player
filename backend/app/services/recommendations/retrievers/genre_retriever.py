from collections import Counter, defaultdict
import random

from sqlalchemy.orm import Session

from app.models.track import Track
from app.models.track_genre import TrackGenre
from app.services.recommendations.genre_utils import map_genre_to_family
from app.services.recommendations.rec_cache import get_or_build
from app.services.recommendations.types import RetrievedCandidate


def get_genre_family_map(db: Session) -> dict[str, str]:
    """Distinct genre strings in the library mapped to their family, cached.

    A library has a few hundred distinct genre strings; mapping them once lets
    retrieval work backwards from the playlist's families to an indexed
    IN-query over track_genres instead of scanning tracks.
    """

    def build():
        genre_values = {
            row[0]
            for row in db.query(TrackGenre.genre).distinct().all()
            if row[0]
        }
        genre_values.update(
            row[0]
            for row in db.query(Track.genre).distinct().all()
            if row[0]
        )

        return {genre: map_genre_to_family(genre) for genre in genre_values}

    return get_or_build("genre_family_map", build)


def retrieve_genre_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 300,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    """Family-matched candidates over the WHOLE library.

    The previous version loaded `Track ... .limit(3000)` with no ordering and
    matched in Python — an arbitrary 8% slice of a large library (insertion
    order), silently excluding everything else from genre retrieval.
    """
    candidates: dict[int, RetrievedCandidate] = {}

    family_counts = playlist_profile.get("family_counts", {})
    if not family_counts:
        return candidates

    focused_playlist = bool(playlist_profile.get("focused_playlist"))
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster"))
    top_family_limit = 2 if focused_playlist else (4 if is_multi_cluster else 5)

    top_families = {
        family
        for family, _count in Counter(family_counts).most_common(top_family_limit)
    }

    genre_family_map = get_genre_family_map(db)
    target_genres = [
        genre
        for genre, family in genre_family_map.items()
        if family in family_counts
    ]

    if not target_genres:
        return candidates

    excluded_ids = set(playlist_track_ids)

    families_by_track: dict[int, set[str]] = defaultdict(set)

    genre_rows = (
        db.query(TrackGenre.track_id, TrackGenre.genre)
        .filter(TrackGenre.genre.in_(target_genres))
        .all()
    )
    for track_id, genre in genre_rows:
        if track_id in excluded_ids:
            continue
        families_by_track[track_id].add(genre_family_map[genre])

    # Tracks that predate multi-genre rows only carry Track.genre.
    legacy_rows = (
        db.query(Track.id, Track.genre)
        .filter(Track.genre.in_(target_genres))
        .all()
    )
    for track_id, genre in legacy_rows:
        if track_id in excluded_ids:
            continue
        families_by_track[track_id].add(genre_family_map[genre])

    score_buckets: dict[float, list[int]] = defaultdict(list)

    for track_id, shared_families in families_by_track.items():
        shared_top_families = [
            family for family in shared_families if family in top_families
        ]

        if focused_playlist and not shared_top_families:
            continue

        score = 0.0

        for family in shared_families:
            score += float(family_counts.get(family, 0))

            if focused_playlist and family in top_families:
                score += 2.0

            if is_multi_cluster and family in top_families:
                score += 0.75

        if len(shared_top_families) >= 2:
            score += 1.5

        if len(shared_families) >= 2:
            score += 1.5

        if focused_playlist and len(shared_top_families) == 1:
            score += 1.0

        if score <= 0:
            continue

        score_buckets[score].append(track_id)

    rng = random.Random(f"genre:{playlist_id}:{refresh}")
    selected_track_ids: list[tuple[int, float]] = []

    for score in sorted(score_buckets.keys(), reverse=True):
        bucket = score_buckets[score]
        rng.shuffle(bucket)

        for track_id in bucket:
            selected_track_ids.append((track_id, score))
            if len(selected_track_ids) >= limit:
                break

        if len(selected_track_ids) >= limit:
            break

    for track_id, score in selected_track_ids:
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id),
        )
        candidate.add_score("genre", float(score))

    return candidates
