from app.db import SessionLocal
from app.models.track import Track
from app.services.musicbrainz import find_recording_mbid


TRACK_ID_TO_TEST = 1


def main():
    db = SessionLocal()

    try:
        track = db.query(Track).filter(Track.id == TRACK_ID_TO_TEST).first()

        if not track:
            print(f"Track {TRACK_ID_TO_TEST} not found.")
            return

        print("Before:")
        print(f"id={track.id}")
        print(f"title={track.title}")
        print(f"artist={track.artist}")
        print(f"musicbrainz_recording_id={track.musicbrainz_recording_id}")
        print()

        mbid = find_recording_mbid(track.title, track.artist)

        print(f"Lookup result: {mbid}")
        print()

        if not mbid:
            print("No MBID found. Nothing saved.")
            return

        track.musicbrainz_recording_id = mbid
        db.commit()
        db.refresh(track)

        print("After:")
        print(f"id={track.id}")
        print(f"title={track.title}")
        print(f"artist={track.artist}")
        print(f"musicbrainz_recording_id={track.musicbrainz_recording_id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()