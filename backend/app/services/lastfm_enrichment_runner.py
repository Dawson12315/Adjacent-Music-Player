import logging
import threading

from app.db import SessionLocal
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.lastfm_enrichment_batch import run_lastfm_enrichment
from app.services.lastfm_enrichment_progress import get_progress



logger = logging.getLogger(__name__)

_lastfm_thread = None
LASTFM_ENRICHMENT_LOCK_NAME = "lastfm_enrichment"


def is_lastfm_enrichment_running() -> bool:
    progress = get_progress()
    return progress.get("is_running", False) or progress.get("is_stopping", False)


def run_lastfm_enrichment_with_lock() -> bool:
    db = SessionLocal()

    try:
        # Decided before the try/finally below: a failed acquire must not fall
        # through to a release that would unlock the run that owns the lock.
        if not try_acquire_job_lock(db, LASTFM_ENRICHMENT_LOCK_NAME):
            logger.warning("Last.fm enrichment skipped: already running")
            return False

        try:
            logger.info("Running Last.fm enrichment...")
            run_lastfm_enrichment()
            return True
        except Exception as error:
            logger.warning(f"Last.fm enrichment error: {error}")
            return False
        finally:
            try:
                release_job_lock(db, LASTFM_ENRICHMENT_LOCK_NAME)
            except Exception:
                pass
    finally:
        db.close()


def start_lastfm_enrichment_background() -> bool:
    global _lastfm_thread

    if is_lastfm_enrichment_running():
        return False

    _lastfm_thread = threading.Thread(
        target=run_lastfm_enrichment_with_lock,
        daemon=True,
    )
    _lastfm_thread.start()
    return True