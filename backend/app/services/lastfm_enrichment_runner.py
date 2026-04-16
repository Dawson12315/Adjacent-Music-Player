import threading

from app.services.lastfm_enrichment_batch import run_lastfm_enrichment
from app.services.lastfm_enrichment_progress import get_progress


_lastfm_thread = None


def is_lastfm_enrichment_running() -> bool:
    progress = get_progress()
    return progress.get("is_running", False) or progress.get("is_stopping", False)


def start_lastfm_enrichment_background() -> bool:
    global _lastfm_thread

    if is_lastfm_enrichment_running():
        return False

    _lastfm_thread = threading.Thread(
        target=run_lastfm_enrichment,
        daemon=True,
    )
    _lastfm_thread.start()
    return True