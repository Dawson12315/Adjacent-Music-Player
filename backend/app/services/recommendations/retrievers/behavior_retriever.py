from sqlalchemy.orm import Session, selectinload

from app.models.track import Track
from app.models.track_user_stats import TrackUserStats
from app.services.recommendations.genre_utils import get_track_families
from app.services.recommendations.types import RetrievedCandidate


def retrieve_behavior_candidates(
    db: Session,
    playlist_track_ids: list[int],
    playlist_profile: dict,
    limit: int = 150,
):
    candidates: dict[int, RetrievedCandidate] = {}

    family_counts = playlist_profile.get("family_counts", {})
    artist_counts = playlist_profile.get("artist_counts", {})
    album_counts = playlist_profile.get("album_counts", {})
    metadata_sparse = bool(playlist_profile.get("metadata_sparse"))
    is_multi_cluster = bool(playlist_profile.get("is_multi_cluster"))

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
        .limit(limit * 3)
        .all()
    )

    ranked_rows: list[tuple[float, int]] = []

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

        candidate_families = get_track_families(track)
        shared_families = [
            family for family in candidate_families if family in family_counts
        ]

        artist_key = (track.artist or "").strip().casefold()
        album_key = f"{artist_key}::{(track.album or '').strip().casefold()}"

        affinity = 0.15

        if shared_families:
            affinity = 1.0 + (0.1 * max(len(shared_families) - 1, 0))
        elif artist_key and artist_key in artist_counts:
            affinity = 0.7
        elif track.album and album_key in album_counts:
            affinity = 0.55
        elif metadata_sparse:
            affinity = 0.35
        elif is_multi_cluster:
            affinity = 0.45

        final_behavior_score = behavior_score * affinity
        if final_behavior_score <= 0:
            continue

        ranked_rows.append((final_behavior_score, track.id))

    ranked_rows.sort(key=lambda item: item[0], reverse=True)

    for score, track_id in ranked_rows[:limit]:
        candidate = candidates.setdefault(
            track_id,
            RetrievedCandidate(track_id=track_id)
        )
        candidate.add_score("behavior", float(score))

    return candidates