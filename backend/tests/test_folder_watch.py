"""The folder watch: its helpers, the scoped scan it drives, the setting that
turns it on, and the real thing — a file landing in the watched folder and
turning up in the library without anyone pressing Scan."""

import shutil
import time
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "audio"


@pytest.fixture()
def admin(client):
    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )
    assert login.status_code == 200
    return client


def _delete_tracks_under(db_session_factory, prefix: str):
    from app.models.track import Track
    from app.models.track_artist import TrackArtist
    from app.models.track_genre import TrackGenre

    db = db_session_factory()
    try:
        ids = [row.id for row in db.query(Track.id).filter(Track.file_path.like(f"{prefix}%")).all()]
        if ids:
            db.query(TrackArtist).filter(TrackArtist.track_id.in_(ids)).delete(synchronize_session=False)
            db.query(TrackGenre).filter(TrackGenre.track_id.in_(ids)).delete(synchronize_session=False)
            db.query(Track).filter(Track.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_the_mount_holding_the_library_decides_events_or_polling():
    from app.services import folder_watch as fw

    mounts = "\n".join(
        [
            "sysfs /sys sysfs rw 0 0",
            "/dev/sda1 / ext4 rw 0 0",
            "//nas/music /mnt/nas\\040music cifs rw 0 0",
            "nas:/export/media /mnt/media nfs4 rw 0 0",
            "shfs /mnt/user fuse.shfs rw 0 0",
        ]
    )
    assert fw.mount_type_for("/music", mounts) == "ext4"
    assert fw.mount_type_for("/mnt/nas music/albums", mounts) == "cifs"
    assert fw.mount_type_for("/mnt/media", mounts) == "nfs4"
    # A prefix only counts at a path boundary.
    assert fw.mount_type_for("/mnt/mediafoo", mounts) == "ext4"
    # Unraid's user shares are FUSE on the box itself: real events.
    assert fw.mount_type_for("/mnt/user/media/music", mounts) == "fuse.shfs"

    for network in ("cifs", "nfs", "nfs4", "fuse.sshfs", "smb3"):
        assert fw.is_network_filesystem(network), network
    for local in ("ext4", "btrfs", "xfs", "fuse.shfs", "apfs", None):
        assert not fw.is_network_filesystem(local), local


def test_the_poll_interval_has_a_floor(monkeypatch):
    from app.services import folder_watch as fw

    monkeypatch.delenv("FOLDER_WATCH_POLL_SECONDS", raising=False)
    assert fw.poll_seconds() == fw.DEFAULT_POLL_SECONDS
    monkeypatch.setenv("FOLDER_WATCH_POLL_SECONDS", "600")
    assert fw.poll_seconds() == 600
    monkeypatch.setenv("FOLDER_WATCH_POLL_SECONDS", "1")
    assert fw.poll_seconds() == fw.MIN_POLL_SECONDS
    monkeypatch.setenv("FOLDER_WATCH_POLL_SECONDS", "soon")
    assert fw.poll_seconds() == fw.DEFAULT_POLL_SECONDS

    monkeypatch.setenv("WATCHFILES_FORCE_POLLING", "1")
    assert fw.decide_mode("/anywhere")[0] == "polling"
    monkeypatch.setenv("WATCHFILES_FORCE_POLLING", "false")
    # Falls through to the mount check; on a developer machine that is a local disk.
    mode, _why = fw.decide_mode(str(Path(__file__).parent))
    assert mode in ("events", "polling")


def test_only_music_and_folders_count_and_folders_collapse(tmp_path):
    from app.services import folder_watch as fw

    lib = tmp_path / "lib"
    album = lib / "Artist" / "Album"
    album.mkdir(parents=True)
    (lib / "#recycle" / "Old").mkdir(parents=True)
    (lib / ".hidden").mkdir()
    song = album / "01.flac"
    song.write_bytes(b"x")

    assert fw.relevant_change(str(song), str(lib))
    assert fw.relevant_change(str(album), str(lib)), "a folder moved in is one event for the folder"
    assert not fw.relevant_change(str(album / "cover.jpg"), str(lib))
    assert not fw.relevant_change(str(lib / "#recycle" / "Old" / "x.mp3"), str(lib))
    assert not fw.relevant_change(str(lib / "#recycle"), str(lib)), "the bin itself"
    assert not fw.relevant_change(str(lib / ".hidden"), str(lib))
    assert not fw.relevant_change(str(album / "._01.flac"), str(lib)), "a resource fork"
    assert not fw.relevant_change(str(tmp_path / "elsewhere.mp3"), str(lib))
    assert not fw.relevant_change(str(lib), str(lib))

    # Watchers report real paths; the library is spelled as configured.
    linked = tmp_path / "linked-lib"
    linked.symlink_to(lib)
    real_song = str(lib.resolve() / "Artist" / "Album" / "01.flac")
    assert fw.under_library(real_song, str(linked)) == linked / "Artist" / "Album" / "01.flac"
    assert fw.relevant_change(real_song, str(linked))
    assert fw.folders_for([real_song], str(linked)) == [str(linked / "Artist" / "Album")]
    assert fw.under_library(str(tmp_path / "elsewhere.mp3"), str(linked)) is None

    assert fw.folders_for([str(song)], str(lib)) == [str(album)]
    assert fw.folders_for([str(song), str(lib / "Artist")], str(lib)) == [str(lib / "Artist")]
    assert fw.folders_for([str(lib / "loose.mp3")], str(lib)) is None, "a change at the root: the whole library"
    assert fw.folders_for([str(tmp_path / "elsewhere.mp3")], str(lib)) == []

    many = []
    for index in range(fw.MAX_SCOPED_FOLDERS + 1):
        folder = lib / f"A{index}"
        folder.mkdir()
        many.append(str(folder / "x.mp3"))
    assert fw.folders_for(many, str(lib)) is None, "too many folders: the whole library"


# ---------------------------------------------------------------------------
# The scoped scan
# ---------------------------------------------------------------------------


def test_a_scoped_scan_walks_only_the_named_folders(client, db_session_factory, tmp_path, monkeypatch):
    from app.models.track import Track
    from app.services import scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)

    lib = tmp_path / "library"
    a = lib / "A"
    b = lib / "B" / "deeper"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    shutil.copy(FIXTURES / "tagged.mp3", a / "a-scoped.mp3")
    shutil.copy(FIXTURES / "tagged.flac", b / "b-scoped.flac")

    assert scanner.walk_roots(lib, None) == [lib]
    assert scanner.walk_roots(lib, [str(a), str(a), str(lib / "B"), str(b), str(tmp_path / "other")]) == [a, lib / "B"]
    assert scanner.walk_roots(lib, [str(tmp_path / "other")]) == []

    try:
        result = scanner.scan_directory(str(lib), limit=100, within=[str(a)])
        assert result["added"] == 1
        assert result["files_seen"] == 1, "B was never stat'ed"

        db = db_session_factory()
        try:
            paths = {row.file_path for row in db.query(Track).filter(Track.file_path.like(f"{lib}%")).all()}
        finally:
            db.close()
        assert paths == {str(a / "a-scoped.mp3")}

        # Nothing left to walk is nothing — not the whole library.
        assert scanner.scan_directory(str(lib), limit=100, within=[])["added"] == 0
        # The full walk still finds the rest.
        assert scanner.scan_directory(str(lib), limit=100)["added"] == 1
    finally:
        _delete_tracks_under(db_session_factory, str(lib))


