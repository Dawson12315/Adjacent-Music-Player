from pathlib import Path

from app.db import SessionLocal
from app.models.track import Track
from app.services.filename_metadata import extract_metadata_from_filename
from app.services.metadata import extract_track_metadata
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist,
    normalize_title
)
from app.services.genre_normalizer import normalize_genre
from app.utils.files import is_supported_audio_file


def scan_directory(base_path: str, limit: int = 20) -> dict:
    base = Path(base_path)

    if not base.exists():
        raise ValueError(f"Path does not exist: {base_path}")

    db = SessionLocal()

    count = 0

    try:
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue

            if not is_supported_audio_file(file_path):
                continue

            existing = db.query(Track).filter(
                Track.file_path == str(file_path)
            ).first()

            if existing:
                continue

            try:
                metadata = extract_track_metadata(str(file_path))
            except Exception as e:
                print(f"Skipping file (metadata error): {file_path} -> {e}")
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

            final_title = normalize_title(
                filename_title if use_filename_title else raw_title
            )
            final_artist = normalize_artist(raw_artist or filename_artist)
            final_album = normalize_album(raw_album or filename_album)
            normalized_genre = normalize_genre(metadata.get("genre"))

            track = Track(
                title=final_title,
                artist=final_artist,
                album=final_album,
                genre=normalized_genre,
                raw_title=raw_title,
                raw_artist=raw_artist,
                raw_album=raw_album,
                raw_genre=raw_genre,
                file_path=metadata["file_path"],
            )

            db.add(track)
            db.commit()

            count += 1
            print(f"Added: {metadata['title']}")

            if count >= limit:
                break

        print(f"Scan complete. Added {count} tracks.")
        return {"added": count}

    finally:
        db.close()