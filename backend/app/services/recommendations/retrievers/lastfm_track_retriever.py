from sqlalchemy.orm import Session

from app.models.track_lastfm_similarity import TrackLastfmSimilarity
from app.services.recommendations.types import RetrievedCandidate


def retrieve_lastfm_track_candidates(
    db: Session,
    playlist_track_ids: list[int],
    limit: int = 300,
    min_match_score: float = 0.20,
):
    candidates: dict[int, RetrievedCandidate] = {}

    if not playlist_track_ids:
        return candidates

    similarity_rows = (
        db.query(TrackLastfmSimilarity)
        .filter(
            TrackLastfmSimilarity.source_track_id.in_(playlist_track_ids),
            TrackLastfmSimilarity.similar_track_id.isnot(None),
            ~TrackLastfmSimilarity.similar_track_id.in_(playlist_track_ids),
        )
        .all()
    )

    if not similarity_rows:
        return candidates

    for row in similarity_rows:
        match_score = float(row.match_score or 0.0)

        if match_score < min_match_score:
            continue

        retrieval_score = min(match_score, 1.0) * 3.0

        candidate = candidates.setdefault(
            row.similar_track_id,
            RetrievedCandidate(track_id=row.similar_track_id),
        )
        candidate.add_score("lastfm_track", float(retrieval_score))

        if len(candidates) >= limit:
            break

    sorted_candidates = sorted(
        candidates.items(),
        key=lambda item: item[1].total_retrieval_score,
        reverse=True,
    )

    return dict(sorted_candidates[:limit])