from collections import defaultdict
import random

from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.types import RetrievedCandidate


def retrieve_genre_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 300,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    candidates: dict[int, RetrievedCandidate] = {}

    family_counts = playlist_profile.get("family_counts", {})
    if not family_counts:
        return candidates

    focused_playlist = len(family_counts) <= 2
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster"))
    top_family_limit = 2 if focused_playlist else (4 if is_multi_cluster else 5)

    top_families = {
        family
        for family, _count in family_counts.most_common(top_family_limit)
    }

    tracks = (
        db.query(Track)
        .options(selectinload(Track.track_genres))
        .filter(~Track.id.in_(playlist_track_ids))
        .limit(3000)
        .all()
    )

    score_buckets: dict[float, list[int]] = defaultdict(list)

    for track in tracks:
        track_families = get_track_families(track)
        if not track_families:
            continue

        shared_families = [
            family for family in track_families if family in family_counts
        ]
        shared_top_families = [
            family for family in track_families if family in top_families
        ]

        if focused_playlist:
            if not shared_top_families:
                continue
        else:
            if not shared_families:
                continue

        score = 0.0

        for family in shared_families:
            family_weight = float(family_counts.get(family, 0))
            score += family_weight

            if focused_playlist and family in top_families:
                score += 2.0

            if is_multi_cluster and family in top_families:
                score += 0.75

        if len(shared_top_families) >= 2:
            score += 1.5

        if len(shared_families) >= 2:
            score += 1.5

        if focused_playlist:
            dominant_shared_count = len(shared_top_families)
            if dominant_shared_count == 1:
                score += 1.0
            elif dominant_shared_count == 0:
                continue

        if score <= 0:
            continue

        score_buckets[score].append(track.id)

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