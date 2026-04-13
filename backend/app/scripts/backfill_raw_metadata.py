from mutagen import File
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.track import Track


def _first_tag_value(tags, keys):
    if not tags:
        return None

    for key in keys:
        value = tags.get(key)
        if value is None:
            continue

        if isinstance(value, list) and value:
            return str(value[0]).strip() or None

        text = str(value).strip()
        if text:
            return text

    return None


def read_metadata(file_path: str):
    audio = File(file_path, easy=True)

    if not audio:
        return {
            "title": None,
            "artist": None,
            "album": None,
        }

    tags = audio.tags or {}

    return {
        "title": _first_tag_value(tags, ["title"]),
        "artist": _first_tag_value(tags, ["artist", "albumartist"]),
        "album": _first_tag_value(tags, ["album"]),
    }


def backfill_raw_metadata(db: Session):
    tracks = db.query(Track).all()
    updated_count = 0

    for track in tracks:
        current_raw_title = (track.raw_title or "").strip()
        current_raw_artist = (track.raw_artist or "").strip()
        current_raw_album = (track.raw_album or "").strip()

        if current_raw_title and current_raw_artist and current_raw_album:
            continue

        metadata = read_metadata(track.file_path)

        track.raw_title = metadata["title"] or track.title or ""
        track.raw_artist = metadata["artist"] or track.artist or ""
        track.raw_album = metadata["album"] or track.album or ""

        updated_count += 1

    db.commit()
    return updated_count


def main():
    db = SessionLocal()
    try:
        updated_count = backfill_raw_metadata(db)
        print(f"Backfilled raw metadata for {updated_count} tracks.")
    finally:
        db.close()


if __name__ == "__main__":
    main()