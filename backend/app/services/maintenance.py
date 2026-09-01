from pathlib import Path

from sqlalchemy.orm import Session

from app.models.listening_event import ListeningEvent
from app.models.playback_queue_item import PlaybackQueueItem
from app.models.playback_session import PlaybackSession
from app.models.playlist_track import PlaylistTrack
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_cooccurrence import TrackCooccurrence
from app.models.track_genre import TrackGenre
from app.models.track_lastfm_similarity import TrackLastfmSimilarity
from app.models.track_user_stats import TrackUserStats
from app.config import settings
from app.services.recommendations.rec_cache import invalidate_library_caches
from app.services.scanner import scan_directory

# Keeps each IN (...) list under SQLite's bound-parameter ceiling.
_DELETE_CHUNK_SIZE = 500


def cleanup_missing_tracks(db: Session) -> dict:
    # If the library root itself is gone the files are not missing — the
    # volume is. Refuse rather than delete every track over an unmounted NAS.
    library_root = Path(settings.music_library_path)
    if not library_root.exists():
        raise ValueError(
            f"Music library path does not exist: {library_root} — "
            "is the volume mounted?"
        )

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

    # Every table referencing tracks is cleared explicitly with bulk statements
    # that execute immediately: FK enforcement is on, this session does not
    # autoflush, and whether a given table's FK carries ON DELETE CASCADE
    # depends on which schema vintage created it. Chunked so the IN lists stay
    # under SQLite's bound-parameter limit however many files went missing.
    for start in range(0, len(removed_track_ids), _DELETE_CHUNK_SIZE):
        chunk = removed_track_ids[start : start + _DELETE_CHUNK_SIZE]

        db.query(PlaylistTrack).filter(
            PlaylistTrack.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(PlaybackQueueItem).filter(
            PlaybackQueueItem.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(PlaybackSession).filter(
            PlaybackSession.current_track_id.in_(chunk)
        ).update(
            {
                PlaybackSession.current_track_id: None,
                PlaybackSession.queue_index: -1,
                PlaybackSession.current_time_seconds: 0,
                PlaybackSession.is_playing: False,
            },
            synchronize_session=False,
        )

        db.query(TrackLastfmSimilarity).filter(
            TrackLastfmSimilarity.source_track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(TrackLastfmSimilarity).filter(
            TrackLastfmSimilarity.similar_track_id.in_(chunk)
        ).update(
            {TrackLastfmSimilarity.similar_track_id: None},
            synchronize_session=False,
        )

        db.query(TrackCooccurrence).filter(
            TrackCooccurrence.track_a_id.in_(chunk)
            | TrackCooccurrence.track_b_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(TrackUserStats).filter(
            TrackUserStats.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(ListeningEvent).filter(
            ListeningEvent.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(TrackArtist).filter(
            TrackArtist.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(TrackGenre).filter(
            TrackGenre.track_id.in_(chunk)
        ).delete(synchronize_session=False)

        db.query(Track).filter(
            Track.id.in_(chunk)
        ).delete(synchronize_session=False)

    db.commit()
    invalidate_library_caches()

    return {"removed": removed_count}

def scan_library_job(db: Session) -> dict:
    result = scan_directory(settings.music_library_path, limit=100000)
    return result