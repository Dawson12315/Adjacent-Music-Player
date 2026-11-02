from datetime import datetime, timedelta
import logging
import time
from typing import Dict, List, Optional

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
from app.models.artist_lastfm_check import ArtistLastfmCheck
from app.models.artist_lastfm_similarity import ArtistLastfmSimilarity
from app.models.track_genre import TrackGenre
from app.utils.artist_normalization import normalize_artist_name
from app.services.job_locking import JobHeartbeat

logger = logging.getLogger(__name__)

# A failed lookup is retried after this long, not nightly.
RETRY_FAILED_AFTER = timedelta(days=7)

# On a Last.fm rate limit: wait, double, and give up for the night after a run of them.
RATE_LIMIT_BACKOFF_SECONDS = 30
RATE_LIMIT_BACKOFF_MAX_SECONDS = 600
RATE_LIMIT_GIVE_UP_AFTER = 5

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
    logger.info("\n=== LAST.FM ENRICHMENT STOP REQUESTED ===")

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


# Similar artists are asked for per artist, once, and an artist Last.fm had
# nothing for is asked again after this long.
ARTIST_RETRY_AFTER = timedelta(days=30)
# Tracks enriched before tag weights were recorded are asked again, this
# many per nightly run, after everything new has been done — about ten
# minutes at the rate limit, so it never crowds out real enrichment.
WEIGHT_BACKFILL_PER_RUN = 500


def _rate_limited(result: Dict) -> bool:
    if result.get("rate_limited"):
        return True
    for key in ("reason", "error"):
        value = str(result.get(key) or "").casefold()
        if value == "rate_limited" or "rate limit" in value:
            return True
    return False


def _library_artist_names(db) -> Dict[str, str]:
    """Every credited artist in the library: normalised key → a display name."""
    names: Dict[str, str] = {}
    for (name,) in db.query(TrackArtist.artist_name).distinct():
        key = normalize_artist_name(name or "")
        if key and key not in names:
            names[key] = name
    for (name,) in db.query(Track.artist).filter(Track.artist.isnot(None)).distinct():
        key = normalize_artist_name(name or "")
        if key and key not in names:
            names[key] = name
    return names


def artists_needing_similarity(db, now: Optional[datetime] = None) -> List[tuple]:
    """(key, name) for every library artist with no similar-artist rows and no
    recent answer from Last.fm, so one run covers the whole library's artists
    rather than only those of the tracks it happened to enrich."""
    now = now or datetime.utcnow()
    have = {key for (key,) in db.query(ArtistLastfmSimilarity.source_artist_key).distinct()}
    checked = {row.artist_key: row.checked_at for row in db.query(ArtistLastfmCheck).all()}
    todo = []
    for key, name in _library_artist_names(db).items():
        if key in have:
            continue
        last = checked.get(key)
        if last is not None and last > now - ARTIST_RETRY_AFTER:
            continue
        todo.append((key, name))
    return sorted(todo)


def _record_artist_check(db, key: str, name: str, similar_count: int) -> None:
    row = db.get(ArtistLastfmCheck, key)
    if row is None:
        row = ArtistLastfmCheck(artist_key=key, artist_name=name)
        db.add(row)
    row.artist_name = name
    row.checked_at = datetime.utcnow()
    row.similar_count = int(similar_count or 0)
    db.commit()


def run_artist_similarity_phase(db, heartbeat=None, stop=should_stop) -> Dict:
    """Similar artists for every artist in the library, before the track walk.

    The track walk only reached an artist through an unenriched track, so a
    library enriched before similarity existed — or one whose walk is still
    weeks from finishing — had neighbours for a handful of artists. This is
    one call per artist, about ten minutes for five hundred.
    """
    todo = artists_needing_similarity(db)
    ingested = skipped = 0
    consecutive = 0
    backoff = RATE_LIMIT_BACKOFF_SECONDS
    stopped = None
    for key, name in todo:
        if heartbeat is not None:
            heartbeat.tick()
        if stop():
            stopped = "stopped"
            break
        try:
            result = ingest_similar_artists_for_artist(db=db, artist_name=name, limit=SIMILAR_ARTIST_LIMIT)
        except Exception as error:  # noqa: BLE001
            db.rollback()
            result = {"success": False, "reason": "lastfm_artist_similarity_failed", "error": str(error)}
        if result.get("reason") == "missing_api_key":
            stopped = "missing_api_key"
            break
        if _rate_limited(result):
            consecutive += 1
            skipped += 1
            if consecutive >= RATE_LIMIT_GIVE_UP_AFTER:
                logger.warning("Last.fm keeps rate-limiting the artist phase; stopping after %s in a row", consecutive)
                stopped = "rate_limited"
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, RATE_LIMIT_BACKOFF_MAX_SECONDS)
            continue
        consecutive = 0
        backoff = RATE_LIMIT_BACKOFF_SECONDS
        _record_artist_check(db, key, name, result.get("stored_count", 0) if result.get("success") else 0)
        if result.get("success"):
            ingested += 1
        else:
            skipped += 1
    return {"artists_considered": len(todo), "artists_ingested": ingested, "artists_skipped": skipped, "stopped": stopped}


