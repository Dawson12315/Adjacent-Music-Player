from app.db import SessionLocal
from app.models.track import Track
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist,
    normalize_title,
)


def normalize_existing_metadata():
    db = SessionLocal()
    try:
        tracks = db.query(Track).all()
        updated_count = 0

        for track in tracks:
            normalized_title = normalize_title(track.raw_title or track.title)
            normalized_artist = normalize_artist(track.raw_artist or track.artist)
            normalized_album = normalize_album(track.raw_album or track.album)

            changed = False

            if track.title != normalized_title:
                track.title = normalized_title
                changed = True

            if track.artist != normalized_artist:
                track.artist = normalized_artist
                changed = True

            if track.album != normalized_album:
                track.album = normalized_album
                changed = True

            if changed:
                updated_count += 1

        db.commit()
        print(f"Normalized {updated_count} tracks.")
    finally:
        db.close()


if __name__ == "__main__":
    normalize_existing_metadata()