"""Maintenance for the mobile/HLS transcode caches.

Cache entries embed a fingerprint of the source file (path + mtime + size),
so an entry can never be *wrong* — but nothing removes entries whose track or
file has gone away, or files written by older cache-naming schemes. Left
alone, the caches only ever grow (a real install had accumulated 10.6 GB,
most of it unreachable). The sweeper deletes anything that no current track
could ever read.
"""

import logging
import re
import shutil
import threading
from pathlib import Path

from app.db import SessionLocal
from app.models.track import Track

logger = logging.getLogger(__name__)

MOBILE_CACHE_DIR = Path("data/mobile_cache")
HLS_CACHE_ROOT = Path("data/hls_cache")

# Current naming: track_{id}_{fingerprint12}_{quality}_{version}{ext}
_MOBILE_NAME_PATTERN = re.compile(r"^track_(\d+)_([0-9a-f]{12})_.+")
# Current naming: track_{id}_{fingerprint12}
_HLS_DIR_PATTERN = re.compile(r"^track_(\d+)_([0-9a-f]{12})$")

_sweep_guard = threading.Lock()
_sweep_thread: threading.Thread | None = None


def clear_stream_caches() -> None:
    """Remove everything. Used by purge, where all tracks are gone anyway."""
    for cache_dir in (MOBILE_CACHE_DIR, HLS_CACHE_ROOT):
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Cleared stream caches")


def _valid_identities() -> set[tuple[int, str]] | None:
    """(track_id, fingerprint) pairs a cache entry may legitimately carry.

    Returns None when the library volume looks unmounted — files that merely
    cannot be stat'ed right now are not stale, and sweeping on a dead mount
    would throw away every valid entry's identity check.
    """
    from app.routes.tracks import source_fingerprint

    db = SessionLocal()
    try:
        rows = db.query(Track.id, Track.file_path).all()
    finally:
        db.close()

    if not rows:
        return set()

    identities: set[tuple[int, str]] = set()
    missing = 0

    for track_id, file_path_text in rows:
        file_path = Path(file_path_text)
        try:
            if not file_path.exists():
                missing += 1
                continue
            identities.add((track_id, source_fingerprint(file_path)))
        except OSError:
            missing += 1

    if missing > len(rows) * 0.9:
        logger.warning(
            "Stream cache sweep skipped: %s/%s library files unreachable — "
            "is the volume mounted?",
            missing,
            len(rows),
        )
        return None

    return identities


def sweep_stream_caches() -> dict:
    identities = _valid_identities()

    if identities is None:
        return {"swept": False, "reason": "library_unreachable"}

    removed_files = 0
    removed_dirs = 0
    reclaimed_bytes = 0

    if MOBILE_CACHE_DIR.exists():
        for entry in MOBILE_CACHE_DIR.iterdir():
            if not entry.is_file():
                continue

            match = _MOBILE_NAME_PATTERN.match(entry.name)
            keep = bool(
                match and (int(match.group(1)), match.group(2)) in identities
            )

            if keep:
                continue

            try:
                reclaimed_bytes += entry.stat().st_size
                entry.unlink()
                removed_files += 1
            except OSError:
                pass

    if HLS_CACHE_ROOT.exists():
        for entry in HLS_CACHE_ROOT.iterdir():
            if not entry.is_dir():
                continue

            match = _HLS_DIR_PATTERN.match(entry.name)
            keep = bool(
                match and (int(match.group(1)), match.group(2)) in identities
            )

            if keep:
                continue

            reclaimed_bytes += sum(
                child.stat().st_size
                for child in entry.rglob("*")
                if child.is_file()
            )
            shutil.rmtree(entry, ignore_errors=True)
            removed_dirs += 1

    result = {
        "swept": True,
        "removed_files": removed_files,
        "removed_hls_dirs": removed_dirs,
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 1),
    }
    logger.info("Stream cache sweep: %s", result)
    return result


def start_stream_cache_sweep_background() -> bool:
    """The sweep stats every library file, which can take minutes over a
    network mount — never run it on a request thread."""
    global _sweep_thread

    with _sweep_guard:
        if _sweep_thread is not None and _sweep_thread.is_alive():
            return False

        _sweep_thread = threading.Thread(
            target=sweep_stream_caches,
            name="stream-cache-sweep",
            daemon=True,
        )
        _sweep_thread.start()
        return True
