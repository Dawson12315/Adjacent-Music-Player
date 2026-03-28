from sqlalchemy.orm import Session

from app.models.playback_session import PlaybackSession


def get_or_create_playback_session(db: Session) -> PlaybackSession:
    session = db.query(PlaybackSession).first()

    if session:
        return session

    session = PlaybackSession(
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