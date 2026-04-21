from sqlalchemy.orm import Session, selectinload

from app.models.listening_event import ListeningEvent
from app.models.track import Track
from app.models.track_user_stats import TrackUserStats


def get_top_played_tracks(db: Session, limit: int = 20) -> list[Track]:
    rows = (
        db.query(Track)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(TrackUserStats.play_count > 0)
        .order_by(
            TrackUserStats.play_count.desc(),
            TrackUserStats.last_played_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return rows


def get_most_liked_tracks(db: Session, limit: int = 20) -> list[Track]:
    rows = (
        db.query(Track)
        .join(TrackUserStats, TrackUserStats.track_id == Track.id)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(TrackUserStats.like_count > 0)
        .order_by(
            TrackUserStats.like_count.desc(),
            TrackUserStats.last_played_at.desc(),
        )
        .limit(limit)
        .all()
    )
    return rows


def get_recently_played_tracks(db: Session, limit: int = 20) -> list[Track]:
    recent_track_ids = (
        db.query(ListeningEvent.track_id)
        .filter(ListeningEvent.event_type == "play_started")
        .order_by(ListeningEvent.created_at.desc())
        .all()
    )

    ordered_unique_ids = []
    seen = set()

    for (track_id,) in recent_track_ids:
        if track_id in seen:
            continue
        seen.add(track_id)
        ordered_unique_ids.append(track_id)

        if len(ordered_unique_ids) >= limit:
            break

    if not ordered_unique_ids:
        return []

    tracks = (
        db.query(Track)
        .options(
            selectinload(Track.track_genres),
            selectinload(Track.track_artists),
        )
        .filter(Track.id.in_(ordered_unique_ids))
        .all()
    )

    track_map = {track.id: track for track in tracks}
    return [track_map[track_id] for track_id in ordered_unique_ids if track_id in track_map]