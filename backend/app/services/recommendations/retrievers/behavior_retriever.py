from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.models.track_user_stats import TrackUserStats
from app.services.recommendations.types import RetrievedCandidate


def retrieve_behavior_candidates(
    db: Session,
    playlist_track_ids: list[int],
    limit: int = 150,
):
    candidates: dict[int, RetrievedCandidate] = {}

    rows = (
        db.query(Track, TrackUserStats)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(~Track.id.in_(playlist_track_ids))
        .filter(
            (TrackUserStats.play_count > 0)
            | (TrackUserStats.like_count > 0)
            | (TrackUserStats.completion_count > 0)
        )
        .order_by(
            TrackUserStats.like_count.desc(),
            TrackUserStats.play_count.desc(),
            TrackUserStats.completion_count.desc(),
            TrackUserStats.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )

    for track, stats in rows:
        behavior_score = 0.0

        behavior_score += float(stats.like_count) * 5.0
        behavior_score += float(stats.play_count) * 1.5
        behavior_score += float(stats.completion_count) * 2.0
        behavior_score += float(stats.avg_completion_ratio) * 3.0
        behavior_score += float(stats.replay_score) * 1.0

        if stats.skip_count > 0:
            behavior_score -= float(stats.skip_count) * 1.5

        if behavior_score <= 0:
            continue

        candidate = candidates.setdefault(
            track.id,
            RetrievedCandidate(track_id=track.id)
        )
        candidate.add_score("behavior", behavior_score)

    return candidates