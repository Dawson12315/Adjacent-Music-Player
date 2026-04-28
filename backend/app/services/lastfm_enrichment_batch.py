import time
from typing import Dict

from app.db import SessionLocal
from app.models.track import Track
from app.models.track_artist import TrackArtist
from app.services.lastfm_artist_similarity import ingest_similar_artists_for_artist
from app.services.lastfm_enrichment import enrich_track_lastfm_tags
from app.services.lastfm_enrichment_control import should_stop, reset_stop
from app.services.lastfm_enrichment_progress import (
    finish_progress,
    mark_stopped,
    mark_stopping,
    start_progress,
    update_progress,
)
from app.services.lastfm_track_similarity import ingest_similar_tracks_for_track
from app.utils.artist_normalization import normalize_artist_name


BATCH_SIZE = 25
BATCH_DELAY_SECONDS = 2.0
SIMILAR_ARTIST_LIMIT = 25
SIMILAR_TRACK_LIMIT = 25


def _collect_track_artists(db, track: Track) -> list[str]:
    artist_names: list[str] = []

    if track.artist and track.artist.strip():
        artist_names.append(track.artist.strip())

    track_artist_rows = (
        db.query(TrackArtist)
        .filter(TrackArtist.track_id == track.id)
        .order_by(TrackArtist.position.asc())
        .all()
    )

    for row in track_artist_rows:
        if row.artist_name and row.artist_name.strip():
            artist_names.append(row.artist_name.strip())

    deduped: list[str] = []
    seen_keys: set[str] = set()

    for artist_name in artist_names:
        normalized_key = normalize_artist_name(artist_name)
        if not normalized_key or normalized_key in seen_keys:
            continue

        seen_keys.add(normalized_key)
        deduped.append(artist_name)

    return deduped


def _stop_summary(
    batch_number: int,
    total_checked: int,
    total_processed: int,
    total_skipped: int,
    total_artist_similarity_ingested: int,
    total_artist_similarity_skipped: int,
    total_track_similarity_ingested: int,
    total_track_similarity_skipped: int,
) -> Dict:
    mark_stopping()
    print("\n=== LAST.FM ENRICHMENT STOP REQUESTED ===")

    summary = {
        "stopped": True,
        "batches_processed": batch_number,
        "total_checked": total_checked,
        "total_processed": total_processed,
        "total_skipped": total_skipped,
        "total_artist_similarity_ingested": total_artist_similarity_ingested,
        "total_artist_similarity_skipped": total_artist_similarity_skipped,
        "total_track_similarity_ingested": total_track_similarity_ingested,
        "total_track_similarity_skipped": total_track_similarity_skipped,
    }

    mark_stopped()
    return summary


def run_lastfm_enrichment() -> Dict:
    db = SessionLocal()

    total_checked = 0
    total_processed = 0
    total_skipped = 0
    total_artist_similarity_ingested = 0
    total_artist_similarity_skipped = 0
    total_track_similarity_ingested = 0
    total_track_similarity_skipped = 0
    batch_number = 0
    attempted_track_ids = set()
    attempted_artist_keys = set()

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
                    return _stop_summary(
                        batch_number,
                        total_checked,
                        total_processed,
                        total_skipped,
                        total_artist_similarity_ingested,
                        total_artist_similarity_skipped,
                        total_track_similarity_ingested,
                        total_track_similarity_skipped,
                    )

                attempted_track_ids.add(track.id)

                try:
                    result = enrich_track_lastfm_tags(db, track.id)
                except Exception as error:
                    db.rollback()
                    result = {
                        "success": False,
                        "reason": "lastfm_tag_enrichment_failed",
                        "error": str(error),
                        "added_genres": [],
                    }

                total_checked += 1

                if result["success"]:
                    total_processed += 1
                else:
                    total_skipped += 1

                if should_stop():
                    return _stop_summary(
                        batch_number,
                        total_checked,
                        total_processed,
                        total_skipped,
                        total_artist_similarity_ingested,
                        total_artist_similarity_skipped,
                        total_track_similarity_ingested,
                        total_track_similarity_skipped,
                    )

                try:
                    track_similarity_result = ingest_similar_tracks_for_track(
                        db=db,
                        track_id=track.id,
                        limit=SIMILAR_TRACK_LIMIT,
                    )
                except Exception as error:
                    db.rollback()
                    track_similarity_result = {
                        "success": False,
                        "reason": "lastfm_track_similarity_failed",
                        "error": str(error),
                    }

                if track_similarity_result["success"]:
                    total_track_similarity_ingested += 1
                    print(
                        f"[lastfm track similarity] "
                        f"id={track.id} | "
                        f"title={track.title} | "
                        f"stored={track_similarity_result.get('stored_count', 0)}"
                    )
                else:
                    total_track_similarity_skipped += 1
                    print(
                        f"[lastfm track similarity] "
                        f"id={track.id} | "
                        f"title={track.title} | "
                        f"result={track_similarity_result.get('reason', 'failed')}"
                    )

                if should_stop():
                    return _stop_summary(
                        batch_number,
                        total_checked,
                        total_processed,
                        total_skipped,
                        total_artist_similarity_ingested,
                        total_artist_similarity_skipped,
                        total_track_similarity_ingested,
                        total_track_similarity_skipped,
                    )

                track_artists = _collect_track_artists(db, track)

                for artist_name in track_artists:
                    if should_stop():
                        return _stop_summary(
                            batch_number,
                            total_checked,
                            total_processed,
                            total_skipped,
                            total_artist_similarity_ingested,
                            total_artist_similarity_skipped,
                            total_track_similarity_ingested,
                            total_track_similarity_skipped,
                        )

                    normalized_artist_key = normalize_artist_name(artist_name)

                    if not normalized_artist_key:
                        total_artist_similarity_skipped += 1
                        continue

                    if normalized_artist_key in attempted_artist_keys:
                        total_artist_similarity_skipped += 1
                        continue

                    attempted_artist_keys.add(normalized_artist_key)

                    try:
                        similarity_result = ingest_similar_artists_for_artist(
                            db=db,
                            artist_name=artist_name,
                            limit=SIMILAR_ARTIST_LIMIT,
                        )
                    except Exception as error:
                        db.rollback()
                        similarity_result = {
                            "success": False,
                            "reason": "lastfm_artist_similarity_failed",
                            "error": str(error),
                        }

                    if similarity_result["success"]:
                        total_artist_similarity_ingested += 1
                        print(
                            f"[lastfm artist similarity] "
                            f"artist={artist_name} | "
                            f"stored={similarity_result.get('stored_count', 0)}"
                        )
                    else:
                        total_artist_similarity_skipped += 1
                        print(
                            f"[lastfm artist similarity] "
                            f"artist={artist_name} | "
                            f"result={similarity_result.get('reason', 'failed')}"
                        )

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

            time.sleep(BATCH_DELAY_SECONDS)

        summary = {
            "stopped": False,
            "batches_processed": batch_number,
            "total_checked": total_checked,
            "total_processed": total_processed,
            "total_skipped": total_skipped,
            "total_artist_similarity_ingested": total_artist_similarity_ingested,
            "total_artist_similarity_skipped": total_artist_similarity_skipped,
            "total_track_similarity_ingested": total_track_similarity_ingested,
            "total_track_similarity_skipped": total_track_similarity_skipped,
        }

        print("\n=== LAST.FM FINAL SUMMARY ===")
        print(summary)

        finish_progress()
        return summary

    finally:
        db.close()