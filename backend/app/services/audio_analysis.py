"""The queue of tracks waiting to be listened to, and the thread that works it.

Two things are measured per track, each only when it is missing: the sound
profile (services/audio_features.py, librosa) and the flags (services/
track_flags.py, Whisper). Requests come from the nightly job (the backlog,
most-played first), from a scan that found new files, and from a station
being started on a track nobody has listened to yet (served first). One
track at a time, under the "audio_analysis" job lock and a background
transcode slot, so a listener's stream always has the CPU first.

Progress is in memory and polled by the Settings card, the same shape as the
scan, the Last.fm job and lyrics generation.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from datetime import datetime

from sqlalchemy import func

from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.models.track import Track
from app.models.track_audio_profile import TrackAudioProfile
from app.services import audio_features, track_flags
from app.services.job_locking import JobHeartbeat, release_job_lock, try_acquire_job_lock

logger = logging.getLogger(__name__)

JOB_NAME = "audio_analysis"
DEFAULT_TIME = "03:30"
# The nightly job queues this many at most, and works for at most this long.
NIGHTLY_BATCH = 4000
NIGHTLY_BUDGET_SECONDS = 2 * 60 * 60
# After a scan: the newest files, for at most an hour, in the background slot.
AFTER_SCAN_BATCH = 500
AFTER_SCAN_BUDGET_SECONDS = 60 * 60
# When the transcode pool is full, wait this long before trying again.
BUSY_RETRY_SECONDS = 20
# A failure is remembered this long so the track is not retried every night.
FAILURE_MEMORY_SECONDS = 24 * 60 * 60

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
}


def _set(**changes):
    with _guard:
        _progress.update(changes)
        _progress["queued"] = len(_queue)


def get_progress() -> dict:
    with _guard:
        return {
            **_progress,
            "queued": len(_queue),
            "available": {"sound": audio_features.profiler_available(), "flags": track_flags.flags_available()},
        }


def analysis_settings() -> tuple[bool, str, str]:
    """(enabled, nightly time, lyrics model name) from the settings row."""
    from app.services import lyrics_engine

    db = SessionLocal()
    try:
        row = db.query(AppSetting).first()
        enabled = True if row is None else bool(getattr(row, "audio_analysis_enabled", True))
        at = (row and getattr(row, "audio_analysis_time", None)) or DEFAULT_TIME
        model = (row and getattr(row, "lyrics_model", None)) or lyrics_engine.DEFAULT_LYRICS_MODEL
        return enabled, at, model if model in lyrics_engine.LYRICS_MODELS else lyrics_engine.DEFAULT_LYRICS_MODEL
    finally:
        db.close()


def anything_to_measure_with() -> bool:
    return audio_features.profiler_available() or track_flags.flags_available()


def request_analysis(track_id: int, *, front: bool = True) -> bool:
    """Put a track on the queue (at the front for a station waiting on it)
    and make sure the worker is running. False when analysis is off."""
    enabled, _at, _model = analysis_settings()
    if not enabled or not anything_to_measure_with():
        return False
    with _guard:
        if track_id not in _queued and _progress["current_track_id"] != track_id:
            _queued.add(track_id)
            if front:
                _queue.appendleft(track_id)
            else:
                _queue.append(track_id)
    _ensure_worker()
    return True


def _needs_work_filter(query, want_sound: bool, want_flags: bool):
    """Tracks missing a current profile, or never listened to for flags."""
    conditions = []
    if want_sound:
        conditions.append(TrackAudioProfile.track_id.is_(None))
        conditions.append(TrackAudioProfile.version != audio_features.PROFILE_VERSION)
    if want_flags:
        conditions.append(Track.flags_checked_at.is_(None))
    from sqlalchemy import or_

    return query.filter(or_(*conditions)) if conditions else query.filter(False)


def enqueue_backlog(*, limit: int = NIGHTLY_BATCH, budget_seconds: float | None = NIGHTLY_BUDGET_SECONDS, newest_first: bool = False) -> int:
    """Queue the tracks still to be measured: most-played first (or newest
    first after a scan), up to `limit`, worked for at most `budget_seconds`."""
    from app.models.track_user_stats import TrackUserStats

    enabled, _at, _model = analysis_settings()
    want_sound = audio_features.profiler_available()
    want_flags = track_flags.flags_available()
    if not enabled or not (want_sound or want_flags):
        return 0
    db = SessionLocal()
    try:
        query = (
            db.query(Track.id)
            .outerjoin(TrackAudioProfile, TrackAudioProfile.track_id == Track.id)
            .outerjoin(TrackUserStats, TrackUserStats.track_id == Track.id)
            .filter(Track.missing_since.is_(None))
            .group_by(Track.id, TrackAudioProfile.version)
        )
        query = _needs_work_filter(query, want_sound, want_flags)
        if newest_first:
            query = query.order_by(Track.id.desc())
        else:
            plays = func.coalesce(func.sum(TrackUserStats.play_count), 0)
            query = query.order_by(plays.desc(), Track.id.asc())
        rows = query.limit(limit).all()
    finally:
        db.close()
    added = 0
    now = time.time()
    with _guard:
        for (track_id,) in rows:
            failure = _failures.get(track_id)
            if failure and now - failure[0] < FAILURE_MEMORY_SECONDS:
                continue
            if track_id not in _queued and _progress["current_track_id"] != track_id:
                _queued.add(track_id)
                _queue.append(track_id)
                added += 1
    if added:
        _ensure_worker(budget_seconds=budget_seconds)
    return added


def coverage(db) -> dict:
    """For the Settings card: how much of the library has been measured."""
    total = db.query(func.count(Track.id)).filter(Track.missing_since.is_(None)).scalar() or 0
    profiled = (
        db.query(func.count(TrackAudioProfile.track_id))
        .filter(TrackAudioProfile.version == audio_features.PROFILE_VERSION)
        .scalar()
        or 0
    )
    flagged = db.query(func.count(Track.id)).filter(Track.flags_checked_at.isnot(None), Track.missing_since.is_(None)).scalar() or 0
    vocal_counts = dict(
        db.query(Track.vocal_state, func.count(Track.id))
        .filter(Track.vocal_state.isnot(None), Track.missing_since.is_(None))
        .group_by(Track.vocal_state)
        .all()
    )
    languages = dict(
        db.query(Track.language, func.count(Track.id))
        .filter(Track.language.isnot(None), Track.missing_since.is_(None))
        .group_by(Track.language)
        .all()
    )
    explicit = db.query(func.count(Track.id)).filter(Track.explicit_state == track_flags.EXPLICIT).scalar() or 0
    return {
        "tracks": int(total),
        "profiled": int(profiled),
        "flagged": int(flagged),
        "vocal": int(vocal_counts.get(track_flags.VOCAL, 0)),
        "instrumental": int(vocal_counts.get(track_flags.INSTRUMENTAL, 0)),
        "languages": {str(code): int(count) for code, count in languages.items()},
        "explicit": int(explicit),
    }


def _ensure_worker(budget_seconds: float | None = None):
    global _thread
    with _guard:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_work, args=(budget_seconds,), name="audio-analysis", daemon=True)
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
        if not try_acquire_job_lock(db, JOB_NAME):
            logger.info("Audio analysis skipped: another run holds the lock")
            return
    finally:
        db.close()

    heartbeat = JobHeartbeat(JOB_NAME)
    started = time.monotonic()
    _set(is_running=True, started_at=time.time(), finished_at=None, done=0, failed=0, last_error=None)
    try:
        while not _stop.is_set():
            if budget_seconds is not None and time.monotonic() - started > budget_seconds:
                logger.info("Audio analysis: budget spent; the rest waits for the next run")
                with _guard:
                    _queue.clear()
                    _queued.clear()
                break
            track_id = _pop()
            if track_id is None:
                break
            _set(current_track_id=track_id)
            heartbeat.tick()
            outcome = _analyse_one(track_id)
            if outcome == "busy":
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
            release_job_lock(db, JOB_NAME)
        finally:
            db.close()
        # The map reads the profiles; a run that measured anything is worth
        # a rebuild so stations hear it tonight rather than tomorrow.
        with _guard:
            measured = _progress["done"] > 0
        if measured:
            try:
                from app.services.recommendations.vector_map import start_vector_rebuild_background

                start_vector_rebuild_background()
            except Exception:  # noqa: BLE001
                logger.warning("Could not start the map rebuild after audio analysis", exc_info=True)


def _analyse_one(track_id: int) -> str:
    """Measure one track. Returns "ok", "failed" or "busy"."""
    from fastapi import HTTPException

    from app.routes.tracks import transcode_slot

    enabled, _at, model_name = analysis_settings()
    if not enabled:
        return "failed"
    db = SessionLocal()
    try:
        track = db.query(Track).filter(Track.id == track_id).first()
        if track is None or track.missing_since is not None:
            return "failed"
        file_path = track.file_path
        duration = track.duration_seconds
        profile = db.query(TrackAudioProfile).filter(TrackAudioProfile.track_id == track_id).first()
        want_sound = audio_features.profiler_available() and (profile is None or profile.version != audio_features.PROFILE_VERSION)
        want_flags = track_flags.flags_available() and track.flags_checked_at is None and track.flags_set_by != track_flags.SET_BY_ADMIN
    finally:
        db.close()
    if not want_sound and not want_flags:
        return "ok"

    features = None
    flags = None
    try:
        with transcode_slot(f"audio analysis of track {track_id}", foreground=False):
            if want_sound:
                features = audio_features.profile_file(file_path, duration)
            if want_flags:
                flags = track_flags.detect(file_path, duration, model_name)
    except HTTPException as error:
        if error.status_code == 503:
            return "busy"
        return _fail(track_id, str(error.detail))
    except Exception as error:  # noqa: BLE001
        logger.warning("Audio analysis failed for track %s: %s", track_id, error)
        return _fail(track_id, str(error)[:200] or "Audio analysis failed.")

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        if features is not None:
            row = db.query(TrackAudioProfile).filter(TrackAudioProfile.track_id == track_id).first()
            if row is None:
                row = TrackAudioProfile(track_id=track_id, version=audio_features.PROFILE_VERSION, features=b"", feature_count=0)
                db.add(row)
            row.version = audio_features.PROFILE_VERSION
            row.features = audio_features.pack(features)
            row.feature_count = int(features.shape[0])
            row.built_at = now
        if flags is not None:
            track = db.query(Track).filter(Track.id == track_id).first()
            if track is not None:
                # Words on file outrank a thirty-second listen: a track with
                # lyrics is vocal, and its words say whether it is explicit.
                from app.models.track_lyrics import TrackLyrics

                plain = db.query(TrackLyrics.plain).filter(TrackLyrics.track_id == track_id).scalar()
                detected = {k: v for k, v in flags.items() if k != "words"}
                if plain and plain.strip():
                    detected["vocal_state"] = track_flags.VOCAL
                    detected["explicit_state"] = track_flags.explicit_from_text(plain)
                track_flags.apply_detected(db, track, **detected)
        db.commit()
    finally:
        db.close()
    return "ok"


def _fail(track_id: int, reason: str) -> str:
    with _guard:
        _failures[track_id] = (time.time(), reason)
        _progress["last_error"] = reason
    return "failed"
