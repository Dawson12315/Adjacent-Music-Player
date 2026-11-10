"""Watch the music folder and import new files as they land.

The nightly scan walks the whole library; this is the other half of
"scan library for new files": a watcher on the folder that notices a file
arriving and hands its folder to the same scanner, so a new album is in the
library seconds after the copy finishes instead of the next morning.

How it is put together:

- `watchfiles` (the Rust notify watcher: inotify on Linux, FSEvents on macOS)
  reports the changes. It ships in the server image already.
- The watcher never imports anything itself. It collects the folders that
  changed, waits for a quiet period and for every file to stop growing, and
  starts a *scoped* scan of those folders through the background runner —
  the same code path, lock, progress and cache invalidation as every scan.
  A whole album copied in is one import, not one per file.
- Deleted files are ignored. Cleanup owns removal, with its grace period and
  its safety limit; a disappearing file is more often an unmounted share
  than an intention.
- Network filesystems (CIFS, NFS, SSHFS) only report writes made through
  that mount, never the ones another machine makes on the share, so on
  those the watcher polls instead. So does a watcher whose native events
  fail to start (inotify's per-user watch limit, for one).
- Events only cover the time the watcher was running, so a normal
  incremental scan catches up when it starts: at once when the setting is
  turned on, a minute after boot when it already was.

One watcher per process; the server is already required to be one process.
"""

import logging
import os
import threading
import time
from pathlib import Path

from app.config import settings as config
from app.services.scan_runner import start_scan_background
from app.services.lyrics_files import is_sidecar_name
from app.services.scanner import is_excluded_path
from app.utils.files import is_supported_audio_file

logger = logging.getLogger(__name__)

# How long the folder must be quiet after the last change before importing.
QUIET_SECONDS = 8.0
# How long every pending file must keep its size and mtime before it counts
# as finished copying.
SETTLE_SECONDS = 2.0
# How long to wait before trying again when another scan holds the lock.
RETRY_SECONDS = 15.0
# Past this many changed folders the import is simply a full scan.
MAX_SCOPED_FOLDERS = 50
# watchfiles' own batching of raw events.
DEBOUNCE_MS = 1600
DEFAULT_POLL_SECONDS = 120
MIN_POLL_SECONDS = 15
CATCH_UP_DELAY_AT_BOOT = 60.0
SCAN_LIMIT = 100000
ERROR_BACKOFF_SECONDS = (30.0, 60.0, 120.0, 300.0, 600.0)

# Filesystem types whose kernel driver cannot see writes made elsewhere.
NETWORK_FILESYSTEMS = {
    "cifs",
    "smb3",
    "smbfs",
    "nfs",
    "nfs4",
    "sshfs",
    "fuse.sshfs",
    "davfs",
    "fuse.davfs2",
    "afpfs",
    "9p",
    "fuse.rclone",
    "glusterfs",
    "ceph",
    "fuse.ceph",
    "fuse.gcsfuse",
    "fuse.s3fs",
    "lustre",
}


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested on their own)
# ---------------------------------------------------------------------------


def _truthy(value) -> bool:
    return bool(value) and str(value).strip().lower() not in {
        "",
        "0",
        "false",
        "no",
        "off",
        "disable",
        "disabled",
    }


def poll_seconds() -> int:
    """The polling interval, from FOLDER_WATCH_POLL_SECONDS when set."""
    raw = os.environ.get("FOLDER_WATCH_POLL_SECONDS")
    try:
        value = int(raw) if raw else DEFAULT_POLL_SECONDS
    except ValueError:
        value = DEFAULT_POLL_SECONDS
    return max(MIN_POLL_SECONDS, value)


