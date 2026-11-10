import logging
from stat import S_ISREG
from pathlib import Path

from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.models.track_genre import TrackGenre
from app.services.filename_metadata import extract_track_number_from_filename
from app.services.metadata import extract_track_metadata
from app.services.metadata_normalizer import normalize_primary_artist
from app.services.musicbrainz_backfill_runner import start_musicbrainz_backfill_background
from app.services.track_resolution import resolve_track_fields
from app.models.track_lyrics import TrackLyrics
from app.services.lyrics_files import is_sidecar_name, lyrics_from_file
from app.utils.files import is_supported_audio_file
import json
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Commit in groups rather than per track: one commit per track meant one fsync
# per file, which dominated scan time on large libraries.
SCAN_COMMIT_BATCH_SIZE = 200

# Folders a library walk must not enter, relative to the library root: the
# NAS's own recycle bins and thumbnail caches hold audio files that are not
# part of the library (a deleted album came straight back from "#recycle").
EXCLUDED_FOLDER_NAMES = {
    "#recycle",
    "$recycle.bin",
    "@eadir",
    "@recycle",
    ".trash",
    ".trashes",
    ".trash-1000",
    ".recycle",
    "lost+found",
    "system volume information",
}

# Formats the old tag reader could not read at all; rows imported from them
# carry no tags and are re-read once.
_PREVIOUSLY_UNREAD_SUFFIXES = (".m4a", ".mp4", ".aac")


def is_excluded_path(relative_parts) -> bool:
    """Whether a path (as parts relative to the library root) is one the
    scan skips: a macOS resource fork ("._song.flac"), anything inside a
    hidden folder, or one of the NAS housekeeping folders above."""
    if not relative_parts:
        return False
    name = relative_parts[-1]
    if name.startswith("._") or name == ".DS_Store":
        return True
    for folder in relative_parts[:-1]:
        lowered = folder.lower()
        if lowered in EXCLUDED_FOLDER_NAMES or folder.startswith("."):
            return True
    return False


def _looks_misread(artist, raw_artist, file_path: str) -> bool:
    """A row the old reader got wrong: no artist, an artist that is just a
    position ("07", from a numbered soundtrack file), or an .m4a whose tags
    were never read."""
    if not artist:
        return True
    text = str(artist).strip()
    if text.isdigit() and len(text) <= 3:
        return True
    if not raw_artist and file_path.lower().endswith(_PREVIOUSLY_UNREAD_SUFFIXES):
        return True
    return False


def _refresh_track_metadata(db, track_id: int, file_path: Path, stat, base_path=None) -> bool:
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

    fields = resolve_track_fields(metadata, str(file_path), base_path)

    track = db.query(Track).filter(Track.id == track_id).first()
    if track is None:
        return False

    track.title = fields["title"] or track.title
    track.artist = fields["artist"]
    track.album = fields["album"]
    track.raw_title = fields["raw_title"]
    track.raw_artist = fields["raw_artist"]
    track.raw_album = fields["raw_album"]
    track.duration_seconds = metadata.get("duration_seconds") or track.duration_seconds
    track.file_size = stat.st_size
    track.file_mtime_ns = stat.st_mtime_ns
    track.track_number = fields["track_number"]
    track.disc_number = fields["disc_number"]
    # Edited tags may include edited lyrics.
    _read_lyrics_for(db, track_id, file_path)
    track.album_artist = fields["album_artist"] or ""

    db.query(TrackArtist).filter(TrackArtist.track_id == track.id).delete(synchronize_session=False)
    for index, artist_name in enumerate(fields["artists"]):
        db.add(TrackArtist(track_id=track.id, artist_name=artist_name, position=index))

    db.commit()
    return True


