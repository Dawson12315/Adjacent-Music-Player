from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist_list,
    normalize_primary_artist,
    normalize_title,
)


def normalize_existing_metadata():
    db = SessionLocal()
    try:
        tracks = db.query(Track).all()
        updated_count = 0

        for index, track in enumerate(tracks, start=1):
            source_artist = track.raw_artist or track.artist

            normalized_title = normalize_title(track.raw_title or track.title)
            normalized_artist = normalize_primary_artist(source_artist)
            normalized_album = normalize_album(track.raw_album or track.album)
            normalized_artist_list = normalize_artist_list(source_artist)

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

            db.query(TrackArtist).filter(
                TrackArtist.track_id == track.id
            ).delete(synchronize_session=False)

            for artist_position, artist_name in enumerate(normalized_artist_list):
                db.add(
                    TrackArtist(
                        track_id=track.id,
                        artist_name=artist_name,
                        position=artist_position,
                    )
                )

            if changed:
                updated_count += 1

            if index % 250 == 0:
                db.commit()
                print(f"Processed {index} tracks...")

        db.commit()
        print(f"Normalized {updated_count} tracks.")
    finally:
        db.close()


if __name__ == "__main__":
    normalize_existing_metadata()