import threading

from app.services.musicbrainz_backfill import backfill_musicbrainz_recording_ids


_mbid_backfill_thread = None
_mbid_backfill_lock = threading.Lock()


def is_musicbrainz_backfill_running() -> bool:
    global _mbid_backfill_thread

    return _mbid_backfill_thread is not None and _mbid_backfill_thread.is_alive()


def _run_musicbrainz_backfill():
    global _mbid_backfill_thread

    try:
        backfill_musicbrainz_recording_ids()
    finally:
        with _mbid_backfill_lock:
            _mbid_backfill_thread = None


def start_musicbrainz_backfill_background() -> bool:
    global _mbid_backfill_thread

    with _mbid_backfill_lock:
        if _mbid_backfill_thread is not None and _mbid_backfill_thread.is_alive():
            return False

        _mbid_backfill_thread = threading.Thread(
            target=_run_musicbrainz_backfill,
            daemon=True,
        )
        _mbid_backfill_thread.start()
        return True