def tracks_needing_tag_weights(db, limit: int = WEIGHT_BACKFILL_PER_RUN) -> List[Track]:
    unlabelled = db.query(TrackGenre.track_id).filter(TrackGenre.source.is_(None))
    return (
        db.query(Track)
        .filter(
            Track.lastfm_tags_enriched.is_(True),
            Track.musicbrainz_recording_id.isnot(None),
            Track.id.in_(unlabelled),
        )
        .order_by(Track.id.asc())
        .limit(limit)
        .all()
    )


def run_tag_weight_backfill(db, heartbeat=None, stop=should_stop, limit: int = WEIGHT_BACKFILL_PER_RUN) -> Dict:
    """Weights for tags written before weights were recorded.

    Asks Last.fm again for a bounded number of already-enriched tracks; the
    enrichment fills in weights for the tags it recognises, and whatever is
    left unlabelled is marked legacy so the track is not asked again.
    """
    tracks = tracks_needing_tag_weights(db, limit)
    weighted = skipped = 0
    consecutive = 0
    backoff = RATE_LIMIT_BACKOFF_SECONDS
    stopped = None
    for track in tracks:
        if heartbeat is not None:
            heartbeat.tick()
        if stop():
            stopped = "stopped"
            break
        try:
            result = enrich_track_lastfm_tags(db, track.id)
        except Exception as error:  # noqa: BLE001
            db.rollback()
            result = {"success": False, "reason": "lastfm_tag_enrichment_failed", "error": str(error)}
        if result.get("reason") == "missing_api_key":
            stopped = "missing_api_key"
            break
        if _rate_limited(result):
            consecutive += 1
            if consecutive >= RATE_LIMIT_GIVE_UP_AFTER:
                stopped = "rate_limited"
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, RATE_LIMIT_BACKOFF_MAX_SECONDS)
            continue
        consecutive = 0
        backoff = RATE_LIMIT_BACKOFF_SECONDS
        db.query(TrackGenre).filter(TrackGenre.track_id == track.id, TrackGenre.source.is_(None)).update(
            {"source": "legacy"}, synchronize_session=False
        )
        db.commit()
        if result.get("success"):
            weighted += 1
        else:
            skipped += 1
    return {"tracks_considered": len(tracks), "tracks_weighted": weighted, "tracks_skipped": skipped, "stopped": stopped}


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

    total_tracks_to_process = (
        db.query(Track)
        .filter(
            Track.musicbrainz_recording_id.isnot(None),
            Track.lastfm_tags_enriched.is_(False),
        )
        .count()
    )
    
    reset_stop()
    start_progress(total_tracks=total_tracks_to_process)
    heartbeat = JobHeartbeat("lastfm_enrichment")

    # Paged by id, so a run walks the whole library once. Selecting "the
    # first fifty unenriched" every time stopped the run dead after fifty
    # tracks Last.fm had nothing for.
    last_id = 0
    retry_before = datetime.utcnow() - RETRY_FAILED_AFTER
    consecutive_rate_limits = 0
    backoff_seconds = RATE_LIMIT_BACKOFF_SECONDS
    artist_phase: Dict = {}
    weight_backfill: Dict = {}

    try:
        # Artists first: the whole library's similar-artist graph is a few
        # hundred calls, and the map and radio lean on it more than on any
        # one track's tags.
        artist_phase = run_artist_similarity_phase(db, heartbeat)
        logger.info("[lastfm artist phase] %s", artist_phase)
        if artist_phase.get("stopped") in ("rate_limited", "missing_api_key"):
            summary = _stop_summary(0, 0, 0, 0, artist_phase.get("artists_ingested", 0), artist_phase.get("artists_skipped", 0), 0, 0)
            summary["artist_phase"] = artist_phase
            return summary
        attempted_artist_keys.update(
            key for key, in db.query(ArtistLastfmCheck.artist_key).filter(
                ArtistLastfmCheck.checked_at > datetime.utcnow() - ARTIST_RETRY_AFTER
            )
        )
        total_artist_similarity_ingested += artist_phase.get("artists_ingested", 0)
        total_artist_similarity_skipped += artist_phase.get("artists_skipped", 0)

        while True:
            tracks = (
                db.query(Track)
                .filter(
                    Track.musicbrainz_recording_id.isnot(None),
                    Track.lastfm_tags_enriched.is_(False),
                    Track.id > last_id,
                    (Track.lastfm_checked_at.is_(None))
                    | (Track.lastfm_checked_at < retry_before),
                )
                .order_by(Track.id.asc())
                .limit(BATCH_SIZE)
                .all()
            )

            if not tracks:
                break

            last_id = tracks[-1].id

            batch_number += 1
            logger.info(f"\n=== LAST.FM BATCH {batch_number} ({len(tracks)} tracks) ===\n")

            for index, track in enumerate(tracks, start=1):
                heartbeat.tick()
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
                    consecutive_rate_limits = 0
                    backoff_seconds = RATE_LIMIT_BACKOFF_SECONDS
                elif result.get("reason") == "rate_limited":
                    # Back off, doubling each time; a real throttle is not
                    # "no tags", and continuing at full rate makes it worse.
                    consecutive_rate_limits += 1
                    total_skipped += 1

                    if consecutive_rate_limits >= RATE_LIMIT_GIVE_UP_AFTER:
                        logger.warning(
                            "Last.fm keeps rate-limiting; stopping this run after %s in a row",
                            consecutive_rate_limits,
                        )
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

                    time.sleep(backoff_seconds)
                    backoff_seconds = min(backoff_seconds * 2, RATE_LIMIT_BACKOFF_MAX_SECONDS)
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
                    logger.info(
                        f"[lastfm track similarity] "
                        f"id={track.id} | "
                        f"title={track.title} | "
                        f"stored={track_similarity_result.get('stored_count', 0)}"
                    )
                else:
                    total_track_similarity_skipped += 1
                    logger.info(
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
                        _record_artist_check(db, normalized_artist_key, artist_name, similarity_result.get("stored_count", 0))
                        logger.info(
                            f"[lastfm artist similarity] "
                            f"artist={artist_name} | "
                            f"stored={similarity_result.get('stored_count', 0)}"
                        )
                    else:
                        total_artist_similarity_skipped += 1
                        logger.info(
                            f"[lastfm artist similarity] "
                            f"artist={artist_name} | "
                            f"result={similarity_result.get('reason', 'failed')}"
                        )

                update_progress(
                    current_batch=batch_number,
                    current_index=index,
                    current_total=len(tracks),
                    total_tracks=total_tracks_to_process,
                    processed_tracks=total_checked,
                    total_checked=total_checked,
                    total_processed=total_processed,
                    total_skipped=total_skipped,
                    current_track_id=track.id,
                    current_title=track.title,
                    last_result=result["reason"],
                )

                logger.info(
                    f"[lastfm batch {batch_number} | {index}/{len(tracks)}] "
                    f"id={track.id} | "
                    f"title={track.title} | "
                    f"result={result['reason']} | "
                    f"source={result.get('lastfm_source', 'none')} | "
                    f"added={len(result.get('added_genres', []))}"
                )

            time.sleep(BATCH_DELAY_SECONDS)

        # Everything new is done: spend a bounded slice on weights for the
        # tags written before weights were recorded.
        weight_backfill = run_tag_weight_backfill(db, heartbeat)
        logger.info("[lastfm weight backfill] %s", weight_backfill)

        summary = {
            "stopped": False,
            "artist_phase": artist_phase,
            "weight_backfill": weight_backfill,
            "batches_processed": batch_number,
            "total_checked": total_checked,
            "total_processed": total_processed,
            "total_skipped": total_skipped,
            "total_artist_similarity_ingested": total_artist_similarity_ingested,
            "total_artist_similarity_skipped": total_artist_similarity_skipped,
            "total_track_similarity_ingested": total_track_similarity_ingested,
            "total_track_similarity_skipped": total_track_similarity_skipped,
        }

        logger.info("\n=== LAST.FM FINAL SUMMARY ===")
        logger.info(summary)

        finish_progress()
        return summary

    finally:
        db.close()