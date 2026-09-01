from pathlib import Path

from mutagen import File

from app.db import SessionLocal
from app.models.track import Track


def read_duration_seconds(file_path: str) -> float | None:
    audio = File(file_path)

    if audio is None:
        return None

    return getattr(getattr(audio, "info", None), "length", None)


def backfill_durations(batch_size: int = 250):
    db = SessionLocal()
    try:
        tracks = (
            db.query(Track)
            .filter(Track.duration_seconds.is_(None))
            .order_by(Track.id.asc())
            .all()
        )

        print(f"Found {len(tracks)} tracks without a duration.")

        updated_count = 0
        missing_count = 0
        failed_count = 0

        for index, track in enumerate(tracks, start=1):
            if not track.file_path or not Path(track.file_path).exists():
                missing_count += 1
                continue

            try:
                duration_seconds = read_duration_seconds(track.file_path)
            except Exception as error:
                failed_count += 1
                print(f"Failed to read duration for {track.file_path}: {error}")
                continue

            if duration_seconds is None:
                failed_count += 1
                continue

            track.duration_seconds = float(duration_seconds)
            updated_count += 1

            if index % batch_size == 0:
                db.commit()
                print(f"Processed {index}/{len(tracks)} tracks...")

        db.commit()
        print(
            f"Backfilled durations for {updated_count} tracks "
            f"({missing_count} missing files, {failed_count} unreadable)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    backfill_durations()