def _unescape_mount(field: str) -> str:
    # /proc/mounts escapes space, tab, newline and backslash as octal.
    return (
        field.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def mount_type_for(path: str, mounts_text: str) -> str | None:
    """The filesystem type of the mount holding `path`, read from the text
    of /proc/mounts: the longest mount point that is a prefix of the path."""
    target = os.path.abspath(path)
    best = None
    best_length = -1
    for line in mounts_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        mount_point = _unescape_mount(parts[1])
        fstype = parts[2]
        if mount_point == "/":
            covers = True
        else:
            covers = target == mount_point or target.startswith(mount_point.rstrip("/") + "/")
        if covers and len(mount_point) > best_length:
            best, best_length = fstype, len(mount_point)
    return best


def is_network_filesystem(fstype: str | None) -> bool:
    if not fstype:
        return False
    lowered = fstype.lower()
    return lowered in NETWORK_FILESYSTEMS or lowered.startswith(("nfs", "cifs", "smb"))


def decide_mode(library: str) -> tuple[str, str]:
    """("events" | "polling", why)."""
    if _truthy(os.environ.get("WATCHFILES_FORCE_POLLING")):
        return "polling", "WATCHFILES_FORCE_POLLING is set"
    try:
        with open("/proc/mounts", encoding="utf-8") as handle:
            fstype = mount_type_for(library, handle.read())
    except OSError:
        fstype = None
    if is_network_filesystem(fstype):
        return "polling", f"the library is on a {fstype} mount, which only reports its own writes"
    return "events", fstype or "local filesystem"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def under_library(path: str, library: str) -> Path | None:
    """The changed path spelled under the configured library path, or None
    when it is not inside the library.

    Watchers report real paths — on macOS /var/… comes back as
    /private/var/…, and a library reached through a symlink comes back
    resolved — while the scanner stores paths exactly as the library is
    configured. The two have to agree, or a watch import and the nightly
    scan would store the same file twice."""
    root = Path(library)
    candidate = Path(path)
    if _is_within(candidate, root):
        return candidate
    try:
        real_root = Path(os.path.realpath(library))
        real_candidate = Path(os.path.realpath(path))
    except OSError:
        return None
    if not _is_within(real_candidate, real_root):
        return None
    return root / real_candidate.relative_to(real_root)


def relevant_change(path: str, library: str) -> bool:
    """Whether a changed path is worth an import: a music file, or a folder
    (a folder moved into the library arrives as one event for the folder,
    with nothing said about the files inside), and not somewhere the scan
    skips — recycle bins, caches, hidden folders, resource forks."""
    root = Path(library)
    candidate = under_library(path, library)
    if candidate is None or candidate == root:
        return False
    parts = candidate.relative_to(root).parts
    if is_excluded_path(parts):
        return False
    if is_supported_audio_file(candidate):
        return True
    # A lyrics file arriving beside a track is a change to that track.
    if is_sidecar_name(candidate):
        return True
    if candidate.is_dir():
        # The folder's own name has to pass the folder rules too; the
        # exclusion check reads the last part as a file name.
        return not is_excluded_path(parts + ("_",))
    return False


def folders_for(paths, library: str) -> list[str] | None:
    """The folders a scoped scan should walk for these changed paths.

    None means walk the whole library: a change right at the root, or more
    folders than a scoped walk is worth. An empty list means nothing is left
    to walk (everything pointed outside the library)."""
    root = Path(library)
    folders: set[Path] = set()
    for raw in paths:
        candidate = under_library(raw, library)
        if candidate is None:
            continue
        folder = candidate if candidate.is_dir() else candidate.parent
        if folder == root:
            return None
        folders.add(folder)

    ordered = sorted(folders, key=lambda folder: len(folder.parts))
    kept: list[Path] = []
    for folder in ordered:
        if any(_is_within(folder, parent) for parent in kept):
            continue
        kept.append(folder)
    if len(kept) > MAX_SCOPED_FOLDERS:
        return None
    return [str(folder) for folder in kept]


_MISSING = object()


def _fingerprint(path: str):
    """(size, mtime_ns) for a file, None for a folder, _MISSING when gone."""
    try:
        stat = os.stat(path)
    except OSError:
        return _MISSING
    if os.path.isdir(path):
        return None
    return (stat.st_size, stat.st_mtime_ns)


def _short(error: BaseException) -> str:
    text = str(error) or error.__class__.__name__
    return text[:200]


# ---------------------------------------------------------------------------
# Status, read by /scan/progress
# ---------------------------------------------------------------------------

_status_guard = threading.Lock()
_status = {
    "enabled": False,
    "mode": None,          # "events" | "polling"
    "reason": None,        # why that mode
    "state": "stopped",    # "stopped" | "starting" | "watching" | "error"
    "since": None,
    "last_event_at": None,
    "last_import_at": None,
    "last_added": None,
    "pending": 0,
    "error": None,
    "poll_seconds": None,
}


def _set(**changes):
    with _status_guard:
        _status.update(changes)


def get_watch_status() -> dict:
    with _status_guard:
        return dict(_status)


# ---------------------------------------------------------------------------
# The watcher thread
# ---------------------------------------------------------------------------


class _Watcher(threading.Thread):
    def __init__(self, library: str, *, quiet=None, settle=None, retry=None):
        super().__init__(name="folder-watch", daemon=True)
        self.library = library
        self.stop_event = threading.Event()
        self.quiet = QUIET_SECONDS if quiet is None else quiet
        self.settle = SETTLE_SECONDS if settle is None else settle
        self.retry = RETRY_SECONDS if retry is None else retry

    def stop(self):
        self.stop_event.set()

    def _current(self) -> bool:
        # A watcher that was replaced must not write over its successor's status.
        return _watcher is self

    def _report(self, **changes):
        if self._current():
            _set(**changes)

    def run(self):
        mode, reason = decide_mode(self.library)
        failures = 0
        while not self.stop_event.is_set():
            try:
                self._watch(mode, reason)
                break  # the generator only ends when a stop was asked for
            except Exception as error:  # noqa: BLE001
                if self.stop_event.is_set():
                    break
                if mode == "events":
                    logger.warning(
                        "Folder watch cannot use file events (%s); checking the folder every %s s instead",
                        _short(error),
                        poll_seconds(),
                    )
                    mode, reason = "polling", f"file events were not available ({_short(error)})"
                    continue
                failures += 1
                wait = ERROR_BACKOFF_SECONDS[min(failures, len(ERROR_BACKOFF_SECONDS)) - 1]
                logger.warning("Folder watch stopped (%s); trying again in %s s", _short(error), wait)
                self._report(state="error", error=_short(error), pending=0)
                self.stop_event.wait(wait)
        self._report(state="stopped", pending=0)

    def _watch(self, mode: str, reason: str):
        import watchfiles

        library = self.library
        poll = poll_seconds()
        self._report(
            mode=mode,
            reason=reason,
            state="starting",
            error=None,
            poll_seconds=poll if mode == "polling" else None,
        )

        # path -> fingerprint (None for a folder); the files and folders
        # waiting to be imported.
        pending: dict = {}
        last_event = 0.0
        next_try = 0.0
        started = False

        def accept(_change, path):
            return relevant_change(path, library)

        changes_stream = watchfiles.watch(
            library,
            watch_filter=accept,
            debounce=DEBOUNCE_MS,
            step=50,
            stop_event=self.stop_event,
            # Wake once a second with an empty set, so the quiet period can
            # run out without another event arriving.
            rust_timeout=1000,
            yield_on_timeout=True,
            force_polling=(mode == "polling"),
            poll_delay_ms=poll * 1000,
            recursive=True,
            ignore_permission_denied=True,
            raise_interrupt=False,
        )

        for changes in changes_stream:
            if not started:
                started = True
                self._report(state="watching", since=time.time())
            if self.stop_event.is_set():
                return

            now = time.monotonic()
            for change, path in changes:
                if change == watchfiles.Change.deleted:
                    pending.pop(path, None)
                    continue
                fingerprint = _fingerprint(path)
                if fingerprint is _MISSING:
                    pending.pop(path, None)
                    continue
                pending[path] = fingerprint
                last_event = now
            if changes:
                self._report(last_event_at=time.time(), pending=len(pending))

            if not pending or now < next_try or now - last_event < self.quiet:
                continue
            if not self._settled(pending):
                # Something was still being written; start the quiet period over.
                last_event = time.monotonic()
                self._report(pending=len(pending))
                continue

            within = folders_for(list(pending), library)
            if within == []:
                pending.clear()
                self._report(pending=0)
                continue

            result = start_scan_background(
                limit=SCAN_LIMIT, within=within, source="watch", on_done=self._imported
            )
            if result["started"]:
                logger.info(
                    "Folder watch: importing %s",
                    "the whole library" if within is None else f"{len(within)} folder(s)",
                )
                pending.clear()
                self._report(pending=0)
            else:
                # Another scan holds the lock; keep what is pending and try again.
                next_try = time.monotonic() + self.retry

    def _settled(self, pending: dict) -> bool:
        """Whether every pending file has held its size and mtime still for
        the settle window. Refreshes the fingerprints as it goes and drops
        files that have vanished (a temp file renamed away)."""
        if not self._refresh(pending):
            return False
        if self.stop_event.wait(self.settle):
            return False
        return self._refresh(pending)

    @staticmethod
    def _refresh(pending: dict) -> bool:
        stable = True
        for path, before in list(pending.items()):
            if before is None:
                continue
            after = _fingerprint(path)
            if after is _MISSING:
                pending.pop(path, None)
            elif after != before:
                pending[path] = after
                stable = False
        return stable

    def _imported(self, outcome: dict):
        self._report(last_import_at=time.time(), last_added=outcome.get("added"))
        if outcome.get("ok"):
            logger.info("Folder watch: import finished, %s added", outcome.get("added"))
        else:
            logger.warning("Folder watch: import failed: %s", outcome.get("error"))


# ---------------------------------------------------------------------------
# Lifecycle, driven by the setting
# ---------------------------------------------------------------------------

_manager_guard = threading.Lock()
_watcher: _Watcher | None = None
_catch_up: threading.Timer | None = None


def _read_enabled() -> bool:
    from app.db import SessionLocal
    from app.models.app_setting import AppSetting

    db = SessionLocal()
    try:
        row = db.query(AppSetting).first()
        return bool(row and row.watch_enabled)
    except Exception:  # noqa: BLE001
        logger.warning("Could not read the folder watch setting", exc_info=True)
        return False
    finally:
        db.close()


def _run_catch_up():
    if not get_watch_status()["enabled"]:
        return
    result = start_scan_background(limit=SCAN_LIMIT, source="watch-catch-up")
    logger.info("Folder watch catch-up scan: %s", result["reason"])


def sync_folder_watch(*, enabled: bool | None = None, at_boot: bool = False) -> dict:
    """Start or stop the watcher to match the setting (read from the database
    when `enabled` is not given). Returns the status."""
    global _watcher, _catch_up

    if enabled is None:
        enabled = _read_enabled()

    with _manager_guard:
        running = _watcher is not None and _watcher.is_alive()
        _set(enabled=bool(enabled))

        if enabled and not running:
            _watcher = _Watcher(config.music_library_path)
            _watcher.start()
            if _catch_up is not None:
                _catch_up.cancel()
            _catch_up = threading.Timer(CATCH_UP_DELAY_AT_BOOT if at_boot else 0.0, _run_catch_up)
            _catch_up.daemon = True
            _catch_up.start()
            logger.info("Folder watch on: %s", config.music_library_path)
        elif not enabled and running:
            if _catch_up is not None:
                _catch_up.cancel()
                _catch_up = None
            _watcher.stop()
            _watcher = None
            _set(state="stopped", pending=0, error=None)
            logger.info("Folder watch off")

    return get_watch_status()


def stop_folder_watch() -> None:
    sync_folder_watch(enabled=False)