# ---------------------------------------------------------------------------
# The setting
# ---------------------------------------------------------------------------


def test_the_setting_round_trips_and_drives_the_watcher(admin, monkeypatch):
    from app.routes import settings as settings_route

    calls = []
    monkeypatch.setattr(settings_route, "sync_folder_watch", lambda **kwargs: calls.append(kwargs))

    current = admin.get("/api/settings").json()
    assert current["watch_enabled"] is False
    payload = {key: value for key, value in current.items() if not key.endswith("_set")}

    payload["watch_enabled"] = True
    assert admin.put("/api/settings", json=payload).json()["watch_enabled"] is True
    assert calls[-1] == {"enabled": True}

    # A client built before the setting existed leaves it out: kept, not cleared.
    del payload["watch_enabled"]
    assert admin.put("/api/settings", json=payload).json()["watch_enabled"] is True
    assert admin.get("/api/settings").json()["watch_enabled"] is True

    payload["watch_enabled"] = False
    assert admin.put("/api/settings", json=payload).json()["watch_enabled"] is False
    assert calls[-1] == {"enabled": False}

    progress = admin.get("/api/scan/progress").json()
    assert progress["watch"]["state"] == "stopped"
    assert "folder-watch" in admin.get("/api/health").json()["capabilities"]


# ---------------------------------------------------------------------------
# The real thing
# ---------------------------------------------------------------------------


def test_a_file_landing_in_the_watched_folder_is_imported(client, db_session_factory, monkeypatch):
    """A watcher on the configured library, a file copied in slowly, and the
    row appears without a scan being asked for. Runs on real file events
    (FSEvents here, inotify in CI)."""
    from app.config import settings as config
    from app.models.track import Track
    from app.services import folder_watch as fw
    from app.services import scan_runner, scanner

    monkeypatch.setattr(scanner, "start_musicbrainz_backfill_background", lambda: False)

    library = Path(config.music_library_path)
    album = library / "Watched Artist" / "Watched Album"
    album.mkdir(parents=True, exist_ok=True)
    target = album / "landed.mp3"

    watcher = fw._Watcher(str(library), quiet=0.5, settle=0.2, retry=1.0)
    monkeypatch.setattr(fw, "_watcher", watcher)
    watcher.start()
    try:
        deadline = time.time() + 15
        while fw.get_watch_status()["state"] != "watching" and time.time() < deadline:
            time.sleep(0.05)
        assert fw.get_watch_status()["state"] == "watching", fw.get_watch_status()

        # A slow copy: the file appears small and grows. The settle check is
        # what keeps a half-written file out of the library.
        data = (FIXTURES / "tagged.mp3").read_bytes()
        with open(target, "wb") as handle:
            handle.write(data[:1000])
            handle.flush()
            time.sleep(0.3)
            handle.write(data[1000:])

        found = None
        deadline = time.time() + 25
        while time.time() < deadline:
            db = db_session_factory()
            try:
                found = db.query(Track).filter(Track.file_path == str(target)).first()
                if found:
                    db.expunge(found)
            finally:
                db.close()
            if found:
                break
            time.sleep(0.2)

        assert found is not None, fw.get_watch_status()
        assert found.file_size == len(data), "imported whole, not mid-copy"
        assert found.title

        status = fw.get_watch_status()
        assert status["last_import_at"] is not None
        assert status["last_added"] == 1
        progress = scan_runner.get_scan_progress()
        assert progress["source"] == "watch"
        assert progress["folders"] == 1
    finally:
        watcher.stop()
        watcher.join(timeout=5)
        _delete_tracks_under(db_session_factory, str(album))
        shutil.rmtree(library / "Watched Artist", ignore_errors=True)
