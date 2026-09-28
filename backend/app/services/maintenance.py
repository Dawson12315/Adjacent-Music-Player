"""Removing tracks whose files are gone — carefully.

Cleanup is the one job that deletes user data (plays, likes, playlist rows go
with the track), so it is built to refuse rather than guess:

- The library root must exist, be non-empty, and still contain at least one
  file the database knows about. An unmounted NAS looks like an empty
  directory, and an empty directory must never read as "every file is gone".
- Those checks are repeated after the walk. A share that drops halfway through
  is caught before anything is deleted.
- A track is marked missing on the first sighting and only deleted once it has
  stayed missing for CLEANUP_GRACE_DAYS. A file that comes back is unmarked.
- Deleting more than CLEANUP_MAX_MISSING_COUNT tracks, or more than
  CLEANUP_MAX_MISSING_FRACTION of the library, needs an explicit `force`.
- On SQLite a backup is written before the first row is deleted.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
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
from app.services.db_backup import backup_sqlite_database
from app.services.job_locking import JobHeartbeat
from app.services.recommendations.rec_cache import invalidate_library_caches

logger = logging.getLogger(__name__)

# Keeps each IN (...) list under SQLite's bound-parameter ceiling.
_DELETE_CHUNK_SIZE = 500

# How long a file has to stay missing before its track is deleted.
CLEANUP_GRACE_DAYS = 7

# Above either of these the run refuses without `force`: a real library does
# not lose a fifth of itself overnight, but an unmounted sub-share does.
CLEANUP_MAX_MISSING_COUNT = 500
CLEANUP_MAX_MISSING_FRACTION = 0.20

# How often the file walk touches the job lock's heartbeat (in tracks).
_HEARTBEAT_EVERY = 200

PRE_CLEANUP_BACKUP_LABEL = "pre-cleanup"
PRE_CLEANUP_BACKUP_KEEP = 3


class LibraryUnavailable(ValueError):
    """The library root is missing, empty, or holds none of our files."""

    code = "library_unavailable"


class CleanupRefused(Exception):
    """More would be deleted than the safety threshold allows without force."""

    code = "cleanup_refused"

    def __init__(self, missing: int, total: int):
        self.missing = missing
        self.total = total
        super().__init__(
            f"Cleanup would remove {missing} of {total} tracks. That is more "
            f"than the safety limit ({CLEANUP_MAX_MISSING_COUNT} tracks or "
            f"{int(CLEANUP_MAX_MISSING_FRACTION * 100)}% of the library); "
            "run it again with force to confirm."
        )


def _check_library_root(library_root: Path) -> None:
    if not library_root.exists():
        raise LibraryUnavailable(
            f"Music library path does not exist: {library_root} — "
            "is the volume mounted?"
        )

    if not library_root.is_dir():
        raise LibraryUnavailable(
            f"Music library path is not a directory: {library_root}"
        )

    try:
        has_entries = any(library_root.iterdir())
    except OSError as error:
        raise LibraryUnavailable(
            f"Music library path cannot be read: {library_root} ({error})"
        ) from error

    if not has_entries:
        raise LibraryUnavailable(
            f"Music library path is empty: {library_root} — an unmounted "
            "share looks exactly like this, so nothing was removed."
        )


def cleanup_missing_tracks(
    db: Session,
    force: bool = False,
    now: datetime | None = None,
) -> dict:
    """Mark, unmark and eventually delete tracks whose files are gone.

    Raises LibraryUnavailable when the root cannot be trusted and
    CleanupRefused when the deletion exceeds the threshold without `force`.
    In both cases nothing has been deleted; missing marks may have been saved,
    which is deliberate — they are reversible.
    """
    now = now or datetime.utcnow()
    library_root = Path(settings.music_library_path)
    _check_library_root(library_root)

    tracks = db.query(Track).all()
    total = len(tracks)

    if total == 0:
        return _summary(0, 0, 0, 0)

    heartbeat = JobHeartbeat("cleanup")
    sentinel: Path | None = None
    missing: list[Track] = []
    returned = 0

    for index, track in enumerate(tracks, start=1):
        if index % _HEARTBEAT_EVERY == 0:
            heartbeat.tick()

        path = Path(track.file_path)
        if path.exists():
            if sentinel is None:
                sentinel = path
            if track.missing_since is not None:
                track.missing_since = None
                returned += 1
            continue

        missing.append(track)

    if sentinel is None:
        raise LibraryUnavailable(
            f"None of the {total} tracks in the database can be found under "
            f"{library_root}. If the library really moved, purge the stored "
            "tracks and scan the new location instead."
        )

    # The walk can take minutes over a network mount. If the share dropped
    # during it, every remaining track "went missing" at once.
    _check_library_root(library_root)
    if not sentinel.exists():
        raise LibraryUnavailable(
            f"The music library became unreachable during cleanup "
            f"({sentinel} disappeared) — nothing was removed."
        )

    newly_missing = 0
    expired: list[Track] = []
    grace = timedelta(days=CLEANUP_GRACE_DAYS)

    for track in missing:
        if track.missing_since is None:
            track.missing_since = now
            newly_missing += 1
        elif now - track.missing_since >= grace:
            expired.append(track)

    # Marks go to the database before any bulk delete below: an ORM update
    # left pending on a row the delete has already removed fails the commit.
    db.flush()

    to_delete = missing if force else expired

    if not force and to_delete:
        over_count = len(to_delete) > CLEANUP_MAX_MISSING_COUNT
        over_fraction = len(to_delete) / total > CLEANUP_MAX_MISSING_FRACTION
        if over_count or over_fraction:
            # Keep the marks: they are what lets a later, confirmed run
            # delete without waiting out the grace period again.
            db.commit()
            raise CleanupRefused(missing=len(to_delete), total=total)

    if not to_delete:
        db.commit()
        return _summary(0, newly_missing, len(missing), returned)

    # Nothing is deleted without a way back. Raises if the copy fails.
    backup = backup_sqlite_database(
        label=PRE_CLEANUP_BACKUP_LABEL, keep=PRE_CLEANUP_BACKUP_KEEP
    )
    if backup is not None:
        logger.info("Pre-cleanup backup written to %s", backup)

    _delete_tracks(db, [track.id for track in to_delete])

    db.commit()
    invalidate_library_caches()

    still_missing = len(missing) - len(to_delete)
    logger.info(
        "Cleanup removed %s tracks (%s newly missing, %s still within grace, %s returned)",
        len(to_delete),
        newly_missing,
        still_missing,
        returned,
    )
    return _summary(len(to_delete), newly_missing, still_missing, returned)


def _summary(removed: int, marked_missing: int, still_missing: int, returned: int) -> dict:
    return {
        "removed": removed,
        "marked_missing": marked_missing,
        "still_missing": still_missing,
        "returned": returned,
        "grace_days": CLEANUP_GRACE_DAYS,
    }


def _delete_tracks(db: Session, track_ids: list[int]) -> None:
    # Every table referencing tracks is cleared explicitly with bulk statements
    # that execute immediately: FK enforcement is on, this session does not
    # autoflush, and whether a given table's FK carries ON DELETE CASCADE
    # depends on which schema vintage created it. Chunked so the IN lists stay
    # under SQLite's bound-parameter limit however many files went missing.
    for start in range(0, len(track_ids), _DELETE_CHUNK_SIZE):
        chunk = track_ids[start : start + _DELETE_CHUNK_SIZE]

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