def _store_lyrics(db, track_id: int, found: dict | None) -> None:
    """Keep what the file says about its lyrics, without touching a person's
    corrections: a `user` row outranks the file and stays as it is."""
    existing = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
    if existing is not None and existing.source == "user":
        return
    if found is None:
        # The file carries no lyrics (any more). A row that came from the
        # file goes with it; one the server produced from the audio stays.
        if existing is not None and existing.source in ("embedded", "sidecar"):
            db.delete(existing)
        return
    synced = json.dumps(found["synced"], ensure_ascii=False) if found.get("synced") else None
    if existing is None:
        db.add(
            TrackLyrics(
                track_id=track_id,
                source=found["source"],
                synced_source=found["source"] if synced else None,
                plain=found["plain"],
                synced=synced,
            )
        )
        return
    changed = existing.plain != found["plain"] or (existing.synced or None) != synced or existing.source != found["source"]
    if not changed:
        return
    existing.source = found["source"]
    existing.plain = found["plain"]
    # The file's own timing replaces timing the server made; the file's
    # words without timing keep a timing the server made for those same words.
    if synced:
        existing.synced = synced
        existing.synced_source = found["source"]
        existing.model = None
        existing.confidence = None
    elif existing.synced_source != "aligned":
        existing.synced = None
        existing.synced_source = None
    existing.updated_at = datetime.utcnow()


def _read_lyrics_for(db, track_id: int, file_path) -> None:
    """Read the file's tags and sidecar for lyrics and remember when."""
    try:
        found = lyrics_from_file(str(file_path))
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not read lyrics for %s -> %s", file_path, error)
        found = None
    _store_lyrics(db, track_id, found)
    db.query(Track).filter(Track.id == track_id).update(
        {Track.lyrics_checked_at: datetime.utcnow()}, synchronize_session=False
    )


def _checked_ns(checked_at) -> int:
    if checked_at is None:
        return -1
    return int(checked_at.replace(tzinfo=timezone.utc).timestamp() * 1_000_000_000)


def resolve_track_number(metadata: dict, file_path: str) -> int:
    """The tag's number, else the filename's, else 0 for "read, none"."""
    tagged = metadata.get("track_number")
    if tagged:
        return int(tagged)
    return extract_track_number_from_filename(file_path) or 0


def _backfill_album_artist(db, track_id: int, file_path) -> None:
    """Read the album-artist tag of a row imported before it was stored.
    Written as "" when the file has none, so the row is read once."""
    value = ""
    try:
        metadata = extract_track_metadata(str(file_path))
        raw = metadata.get("album_artist")
        value = (normalize_primary_artist(raw) if raw else None) or ""
    except Exception:  # noqa: BLE001
        value = ""
    db.query(Track).filter(Track.id == track_id).update(
        {Track.album_artist: value}, synchronize_session=False
    )


