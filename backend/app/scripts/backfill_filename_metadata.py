"""Re-derive every track's title, artist, album and credits the way the
scanner would import it today.

Rows the old tag reader could not read properly — no artist, an artist that
is just a track position, or an .m4a/.mp4/.aac file — have their tags read
again from the file when it can be reached; every other row is resolved from
the tags it stored. The scanner does the same repair on its own during its
next walk; this script is for doing it now, in one go.

Genres are left alone (the Last.fm enrichment adds to them).
"""

from pathlib import Path

from app.config import settings
from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.metadata import extract_track_metadata
from app.services.scanner import _looks_misread
from app.services.track_resolution import resolve_track_fields


def main():
    db = SessionLocal()
    base_path = settings.music_library_path
    updated = 0
    reread = 0

    try:
        tracks = db.query(Track).all()

        for index, track in enumerate(tracks, start=1):
            metadata = {
                "title": track.raw_title,
                "artist": track.raw_artist,
                "album": track.raw_album,
                "genre": track.raw_genre,
                "track_number": track.track_number,
                "disc_number": track.disc_number,
            }

            if _looks_misread(track.artist, track.raw_artist, track.file_path) and Path(track.file_path).exists():
                try:
                    metadata = extract_track_metadata(track.file_path)
                    reread += 1
                except Exception as error:  # noqa: BLE001
                    print(f"Could not read {track.file_path}: {error}")

            fields = resolve_track_fields(metadata, track.file_path, base_path)

            changed = False
            for column in ("title", "artist", "album"):
                value = fields[column]
                if column == "title" and not value:
                    continue
                if getattr(track, column) != value:
                    setattr(track, column, value)
                    changed = True

            if metadata is not None and "raw_title" in fields:
                track.raw_title = fields["raw_title"]
                track.raw_artist = fields["raw_artist"]
                track.raw_album = fields["raw_album"]

            if fields["track_number"] and track.track_number != fields["track_number"]:
                track.track_number = fields["track_number"]
                changed = True
            if fields["disc_number"] and track.disc_number != fields["disc_number"]:
                track.disc_number = fields["disc_number"]
                changed = True

            db.query(TrackArtist).filter(TrackArtist.track_id == track.id).delete(synchronize_session=False)
            for position, artist_name in enumerate(fields["artists"]):
                db.add(TrackArtist(track_id=track.id, artist_name=artist_name, position=position))

            if changed:
                updated += 1

            if index % 250 == 0:
                db.commit()
                print(f"Processed {index} tracks...")

        db.commit()
        print(f"Updated {updated} tracks ({reread} re-read from their files).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
