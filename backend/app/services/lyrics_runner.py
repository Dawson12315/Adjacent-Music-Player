"""The queue of tracks waiting for lyrics, and the thread that works it.

Requests come from two places: a person opening the lyrics panel on a track
that has none (served first), and the nightly job, which adds the most-played
tracks still without words. One track at a time, under the "lyrics" job lock
and a background transcode slot, so a listener's stream always has the CPU
first; the model work itself runs on a bounded number of threads.

Progress is in memory and polled by the clients, the same shape as the scan
and the Last.fm job. A failure is remembered per track for a while so the
client can say why, then forgotten so it can be tried again.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime

from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_lyrics import TrackLyrics
from app.services import lyrics_engine
from app.services.job_locking import JobHeartbeat, release_job_lock, try_acquire_job_lock

logger = logging.getLogger(__name__)

# How long a failure is shown for before the track may be asked for again.
FAILURE_MEMORY_SECONDS = 15 * 60
# The nightly job adds this many tracks at most.
NIGHTLY_BATCH = 40
# And works for at most this long before standing down until tomorrow.
NIGHTLY_BUDGET_SECONDS = 2 * 60 * 60
# When the transcode pool is full, wait this long before trying the track again.
BUSY_RETRY_SECONDS = 20

_guard = threading.Lock()
_queue: deque[int] = deque()
_queued: set[int] = set()
_failures: dict[int, tuple[float, str]] = {}
_thread: threading.Thread | None = None
_stop = threading.Event()

_progress = {
    "is_running": False,
    "current_track_id": None,
    "queued": 0,
    "done": 0,
    "failed": 0,
    "started_at": None,
    "finished_at": None,
    "last_error": None,
    "model": None,
}


def _set(**changes):
    with _guard:
        _progress.update(changes)
        _progress["queued"] = len(_queue)


def get_progress() -> dict:
    with _guard:
        return {**_progress, "queued": len(_queue), "available": lyrics_engine.transcriber_available()}


def generation_settings() -> tuple[bool, str]:
    """(enabled, model) from the settings row."""
    db = SessionLocal()
    try:
        row = db.query(AppSetting).first()
        enabled = bool(row and getattr(row, "lyrics_generation_enabled", False))
        model = (row and getattr(row, "lyrics_model", None)) or lyrics_engine.DEFAULT_LYRICS_MODEL
        return enabled, model if model in lyrics_engine.LYRICS_MODELS else lyrics_engine.DEFAULT_LYRICS_MODEL
    finally:
        db.close()


def track_generation_status(track_id: int, enabled: bool | None = None) -> dict:
    """What a client may expect for this track: {"state", "reason"}.

    States: unsupported (no model on this server), off (the admin switch),
    queued, running, failed (with the reason), available.
    """
    if not lyrics_engine.transcriber_available():
        return {"state": "unsupported", "reason": "This server cannot generate lyrics."}
    if enabled is None:
        enabled, _model = generation_settings()
    if not enabled:
        return {"state": "off", "reason": "Lyrics generation is turned off in Settings."}
    with _guard:
        if _progress["current_track_id"] == track_id and _progress["is_running"]:
            return {"state": "running", "reason": None}
        if track_id in _queued:
            return {"state": "queued", "reason": None}
        failure = _failures.get(track_id)
        if failure and time.time() - failure[0] < FAILURE_MEMORY_SECONDS:
            return {"state": "failed", "reason": failure[1]}
    return {"state": "available", "reason": None}


def request_generation(track_id: int, *, front: bool = True) -> dict:
    """Put a track on the queue (at the front for a person waiting) and make
    sure the worker is running. Returns the track's status afterwards."""
    enabled, _model = generation_settings()
    if not lyrics_engine.transcriber_available():
        return track_generation_status(track_id, enabled=False) | {"state": "unsupported"}
    if not enabled:
        return track_generation_status(track_id, enabled=False)
    with _guard:
        _failures.pop(track_id, None)
        if track_id not in _queued and _progress["current_track_id"] != track_id:
            _queued.add(track_id)
            if front:
                _queue.appendleft(track_id)
            else:
                _queue.append(track_id)
    _ensure_worker()
    return track_generation_status(track_id, enabled=True)


def enqueue_nightly() -> int:
    """The most-played tracks without lyrics, up to the nightly batch."""
    from sqlalchemy import func

    from app.models.track_user_stats import TrackUserStats

    enabled, _model = generation_settings()
    if not enabled or not lyrics_engine.transcriber_available():
        return 0
    db = SessionLocal()
    try:
        plays = func.coalesce(func.sum(TrackUserStats.play_count), 0)
        rows = (
            db.query(Track.id)
            .outerjoin(TrackLyrics, TrackLyrics.track_id == Track.id)
            .outerjoin(TrackUserStats, TrackUserStats.track_id == Track.id)
            .filter(TrackLyrics.id.is_(None), Track.missing_since.is_(None))
            .group_by(Track.id)
            .order_by(plays.desc(), Track.id.asc())
            .limit(NIGHTLY_BATCH)
            .all()
        )
    finally:
        db.close()
    added = 0
    with _guard:
        for (track_id,) in rows:
            failure = _failures.get(track_id)
            if failure and time.time() - failure[0] < FAILURE_MEMORY_SECONDS:
                continue
            if track_id not in _queued:
                _queued.add(track_id)
                _queue.append(track_id)
                added += 1
    if added:
        _ensure_worker(budget_seconds=NIGHTLY_BUDGET_SECONDS)
    return added


