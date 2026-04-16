import time
from typing import Dict

from app.db import SessionLocal
from app.models.track import Track
from app.services.lastfm_enrichment import enrich_track_lastfm_tags
from app.services.lastfm_enrichment_control import should_stop, reset_stop
from app.services.lastfm_enrichment_control import should_stop, reset_stop
from app.services.lastfm_enrichment_progress import (
    finish_progress,
    mark_stopped,
    mark_stopping,
    start_progress,
    update_progress,
)


BATCH_SIZE = 25
REQUEST_DELAY_SECONDS = 1.1
BATCH_DELAY_SECONDS = 2.0


def run_lastfm_enrichment() -> Dict:
    db = SessionLocal()

    total_checked = 0
    total_processed = 0
    total_skipped = 0
    batch_number = 0
    attempted_track_ids = set()

    reset_stop()
    start_progress()

    try:
        while True:
            candidate_tracks = (
                db.query(Track)
                .filter(
                    Track.musicbrainz_recording_id.isnot(None),
                    Track.lastfm_tags_enriched.is_(False),
                )
                .limit(BATCH_SIZE * 2)
                .all()
            )

            tracks = [
                track for track in candidate_tracks
                if track.id not in attempted_track_ids
            ][:BATCH_SIZE]

            if not tracks:
                break

            batch_number += 1

            print(f"\n=== LAST.FM BATCH {batch_number} ({len(tracks)} tracks) ===\n")

            for index, track in enumerate(tracks, start=1):
                if should_stop():
                    mark_stopping()
                    print("\n=== LAST.FM ENRICHMENT STOP REQUESTED ===")
                    summary = {
                        "stopped": True,
                        "batches_processed": batch_number,
                        "total_checked": total_checked,
                        "total_processed": total_processed,
                        "total_skipped": total_skipped,
                    }
                    mark_stopped()
                    return summary

                attempted_track_ids.add(track.id)

                result = enrich_track_lastfm_tags(db, track.id)

                total_checked += 1

                if result["success"]:
                    total_processed += 1
                else:
                    total_skipped += 1

                update_progress(
                    current_batch=batch_number,
                    current_index=index,
                    current_total=len(tracks),
                    total_checked=total_checked,
                    total_processed=total_processed,
                    total_skipped=total_skipped,
                    current_track_id=track.id,
                    current_title=track.title,
                    last_result=result["reason"],
                )

                print(
                    f"[lastfm batch {batch_number} | {index}/{len(tracks)}] "
                    f"id={track.id} | "
                    f"title={track.title} | "
                    f"result={result['reason']} | "
                    f"source={result.get('lastfm_source', 'none')} | "
                    f"added={len(result.get('added_genres', []))}"
                )

                time.sleep(REQUEST_DELAY_SECONDS)

            time.sleep(BATCH_DELAY_SECONDS)

        summary = {
            "stopped": False,
            "batches_processed": batch_number,
            "total_checked": total_checked,
            "total_processed": total_processed,
            "total_skipped": total_skipped,
        }

        print("\n=== LAST.FM FINAL SUMMARY ===")
        print(summary)

        finish_progress()
        return summary

    finally:
        db.close()