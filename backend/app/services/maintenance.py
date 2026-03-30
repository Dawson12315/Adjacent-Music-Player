from pathlib import Path

from sqlalchemy.orm import Session

from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.config import settings
from app.services.scanner import scan_directory


def cleanup_missing_tracks(db: Session) -> dict:
    tracks = db.query(Track).all()

    removed_track_ids = []
    removed_count = 0

    for track in tracks:
        if Path(track.file_path).exists():
            continue

        removed_track_ids.append(track.id)
        removed_count += 1

    if not removed_track_ids:
        return {"removed": 0}

    db.query(PlaylistTrack).filter(
        PlaylistTrack.track_id.in_(removed_track_ids)
    ).delete(synchronize_session=False)

    db.query(PlaybackQueueItem).filter(
        PlaybackQueueItem.track_id.in_(removed_track_ids)
    ).delete(synchronize_session=False)

    session = db.query(PlaybackSession).first()
    if session and session.current_track_id in removed_track_ids:
        session.current_track_id = None
        session.queue_index = -1
        session.current_time_seconds = 0
        session.is_playing = False

    db.query(Track).filter(
        Track.id.in_(removed_track_ids)
    ).delete(synchronize_session=False)

    db.commit()

    return {"removed": removed_count}

def scan_library_job(db: Session) -> dict:
    result = scan_directory(settings.music_library_path, limit=100000)
    return result