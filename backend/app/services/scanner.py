import logging
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


def scan_directory(base_path: str, limit: int = 20, progress_callback=None) -> dict:
    base = Path(base_path)

    if not base.exists():
        raise ValueError(
            f"Music library path does not exist: {base_path} — is the volume mounted?"
        )

    db = SessionLocal()

    count = 0
    files_seen = 0
    pending_in_batch = 0

    def report_progress():
        if progress_callback:
            progress_callback(files_seen=files_seen, added=count)

    try:
        # One query instead of one per file; 36k existence SELECTs was most of
        # the incremental-scan cost.
        known_file_paths = {row[0] for row in db.query(Track.file_path).all()}

        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue

            if not is_supported_audio_file(file_path):
                continue

            files_seen += 1
            if files_seen % 100 == 0:
                report_progress()

            if str(file_path) in known_file_paths:
                continue

            try:
                metadata = extract_track_metadata(str(file_path))
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

            track = Track(
                title=final_title,
                artist=final_artist,
                album=final_album,
                genre=primary_genre,
                raw_title=raw_title,
                raw_artist=raw_artist,
                raw_album=raw_album,
                raw_genre=raw_genre,
                file_path=metadata["file_path"],
                duration_seconds=metadata.get("duration_seconds"),
            )

            db.add(track)
            db.flush()

            for index, artist_name in enumerate(artist_list):
                db.add(
                    TrackArtist(
                        track_id=track.id,
                        artist_name=artist_name,
                        position=index,
                    )
                )

            for genre_name in normalized_genres:
                db.add(
                    TrackGenre(
                        track_id=track.id,
                        genre=genre_name,
                    )
                )

            known_file_paths.add(str(file_path))
            count += 1
            pending_in_batch += 1

            if pending_in_batch >= SCAN_COMMIT_BATCH_SIZE:
                db.commit()
                pending_in_batch = 0
                logger.info("Scan progress: %s tracks added", count)
                report_progress()

            if count >= limit:
                break

        if pending_in_batch:
            db.commit()

        report_progress()
        logger.info("Scan complete. Added %s tracks.", count)

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