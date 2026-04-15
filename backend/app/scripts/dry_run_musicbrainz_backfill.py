from app.db import SessionLocal
from app.models.track import Track
from app.services.musicbrainz import find_recording_mbid


BATCH_SIZE = 50


def main():
    db = SessionLocal()

    try:
        tracks = (
            db.query(Track)
            .filter(Track.musicbrainz_recording_id.is_(None))
            .limit(BATCH_SIZE)
            .all()
        )

        print(f"=== DRY RUN: MusicBrainz Backfill ({len(tracks)} tracks) ===\n")

        matched = 0
        missing = 0

        for track in tracks:
            mbid = find_recording_mbid(
                track.title,
                track.artist,
                raw_title=track.raw_title,
                raw_artist=track.raw_artist,
            )

            print(f"id={track.id}")
            print(f"title={track.title}")
            print(f"artist={track.artist}")
            print(f"raw_title={track.raw_title}")
            print(f"result_mbid={mbid}")
            print("-" * 50)

            if mbid:
                matched += 1
            else:
                missing += 1

        print("\n=== SUMMARY ===")
        print(f"Total checked: {len(tracks)}")
        print(f"Matched: {matched}")
        print(f"No match: {missing}")

    finally:
        db.close()


if __name__ == "__main__":
    main()