def _backfill_track_number(db, track_id: int, file_path) -> None:
    """Number a row imported before numbers were read: the name first, and
    the tag only when the name says nothing; either way the row is marked
    read so a library is walked for numbers once, not on every scan."""
    number = extract_track_number_from_filename(str(file_path))
    disc = None
    if not number:
        try:
            metadata = extract_track_metadata(str(file_path))
            number = metadata.get("track_number")
            disc = metadata.get("disc_number")
        except Exception:  # noqa: BLE001
            number = None
    db.query(Track).filter(Track.id == track_id).update(
        {Track.track_number: int(number or 0), Track.disc_number: disc},
        synchronize_session=False,
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def walk_roots(base: Path, within) -> list[Path]:
    """The folders a scan walks: the whole library, or only the ones named.

    `within` comes from the folder watcher, which knows which folders just
    changed. Anything outside the library or no longer a folder is dropped,
    and a folder inside another named folder is walked once, as part of its
    parent. An empty result means there is nothing left to walk — not the
    whole library.
    """
    if within is None:
        return [base]

    base_resolved = base.resolve()
    candidates: list[Path] = []
    for raw in within:
        folder = Path(raw)
        try:
            resolved = folder.resolve()
        except OSError:
            continue
        if not _is_within(resolved, base_resolved) or not folder.is_dir():
            continue
        candidates.append(folder)

    candidates.sort(key=lambda folder: len(folder.parts))
    kept: list[Path] = []
    for folder in candidates:
        if any(_is_within(folder, parent) for parent in kept):
            continue
        kept.append(folder)
    return kept


def scan_directory(base_path: str, limit: int = 20, progress_callback=None, within=None) -> dict:
    """Import what is new under the library.

    `within`, when given, is a list of folders inside the library and the walk
    covers only those — how the folder watcher imports one album's worth of
    files without statting every file on the mount. Everything after the
    walk (matching, moves, refreshes, the batch writes) is the same.
    """
    base = Path(base_path)

    if not base.exists():
        raise ValueError(
            f"Music library path does not exist: {base_path} — is the volume mounted?"
        )

    roots = walk_roots(base, within)

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
                                source="file",
                            )
                        )

                    found = prepared.get("lyrics")
                    if found:
                        db.add(
                            TrackLyrics(
                                track_id=track.id,
                                source=found["source"],
                                synced_source=found["source"] if found.get("synced") else None,
                                plain=found["plain"],
                                synced=json.dumps(found["synced"], ensure_ascii=False) if found.get("synced") else None,
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
        known: dict[str, tuple[int, int | None, int | None]] = {}
        # Rows from before track numbers were read; numbered as the walk
        # passes them, in batches, so the first scan after the upgrade does
        # the work once.
        unnumbered: set[str] = set()
        # Rows the old reader misread (see _looks_misread); re-read in place
        # as the walk passes them, so a library heals on its next scan.
        misread: set[str] = set()
        # Rows from before the album-artist tag was stored; read once.
        unread_album_artist: set[str] = set()
        # Rows never read for lyrics; read as the walk passes them.
        unread_lyrics: set[str] = set()
        # Track by the path without its suffix, for matching sidecar files.
        lyrics_checked_by_stem: dict[str, tuple[int, int]] = {}
        for track_id, path, size, mtime_ns, number, artist, raw_artist, album_artist, lyrics_checked in db.query(
            Track.id,
            Track.file_path,
            Track.file_size,
            Track.file_mtime_ns,
            Track.track_number,
            Track.artist,
            Track.raw_artist,
            Track.album_artist,
            Track.lyrics_checked_at,
        ).all():
            known[path] = (track_id, size, mtime_ns)
            if number is None:
                unnumbered.add(path)
            if _looks_misread(artist, raw_artist, path):
                misread.add(path)
            elif album_artist is None:
                unread_album_artist.add(path)
            if lyrics_checked is None:
                unread_lyrics.add(path)
            lyrics_checked_by_stem[str(Path(path).with_suffix(""))] = (track_id, _checked_ns(lyrics_checked))

        backfilled = 0
        healed = 0
        known_file_paths = set(known)
        path_by_id = {track_id: path for path, (track_id, _s, _m) in known.items()}
        # (size, mtime) → track ids, for spotting a file that moved. A match
        # only counts when the old path is really gone.
        by_identity: dict[tuple[int, int], list[int]] = {}
        for path, (track_id, size, mtime_ns) in known.items():
            if size is not None and mtime_ns is not None:
                by_identity.setdefault((size, mtime_ns), []).append(track_id)

        moved = 0
        refreshed = 0
        skipped_excluded = 0
        pending_updates = 0
        album_artists_read = 0
        lyrics_read = 0
        # Sidecar lyrics files met on the walk: stem → mtime, matched to
        # their tracks afterwards (the walk may meet the .lrc before the .mp3).
        sidecars_seen: dict[str, int] = {}

        stop_walk = False
        for root in roots:
            if stop_walk:
                break
            for file_path in root.rglob("*"):
                try:
                    stat = file_path.stat()
                except OSError:
                    continue

                if not S_ISREG(stat.st_mode):
                    continue

                if is_sidecar_name(file_path):
                    sidecars_seen[str(file_path.with_suffix(''))] = stat.st_mtime_ns
                    continue

                if not is_supported_audio_file(file_path):
                    continue

                try:
                    relative_parts = file_path.relative_to(base).parts
                except ValueError:
                    relative_parts = file_path.parts[-1:]
                if is_excluded_path(relative_parts):
                    skipped_excluded += 1
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
                        pending_updates += 1
                    elif (size, mtime_ns) != identity:
                        # The file changed under the same name: tags were edited.
                        if _refresh_track_metadata(db, track_id, file_path, stat, base_path):
                            refreshed += 1
                    elif path_text in misread:
                        if _refresh_track_metadata(db, track_id, file_path, stat, base_path):
                            healed += 1
                    elif path_text in unnumbered:
                        _backfill_track_number(db, track_id, file_path)
                        backfilled += 1
                        pending_updates += 1
                    elif path_text in unread_album_artist:
                        _backfill_album_artist(db, track_id, file_path)
                        album_artists_read += 1
                        pending_updates += 1
                    elif path_text in unread_lyrics:
                        _read_lyrics_for(db, track_id, file_path)
                        unread_lyrics.discard(path_text)
                        lyrics_read += 1
                        pending_updates += 1
                    if pending_updates and pending_updates % 200 == 0:
                        db.commit()
                    continue

                # A new path with a known size and mtime whose old path is gone
                # is a move, not a new track: keep the row and its history.
                moved_track_id = None
                for candidate_id in by_identity.get(identity, []):
                    old_path = path_by_id.get(candidate_id)
                    if old_path and old_path not in known_file_paths:
                        continue  # already matched to another new path
                    if old_path and not Path(old_path).exists():
                        moved_track_id = candidate_id
                        break

                if moved_track_id is not None:
                    db.query(Track).filter(Track.id == moved_track_id).update(
                        {Track.file_path: path_text, Track.missing_since: None},
                        synchronize_session=False,
                    )
                    db.commit()
                    known_file_paths.discard(path_by_id.get(moved_track_id))
                    known_file_paths.add(path_text)
                    path_by_id[moved_track_id] = path_text
                    moved += 1
                    logger.info("Track %s moved to %s", moved_track_id, file_path)
                    continue

                try:
                    metadata = extract_track_metadata(path_text)
                except Exception as e:
                    logger.warning("Skipping file (metadata error): %s -> %s", file_path, e)
                    continue

                fields = resolve_track_fields(metadata, path_text, base_path)

                if fields["sources"]["artist"] != "tag":
                    logger.debug(
                        "No artist tag on %s: artist from %s, album from %s",
                        file_path,
                        fields["sources"]["artist"],
                        fields["sources"]["album"],
                    )

                pending_batch.append(
                    {
                        "track": {
                            "title": fields["title"],
                            "artist": fields["artist"],
                            "album": fields["album"],
                            "genre": fields["genre"],
                            "raw_title": fields["raw_title"],
                            "raw_artist": fields["raw_artist"],
                            "raw_album": fields["raw_album"],
                            "raw_genre": fields["raw_genre"],
                            "file_path": metadata.get("file_path") or path_text,
                            "duration_seconds": metadata.get("duration_seconds"),
                            "file_size": stat.st_size,
                            "file_mtime_ns": stat.st_mtime_ns,
                            "track_number": fields["track_number"],
                            "disc_number": fields["disc_number"],
                            "album_artist": fields["album_artist"] or "",
                            "lyrics_checked_at": datetime.utcnow(),
                        },
                        "artists": fields["artists"],
                        "genres": fields["genres"],
                        "lyrics": lyrics_from_file(path_text),
                    }
                )
                known_file_paths.add(path_text)

                if len(pending_batch) >= SCAN_COMMIT_BATCH_SIZE:
                    write_batch()

                if count + len(pending_batch) >= limit:
                    stop_walk = True
                    break

        if pending_batch:
            write_batch()

        # A lyrics file beside a known track, new or newer than the last
        # read: the track's lyrics are read again. Tracks added on this walk
        # read their sidecar at import, and the walk never stats the sidecar
        # twice — the mtime came with the walk.
        sidecars_read = 0
        for stem, sidecar_mtime_ns in sidecars_seen.items():
            hit = lyrics_checked_by_stem.get(stem)
            if hit is None:
                continue
            track_id, checked_ns = hit
            if path_by_id.get(track_id) in unread_lyrics or sidecar_mtime_ns <= checked_ns:
                continue
            _read_lyrics_for(db, track_id, Path(path_by_id.get(track_id) or stem))
            sidecars_read += 1
            pending_updates += 1
        if pending_updates:
            db.commit()
        if lyrics_read or sidecars_read:
            logger.info("Read lyrics for %s tracks, %s from new or changed sidecar files.", lyrics_read, sidecars_read)
        if backfilled:
            logger.info("Numbered %s tracks imported before track numbers were read.", backfilled)
        if healed:
            logger.info("Re-read %s tracks the old tag reader had misread.", healed)
        if album_artists_read:
            logger.info("Read the album artist of %s tracks imported before it was stored.", album_artists_read)
        if skipped_excluded:
            logger.info("Skipped %s files in recycle, cache or hidden folders.", skipped_excluded)

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

        return {
            "added": count,
            "moved": moved,
            "refreshed": refreshed,
            "files_seen": files_seen,
        }

    finally:
        db.close()
