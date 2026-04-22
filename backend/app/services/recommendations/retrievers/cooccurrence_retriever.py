from collections import Counter, defaultdict
import math

from sqlalchemy.orm import Session

from app.models.track_cooccurrence import TrackCooccurrence
from app.services.recommendations.types import RetrievedCandidate


def retrieve_cooccurrence_candidates(
    db: Session,
    playlist_track_ids: list[int],
    limit: int = 300,
):
    candidates: dict[int, RetrievedCandidate] = {}

    if not playlist_track_ids:
        return candidates

    rows = (
        db.query(TrackCooccurrence)
        .filter(
            (TrackCooccurrence.track_a_id.in_(playlist_track_ids))
            | (TrackCooccurrence.track_b_id.in_(playlist_track_ids))
        )
        .all()
    )

    total_counts = Counter()
    distinct_seed_links = defaultdict(set)

    for row in rows:
        if row.track_a_id in playlist_track_ids and row.track_b_id not in playlist_track_ids:
            total_counts[row.track_b_id] += row.cooccurrence_count
            distinct_seed_links[row.track_b_id].add(row.track_a_id)
        elif row.track_b_id in playlist_track_ids and row.track_a_id not in playlist_track_ids:
            total_counts[row.track_a_id] += row.cooccurrence_count
            distinct_seed_links[row.track_a_id].add(row.track_b_id)

    ranked_scores: list[tuple[int, float]] = []

    for track_id, total_count in total_counts.items():
        distinct_seed_count = len(distinct_seed_links[track_id])
        normalized_score = (0.7 * math.log1p(float(total_count))) + (1.5 * distinct_seed_count)
        ranked_scores.append((track_id, normalized_score))

    ranked_scores.sort(key=lambda item: item[1], reverse=True)

    for track_id, score in ranked_scores[:limit]:
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id),
        )
        candidate.add_score("cooccurrence", float(score))

    return candidates