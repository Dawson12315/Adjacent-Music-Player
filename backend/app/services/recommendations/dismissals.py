"""Recycled suggestions, held out of one playlist's answers for a while.

Pressing "refresh" on a playlist's suggestions means "not these": the rows
on screen are recorded against that playlist and stay out of its answers
for DISMISSAL_DAYS, then return. The hold is per playlist, so a track
recycled from one is still fair game for another.
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.recommendation_dismissal import RecommendationDismissal

DISMISSAL_DAYS = 4
# The home rail's hold is shorter than a playlist's, and its scope is the
# rail itself: playlist ids start at 1, so 0 is free and needs no schema
# change. (A nullable scope would not restamp on SQLite, where NULLs are
# distinct inside a unique constraint.)
FOR_YOU_DISMISSAL_DAYS = 3
FOR_YOU_SCOPE = 0
# A recycle can carry at most one screen of rows; anything larger is a bug
# or a script, and is trimmed rather than stored.
MAX_DISMISSED_PER_RECYCLE = 100


def dismissed_track_ids(db: Session, user_id: int, playlist_id: int, now: datetime | None = None) -> list[int]:
    now = now or datetime.utcnow()
    rows = (
        db.query(RecommendationDismissal.track_id)
        .filter(
            RecommendationDismissal.user_id == user_id,
            RecommendationDismissal.playlist_id == playlist_id,
            RecommendationDismissal.expires_at > now,
        )
        .all()
    )
    return [row.track_id for row in rows]


def dismiss_tracks(
    db: Session,
    user_id: int,
    playlist_id: int,
    track_ids: list[int],
    now: datetime | None = None,
    days: int = DISMISSAL_DAYS,
) -> int:
    """Hold these out of this scope's suggestions; a repeat restamps."""
    now = now or datetime.utcnow()
    expires_at = now + timedelta(days=days)
    wanted = list(dict.fromkeys(int(track_id) for track_id in track_ids if track_id))[:MAX_DISMISSED_PER_RECYCLE]
    if not wanted:
        return 0

    existing = {
        row.track_id: row
        for row in db.query(RecommendationDismissal)
        .filter(
            RecommendationDismissal.user_id == user_id,
            RecommendationDismissal.playlist_id == playlist_id,
            RecommendationDismissal.track_id.in_(wanted),
        )
        .all()
    }
    for track_id in wanted:
        row = existing.get(track_id)
        if row:
            row.expires_at = expires_at
        else:
            db.add(
                RecommendationDismissal(
                    user_id=user_id, playlist_id=playlist_id, track_id=track_id, expires_at=expires_at
                )
            )
    db.commit()
    return len(wanted)


def prune_expired_dismissals(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    removed = (
        db.query(RecommendationDismissal)
        .filter(RecommendationDismissal.expires_at <= now)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(removed or 0)