def _ensure_worker(budget_seconds: float | None = None):
    global _thread
    with _guard:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_work, args=(budget_seconds,), name="lyrics-generation", daemon=True)
        _thread.start()


def stop_worker():
    _stop.set()


def _pop() -> int | None:
    with _guard:
        while _queue:
            track_id = _queue.popleft()
            _queued.discard(track_id)
            return track_id
    return None


def _work(budget_seconds: float | None):
    db = SessionLocal()
    try:
        if not try_acquire_job_lock(db, "lyrics"):
            logger.info("Lyrics generation skipped: another run holds the lock")
            return
    finally:
        db.close()

    heartbeat = JobHeartbeat("lyrics")
    started = time.monotonic()
    _set(is_running=True, started_at=time.time(), finished_at=None, done=0, failed=0, last_error=None)
    try:
        while not _stop.is_set():
            if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                logger.info("Lyrics generation: nightly budget spent; the rest waits for tomorrow")
                with _guard:
                    _queue.clear()
                    _queued.clear()
                break
            track_id = _pop()
            if track_id is None:
                break
            _set(current_track_id=track_id)
            heartbeat.tick()
            outcome = _generate_one(track_id)
            if outcome == "busy":
                # Put it back and wait for the pool.
                with _guard:
                    _queue.appendleft(track_id)
                    _queued.add(track_id)
                _set(current_track_id=None)
                _stop.wait(BUSY_RETRY_SECONDS)
                continue
            with _guard:
                if outcome == "ok":
                    _progress["done"] += 1
                else:
                    _progress["failed"] += 1
    finally:
        _set(is_running=False, current_track_id=None, finished_at=time.time())
        db = SessionLocal()
        try:
            release_job_lock(db, "lyrics")
        finally:
            db.close()


def _generate_one(track_id: int) -> str:
    """Generate for one track. Returns "ok", "failed" or "busy"."""
    from fastapi import HTTPException

    from app.routes.tracks import transcode_slot

    enabled, model_name = generation_settings()
    if not enabled:
        return "failed"
    _set(model=model_name)

    db = SessionLocal()
    try:
        track = db.query(Track).filter(Track.id == track_id).first()
        if track is None:
            return "failed"
        existing = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
        # Known words with no timing: time them. Anything else with a
        # synced text already has what generation would give it.
        known_text = None
        if existing is not None:
            if existing.synced:
                return "ok"
            known_text = existing.plain
        file_path = track.file_path
    finally:
        db.close()

    try:
        with transcode_slot(f"lyrics for track {track_id}", foreground=False):
            result = lyrics_engine.generate(file_path, model_name=model_name, known_text=known_text)
    except HTTPException as error:
        if error.status_code == 503:
            return "busy"
        return _fail(track_id, str(error.detail))
    except Exception as error:  # noqa: BLE001
        logger.exception("Lyrics generation failed for track %s", track_id)
        message = str(error)
        if "huggingface" in message.lower() or "download" in message.lower() or "connection" in message.lower():
            message = "The lyrics model could not be downloaded. The server needs internet access once to fetch it."
        return _fail(track_id, message[:200] or "Lyrics generation failed.")

    if not result.get("ok"):
        return _fail(track_id, result.get("reason") or "Lyrics generation failed.")

    db = SessionLocal()
    try:
        row = db.query(TrackLyrics).filter(TrackLyrics.track_id == track_id).first()
        now = datetime.utcnow()
        if result["kind"] == "aligned" and row is not None:
            row.synced = _dump(result["synced"])
            row.synced_source = "aligned"
            row.model = result["model"]
            row.confidence = result["confidence"]
            row.language = row.language or result.get("language")
            row.updated_at = now
        else:
            if row is None:
                row = TrackLyrics(track_id=track_id, created_at=now)
                db.add(row)
            row.source = "transcribed"
            row.synced_source = "transcribed"
            row.plain = result["plain"]
            row.synced = _dump(result["synced"])
            row.model = result["model"]
            row.confidence = result["confidence"]
            row.language = result.get("language")
            row.updated_at = now
        db.commit()
    finally:
        db.close()
    logger.info("Lyrics %s for track %s (%s)", result["kind"], track_id, model_name)
    return "ok"


def _fail(track_id: int, reason: str) -> str:
    with _guard:
        _failures[track_id] = (time.time(), reason)
        _progress["last_error"] = reason
    logger.info("Lyrics for track %s not generated: %s", track_id, reason)
    return "failed"


def _dump(synced) -> str:
    import json

    return json.dumps(synced, ensure_ascii=False)
