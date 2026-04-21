from collections import Counter, defaultdict
import random

from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.types import RetrievedCandidate


def retrieve_genre_candidates(
    db: Session,
    playlist_track_ids: list[int],
    family_counts: Counter,
    limit: int = 300,
    refresh: int = 0,
    playlist_id: int | None = None,
):
    candidates: dict[int, RetrievedCandidate] = {}

    if not family_counts:
        return candidates

    top_families = {
        family
        for family, _count in family_counts.most_common(2)
    }

    tracks = (
        db.query(Track)
        .options(selectinload(Track.track_genres))
        .filter(~Track.id.in_(playlist_track_ids))
        .limit(2000)
        .all()
    )

    score_buckets: dict[float, list[int]] = defaultdict(list)

    for track in tracks:
        track_families = get_track_families(track)

        if not track_families:
            continue

        shared_top_families = [
            family for family in track_families if family in top_families
        ]

        if not shared_top_families:
            continue

        score = 0
        for family in shared_top_families:
            score += family_counts.get(family, 0)

        if score <= 0:
            continue

        score_buckets[float(score)].append(track.id)

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
        candidate.add_score("genre", score)

    return candidates