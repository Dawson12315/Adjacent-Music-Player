from collections import Counter

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

    scores = Counter()

    for row in rows:
        if row.track_a_id in playlist_track_ids and row.track_b_id not in playlist_track_ids:
            scores[row.track_b_id] += row.cooccurrence_count
        elif row.track_b_id in playlist_track_ids and row.track_a_id not in playlist_track_ids:
            scores[row.track_a_id] += row.cooccurrence_count

    for track_id, score in scores.items():
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id),
        )

        candidate.add_score("cooccurrence", float(score))

    return candidates