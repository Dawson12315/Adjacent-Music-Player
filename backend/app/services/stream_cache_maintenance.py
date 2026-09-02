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

# Identity-based sweeping only removes entries nothing could read. It does not
# bound *valid* growth: any authenticated user can ask for every quality of
# every track (8 renditions each), so the caches can reach several times the
# library size and fill the data volume — which is also where the database
# lives. Past this budget the least-recently-used entries are evicted;
# eviction is safe by construction because a missing cache entry is simply
# rebuilt on the next request.
CACHE_BUDGET_BYTES = 20 * 1024 * 1024 * 1024  # 20 GB across both caches

# Below this much free space on the data volume, refuse new transcodes rather
# than fill the disk out from under SQLite/Postgres.
MIN_FREE_DISK_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB


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

    evicted = _enforce_cache_budget()
    removed_files += evicted["files"]
    removed_dirs += evicted["dirs"]
    reclaimed_bytes += evicted["bytes"]

    result = {
        "swept": True,
        "removed_files": removed_files,
        "removed_hls_dirs": removed_dirs,
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 1),
        "evicted_for_budget": evicted["files"] + evicted["dirs"],
    }
    logger.info("Stream cache sweep: %s", result)
    return result


def _cache_entries() -> list[tuple[float, int, Path, bool]]:
    """(atime, size, path, is_dir) for every cache entry, oldest use first."""
    entries: list[tuple[float, int, Path, bool]] = []

    if MOBILE_CACHE_DIR.exists():
        for entry in MOBILE_CACHE_DIR.iterdir():
            if not entry.is_file():
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            entries.append((stat.st_atime, stat.st_size, entry, False))

    if HLS_CACHE_ROOT.exists():
        for entry in HLS_CACHE_ROOT.iterdir():
            if not entry.is_dir():
                continue
            try:
                children = [c for c in entry.rglob("*") if c.is_file()]
                size = sum(c.stat().st_size for c in children)
                # A directory's own atime does not move when its segments are
                # read, so use the newest child access as the entry's age.
                atime = max((c.stat().st_atime for c in children), default=0.0)
            except OSError:
                continue
            entries.append((atime, size, entry, True))

    entries.sort(key=lambda item: item[0])
    return entries


def _enforce_cache_budget() -> dict:
    """Evict least-recently-used entries until the caches fit the budget."""
    entries = _cache_entries()
    total = sum(size for _, size, _, _ in entries)

    removed = {"files": 0, "dirs": 0, "bytes": 0}

    if total <= CACHE_BUDGET_BYTES:
        return removed

    logger.info(
        "Transcode caches at %.1f GB exceed the %.1f GB budget; evicting oldest",
        total / (1024**3),
        CACHE_BUDGET_BYTES / (1024**3),
    )

    for _atime, size, path, is_dir in entries:
        if total <= CACHE_BUDGET_BYTES:
            break

        try:
            if is_dir:
                shutil.rmtree(path, ignore_errors=True)
                removed["dirs"] += 1
            else:
                path.unlink()
                removed["files"] += 1
        except OSError:
            continue

        removed["bytes"] += size
        total -= size

    return removed


def has_room_for_transcode() -> bool:
    """False when the data volume is too full to safely write a new entry."""
    try:
        usage = shutil.disk_usage(MOBILE_CACHE_DIR.parent)
    except OSError:
        # Cannot tell — do not block playback on a stat failure.
        return True

    return usage.free >= MIN_FREE_DISK_BYTES


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
