from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.filename_metadata import extract_metadata_from_filename
from app.services.metadata_normalizer import (
    normalize_album,
    normalize_artist_list,
    normalize_primary_artist,
    normalize_title,
)


def main():
    db = SessionLocal()
    updated = 0

    try:
        tracks = db.query(Track).all()

        for track in tracks:
            raw_title = track.raw_title or None
            raw_artist = track.raw_artist or None
            raw_album = track.raw_album or None

            filename_artist, filename_album, filename_title = extract_metadata_from_filename(
                track.file_path
            )

            use_filename_title = False

            if not raw_title:
                use_filename_title = True
            elif " - " in raw_title and filename_title:
                use_filename_title = True

            resolved_title = normalize_title(
                filename_title if use_filename_title else raw_title or track.title
            )
            source_artist = raw_artist or filename_artist
            resolved_artist = normalize_primary_artist(source_artist)
            resolved_artist_list = normalize_artist_list(source_artist)
            resolved_album = normalize_album(raw_album or filename_album)

            changed = False

            if track.title != resolved_title:
                track.title = resolved_title
                changed = True

            if track.artist != resolved_artist:
                track.artist = resolved_artist
                changed = True

            if track.album != resolved_album:
                track.album = resolved_album
                changed = True

            db.query(TrackArtist).filter(TrackArtist.track_id == track.id).delete()

            for index, artist_name in enumerate(resolved_artist_list):
                db.add(
                    TrackArtist(
                        track_id=track.id,
                        artist_name=artist_name,
                        position=index,
                    )
                )

            if changed:
                updated += 1

        db.commit()
        print(f"Updated {updated} tracks.")
    finally:
        db.close()


if __name__ == "__main__":
    main()