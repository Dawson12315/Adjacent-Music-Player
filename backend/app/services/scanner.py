import logging
from stat import S_ISREG
from pathlib import Path

from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.services.filename_metadata import extract_metadata_from_filename
from app.services.metadata import extract_track_metadata
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist_list,
    normalize_genre_list,
    normalize_primary_artist,
    normalize_title
)
from app.services.musicbrainz_backfill_runner import start_musicbrainz_backfill_background
from app.services.genre_normalizer import normalize_genre
from app.utils.files import is_supported_audio_file

logger = logging.getLogger(__name__)

# Commit in groups rather than per track: one commit per track meant one fsync
# per file, which dominated scan time on large libraries.
SCAN_COMMIT_BATCH_SIZE = 200


def _refresh_track_metadata(db, track_id: int, file_path: Path, stat) -> bool:
    """Re-read a file whose tags changed since it was imported.

    Titles, artists and albums follow the file; edits made in Adjacent to
    those same fields are overwritten by the tag, which is what "the file is
    the source of truth" has to mean. Genres are left alone: the Last.fm
    enrichment adds to them and a re-read must not undo that.
    """
    try:
        metadata = extract_track_metadata(str(file_path))
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not re-read tags for %s -> %s", file_path, error)
        return False

    raw_title = metadata.get("title") or None
    raw_artist = metadata.get("artist") or None
    raw_album = metadata.get("album") or None
    filename_artist, filename_album, filename_title = extract_metadata_from_filename(str(file_path))

    resolved_artist = raw_artist or filename_artist
    title = normalize_title(raw_title if raw_title and not (" - " in raw_title and filename_title) else (filename_title or raw_title))
    artist = normalize_primary_artist(resolved_artist)
    album = normalize_album(raw_album or filename_album)

    track = db.query(Track).filter(Track.id == track_id).first()
    if track is None:
        return False

    track.title = title or track.title
    track.artist = artist
    track.album = album
    track.raw_title = raw_title
    track.raw_artist = raw_artist
    track.raw_album = raw_album
    track.duration_seconds = metadata.get("duration_seconds") or track.duration_seconds
    track.file_size = stat.st_size
    track.file_mtime_ns = stat.st_mtime_ns

    db.query(TrackArtist).filter(TrackArtist.track_id == track.id).delete(synchronize_session=False)
    for index, artist_name in enumerate(normalize_artist_list(resolved_artist)):
        db.add(TrackArtist(track_id=track.id, artist_name=artist_name, position=index))

    db.commit()
    return True


