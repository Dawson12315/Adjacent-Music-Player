from sqlalchemy.orm import Session

from app.models.playback_session import PlaybackSession


def get_or_create_playback_session(db: Session, user_id: int) -> PlaybackSession:
    session = (
        db.query(PlaybackSession)
        .filter(PlaybackSession.user_id == user_id)
        .first()
    )

    if session:
        return session

    old_global_session = (
        db.query(PlaybackSession)
        .filter(PlaybackSession.user_id.is_(None))
        .first()
    )

    if old_global_session:
        old_global_session.user_id = user_id
        db.commit()
        db.refresh(old_global_session)
        return old_global_session

    session = PlaybackSession(
        user_id=user_id,
        current_track_id=None,
        queue_index=-1,
        current_time_seconds=0,
        is_playing=False,
        is_shuffle=False,
        is_loop=False,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session