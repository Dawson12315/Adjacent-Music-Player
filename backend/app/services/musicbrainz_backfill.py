import time
from typing import Optional

from app.db import SessionLocal
from app.models.track import Track
from app.services.musicbrainz import find_recording_mbid


DEFAULT_BATCH_SIZE = 50
DEFAULT_REQUEST_DELAY_SECONDS = 1.25
DEFAULT_BATCH_DELAY_SECONDS = 2.0


def backfill_musicbrainz_recording_ids(
    batch_size: int = DEFAULT_BATCH_SIZE,
    request_delay_seconds: float = DEFAULT_REQUEST_DELAY_SECONDS,
    batch_delay_seconds: float = DEFAULT_BATCH_DELAY_SECONDS,
    max_batches: Optional[int] = None,
) -> dict:
    db = SessionLocal()

    total_checked = 0
    total_matched = 0
    total_missing = 0
    batch_number = 0

    try:
        while True:
            if max_batches is not None and batch_number >= max_batches:
                break

            tracks = (
                db.query(Track)
                .filter(Track.musicbrainz_recording_id.is_(None))
                .limit(batch_size)
                .all()
            )

            if not tracks:
                break

            batch_number += 1
            batch_matched = 0
            batch_missing = 0

            print(f"\n=== MBID BATCH {batch_number} ({len(tracks)} tracks) ===\n")

            for index, track in enumerate(tracks, start=1):
                mbid = find_recording_mbid(
                    track.title,
                    track.artist,
                    raw_title=track.raw_title,
                    raw_artist=track.raw_artist,
                )

                if mbid:
                    track.musicbrainz_recording_id = mbid
                    batch_matched += 1
                    total_matched += 1
                else:
                    batch_missing += 1
                    total_missing += 1

                total_checked += 1

                print(
                    f"[mbid batch {batch_number} | {index}/{len(tracks)}] "
                    f"id={track.id} | "
                    f"title={track.title} | "
                    f"artist={track.artist} | "
                    f"mbid={mbid}"
                )

                db.commit()
                time.sleep(request_delay_seconds)

            print(f"\n--- MBID BATCH {batch_number} SUMMARY ---")
            print(f"Checked: {len(tracks)}")
            print(f"Matched and saved: {batch_matched}")
            print(f"No match: {batch_missing}")

            time.sleep(batch_delay_seconds)

        summary = {
            "batches_processed": batch_number,
            "total_checked": total_checked,
            "total_matched": total_matched,
            "total_missing": total_missing,
        }

        print("\n=== MBID FINAL SUMMARY ===")
        print(summary)

        return summary

    finally:
        db.close()