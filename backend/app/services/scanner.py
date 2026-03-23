from pathlib import Path

from app.db import SessionLocal
from app.models.track import Track
from app.services.metadata import extract_track_metadata
from app.utils.files import is_supported_audio_file


def scan_directory(base_path: str, limit: int = 20):
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
                print(f"Skipping file (metadata error): {file_path}")
                continue

            track = Track(**metadata)

            db.add(track)
            db.commit()

            count += 1
            print(f"Added: {metadata['title']}")

            if count >= limit:
                break

        print(f"Scan complete. Added {count} tracks.")

    finally:
        db.close()