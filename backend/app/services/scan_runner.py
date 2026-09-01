"""Background runner for library scans.

A full import walks tens of thousands of files over what is often a network
mount. Running that inside the HTTP request meant the scan button blocked for
up to an hour with no feedback, died with the connection, and left the job
lock stuck. The scan now runs in a daemon thread and reports progress the same
way Last.fm enrichment does.
"""

import logging
import threading
import time

from app.config import settings
from app.db import SessionLocal
from app.services.job_locking import release_job_lock, try_acquire_job_lock
from app.services.scanner import scan_directory

logger = logging.getLogger(__name__)

_runner_guard = threading.Lock()
_scan_thread: threading.Thread | None = None

_progress_guard = threading.Lock()
_progress = {
    "is_running": False,
    "files_seen": 0,
    "added": 0,
    "last_result": None,   # "completed" | "error" | None
    "error": None,
    "started_at": None,
    "finished_at": None,
}


def _update_progress(**changes):
    with _progress_guard:
        _progress.update(changes)


def get_scan_progress() -> dict:
    with _progress_guard:
        return dict(_progress)


def is_scan_running() -> bool:
    with _runner_guard:
        return _scan_thread is not None and _scan_thread.is_alive()


def start_scan_background(limit: int) -> dict:
    """Returns {"started": bool, "reason": str}."""
    global _scan_thread

    with _runner_guard:
        if _scan_thread is not None and _scan_thread.is_alive():
            return {"started": False, "reason": "already_running"}

        db = SessionLocal()
        try:
            if not try_acquire_job_lock(db, "scan"):
                return {"started": False, "reason": "already_running"}
        finally:
            db.close()

        _update_progress(
            is_running=True,
            files_seen=0,
            added=0,
            last_result=None,
            error=None,
            started_at=time.time(),
            finished_at=None,
        )

        _scan_thread = threading.Thread(
            target=_run_scan,
            args=(limit,),
            name="library-scan",
            daemon=True,
        )
        _scan_thread.start()

    return {"started": True, "reason": "started"}


def _run_scan(limit: int):
    def on_progress(files_seen: int, added: int):
        _update_progress(files_seen=files_seen, added=added)

    try:
        result = scan_directory(
            settings.music_library_path,
            limit=limit,
            progress_callback=on_progress,
        )
        _update_progress(added=result["added"], last_result="completed")
        logger.info("Background scan finished: %s tracks added", result["added"])
    except ValueError as error:
        # Unmounted or misconfigured library path.
        _update_progress(last_result="error", error=str(error))
        logger.warning("Background scan refused: %s", error)
    except Exception:
        _update_progress(last_result="error", error="Scan failed — see the server log.")
        logger.exception("Background scan failed")
    finally:
        _update_progress(is_running=False, finished_at=time.time())

        db = SessionLocal()
        try:
            release_job_lock(db, "scan")
        finally:
            db.close()