def scan_directory(base_path: str, limit: int = 20, progress_callback=None) -> dict:
    base = Path(base_path)

    if not base.exists():
        raise ValueError(
            f"Music library path does not exist: {base_path} — is the volume mounted?"
        )

    db = SessionLocal()

    count = 0
    files_seen = 0
    pending_batch: list[dict] = []

    def report_progress():
        if progress_callback:
            progress_callback(files_seen=files_seen, added=count)

    def write_batch():
        """Insert one gathered batch inside a short-lived transaction.

        Metadata extraction happens over what is usually a network mount and
        takes seconds per file. Interleaving it with the inserts held SQLite's
        single write lock for the entire batch — minutes at a time — during
        which every user action that writes (likes, playlist edits, listening
        events) sat blocked. Gather first, then write in one quick burst.

        Each row is its own savepoint: one unstorable row (a filename that
        is not valid UTF-8, a duplicate) used to discard the whole batch and
        end the scan — at the same file, every night.
        """
        nonlocal count

        written = 0

        for prepared in pending_batch:
            try:
                with db.begin_nested():
                    track = Track(**prepared["track"])
                    db.add(track)
                    db.flush()

                    for index, artist_name in enumerate(prepared["artists"]):
                        db.add(
                            TrackArtist(
                                track_id=track.id,
                                artist_name=artist_name,
                                position=index,
                            )
                        )

                    for genre_name in prepared["genres"]:
                        db.add(
                            TrackGenre(
                                track_id=track.id,
                                genre=genre_name,
                            )
                        )
                written += 1
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "Skipping file (could not store): %s -> %s",
                    prepared["track"].get("file_path"),
                    error,
                )

        db.commit()
        count += written
        pending_batch.clear()

        logger.info("Scan progress: %s tracks added", count)
        report_progress()

    try:
        # One query instead of one per file; 36k existence SELECTs was most of
        # the incremental-scan cost. The size and mtime come along: they are
        # how a moved file is recognised and how an edited tag is noticed.
        known = {
            path: (track_id, size, mtime_ns)
            for track_id, path, size, mtime_ns in db.query(
                Track.id, Track.file_path, Track.file_size, Track.file_mtime_ns
            ).all()
        }
        known_file_paths = set(known)
        # (size, mtime) → track ids, for spotting a file that moved. A match
        # only counts when the old path is really gone.
        by_identity: dict[tuple[int, int], list[int]] = {}
        for path, (track_id, size, mtime_ns) in known.items():
            if size is not None and mtime_ns is not None:
                by_identity.setdefault((size, mtime_ns), []).append(track_id)

        moved = 0
        refreshed = 0

        for file_path in base.rglob("*"):
            try:
                stat = file_path.stat()
            except OSError:
                continue

            if not S_ISREG(stat.st_mode):
                continue

            if not is_supported_audio_file(file_path):
                continue

            path_text = str(file_path)

            # A filename that is not valid UTF-8 cannot be stored as text;
            # say so once and move on rather than end the scan here nightly.
            try:
                path_text.encode("utf-8")
            except UnicodeEncodeError:
                logger.warning("Skipping file (name is not valid UTF-8): %r", file_path)
                continue

            files_seen += 1
            if files_seen % 100 == 0:
                report_progress()

            identity = (stat.st_size, stat.st_mtime_ns)

            if path_text in known_file_paths:
                track_id, size, mtime_ns = known[path_text]

                if size is None or mtime_ns is None:
                    # First scan since these were recorded: fill them in.
                    db.query(Track).filter(Track.id == track_id).update(
                        {Track.file_size: stat.st_size, Track.file_mtime_ns: stat.st_mtime_ns},
                        synchronize_session=False,
                    )
                    db.commit()
                elif (size, mtime_ns) != identity:
                    # The file changed under the same name: tags were edited.
                    if _refresh_track_metadata(db, track_id, file_path, stat):
                        refreshed += 1
                continue

            # A new path with a known size and mtime whose old path is gone
            # is a move, not a new track: keep the row and its history.
            moved_track_id = None
            for candidate_id in by_identity.get(identity, []):
                old_path = next((p for p, (tid, _s, _m) in known.items() if tid == candidate_id), None)
                if old_path and not Path(old_path).exists():
                    moved_track_id = candidate_id
                    break

            if moved_track_id is not None:
                db.query(Track).filter(Track.id == moved_track_id).update(
                    {Track.file_path: path_text, Track.missing_since: None},
                    synchronize_session=False,
                )
                db.commit()
                known_file_paths.add(path_text)
                moved += 1
                logger.info("Track %s moved to %s", moved_track_id, file_path)
                continue

            try:
                metadata = extract_track_metadata(path_text)
            except Exception as e:
                logger.warning("Skipping file (metadata error): %s -> %s", file_path, e)
                continue

            raw_title = metadata.get("title") or None
            raw_artist = metadata.get("artist") or None
            raw_album = metadata.get("album") or None
            raw_genre = metadata.get("raw_genre") or None

            filename_artist, filename_album, filename_title = extract_metadata_from_filename(
                str(file_path)
            )

            use_filename_title = False

            if not raw_title:
                use_filename_title = True
            elif " - " in raw_title and filename_title:
                use_filename_title = True

            resolved_artist_value = raw_artist or filename_artist
            final_title = normalize_title(
                filename_title if use_filename_title else raw_title
            )
            final_artist = normalize_primary_artist(resolved_artist_value)
            final_album = normalize_album(raw_album or filename_album)
            normalized_genres = normalize_genre_list(metadata.get("genre"))
            primary_genre = normalized_genres[0] if normalized_genres else normalize_genre(metadata.get("genre"))
            artist_list = normalize_artist_list(resolved_artist_value)

            pending_batch.append(
                {
                    "track": {
                        "title": final_title,
                        "artist": final_artist,
                        "album": final_album,
                        "genre": primary_genre,
                        "raw_title": raw_title,
                        "raw_artist": raw_artist,
                        "raw_album": raw_album,
                        "raw_genre": raw_genre,
                        "file_path": metadata["file_path"],
                        "duration_seconds": metadata.get("duration_seconds"),
                        "file_size": stat.st_size,
                        "file_mtime_ns": stat.st_mtime_ns,
                    },
                    "artists": artist_list,
                    "genres": normalized_genres,
                }
            )
            known_file_paths.add(str(file_path))

            if len(pending_batch) >= SCAN_COMMIT_BATCH_SIZE:
                write_batch()

            if count + len(pending_batch) >= limit:
                break

        if pending_batch:
            write_batch()

        report_progress()
        logger.info(
            "Scan complete. Added %s tracks, recognised %s moves, refreshed %s.",
            count,
            moved,
            refreshed,
        )

        if count > 0:
            # Backfill runs for hours on a big import; hand it to the shared
            # background runner instead of blocking the scan caller.
            started = start_musicbrainz_backfill_background()
            logger.info(
                "MusicBrainz backfill %s",
                "started in background" if started else "already running",
            )

        return {"added": count}

    finally:
        db.close()