"""Cleanup, job locks and backups: the ways the server could lose data.

Cleanup is exercised through the service with a real directory tree, because
the failure being guarded against — an unmounted share reading as "every
file is gone" — is a filesystem fact, not a query.
"""

import shutil
import sqlite3
from datetime import datetime, timedelta

import pytest


@pytest.fixture()
def library(tmp_path, monkeypatch):
    from app.config import settings

    root = tmp_path / "music"
    root.mkdir()
    monkeypatch.setattr(settings, "music_library_path", str(root))
    return root


@pytest.fixture()
def seeded(client, db_session_factory, library):
    """Five tracks with real files, one listening event on the first."""
    from app.models.listening_event import ListeningEvent
    from app.models.track import Track

    db = db_session_factory()
    try:
        db.query(ListeningEvent).delete()
        db.query(Track).filter(Track.file_path.like("%cleanup-%")).delete(
            synchronize_session=False
        )
        db.commit()

        ids = []
        for index in range(5):
            path = library / f"cleanup-{index}.mp3"
            path.write_bytes(b"audio")
            track = Track(
                title=f"Cleanup {index}",
                artist="Cleanup Artist",
                file_path=str(path),
            )
            db.add(track)
            db.flush()
            ids.append(track.id)

        db.add(
            ListeningEvent(
                track_id=ids[0],
                user_id=None,
                event_type="play_started",
                source_type="library",
            )
        )
        db.commit()
    finally:
        db.close()

    return ids


def _run(db_session_factory, **kwargs):
    from app.services.maintenance import cleanup_missing_tracks

    db = db_session_factory()
    try:
        return cleanup_missing_tracks(db, **kwargs)
    finally:
        db.close()


def _track_ids(db_session_factory):
    from app.models.track import Track

    db = db_session_factory()
    try:
        return {row[0] for row in db.query(Track.id).all()}
    finally:
        db.close()


def _missing_since(db_session_factory, track_id):
    from app.models.track import Track

    db = db_session_factory()
    try:
        return db.get(Track, track_id).missing_since
    finally:
        db.close()


# --- the root itself -------------------------------------------------------


def test_empty_library_root_is_refused(seeded, library, db_session_factory):
    """Docker creates the mount point, so an unmounted share is an empty dir."""
    from app.services.maintenance import LibraryUnavailable

    shutil.rmtree(library)
    library.mkdir()

    with pytest.raises(LibraryUnavailable):
        _run(db_session_factory)

    assert set(seeded) <= _track_ids(db_session_factory)


def test_root_holding_none_of_our_files_is_refused(seeded, library, db_session_factory):
    from app.services.maintenance import LibraryUnavailable

    for path in library.iterdir():
        path.unlink()
    (library / "somebody-elses.mp3").write_bytes(b"x")

    with pytest.raises(LibraryUnavailable):
        _run(db_session_factory, force=True)

    assert set(seeded) <= _track_ids(db_session_factory)


def test_share_dropping_during_the_walk_is_caught(seeded, library, db_session_factory, monkeypatch):
    """The root is re-checked after the walk, so a drop mid-run deletes nothing."""
    from pathlib import Path

    from app.services.maintenance import LibraryUnavailable

    real_exists = Path.exists
    calls = {"n": 0}

    def flaky_exists(self):
        result = real_exists(self)
        calls["n"] += 1
        if calls["n"] == 2 and library.exists():
            # After the first track is seen present, the share vanishes.
            shutil.rmtree(library)
            library.mkdir()
        return result

    monkeypatch.setattr(Path, "exists", flaky_exists)

    with pytest.raises(LibraryUnavailable):
        _run(db_session_factory)

    assert set(seeded) <= _track_ids(db_session_factory)


# --- grace period, threshold, force ---------------------------------------


def test_missing_track_is_marked_then_removed_after_grace(seeded, library, db_session_factory):
    from app.models.listening_event import ListeningEvent
    from app.services.maintenance import CLEANUP_GRACE_DAYS

    (library / "cleanup-0.mp3").unlink()
    day_one = datetime(2026, 9, 1, 3, 0, 0)

    first = _run(db_session_factory, now=day_one)
    assert first["removed"] == 0
    assert first["marked_missing"] == 1
    assert seeded[0] in _track_ids(db_session_factory)
    assert _missing_since(db_session_factory, seeded[0]) == day_one

    # Still within grace a day later: nothing happens.
    second = _run(db_session_factory, now=day_one + timedelta(days=1))
    assert second["removed"] == 0
    assert second["still_missing"] == 1

    third = _run(db_session_factory, now=day_one + timedelta(days=CLEANUP_GRACE_DAYS))
    assert third["removed"] == 1
    assert seeded[0] not in _track_ids(db_session_factory)

    db = db_session_factory()
    try:
        assert db.query(ListeningEvent).filter_by(track_id=seeded[0]).count() == 0
    finally:
        db.close()


def test_returning_file_is_unmarked(seeded, library, db_session_factory):
    path = library / "cleanup-1.mp3"
    path.unlink()
    day_one = datetime(2026, 9, 1)

    _run(db_session_factory, now=day_one)
    assert _missing_since(db_session_factory, seeded[1]) == day_one

    path.write_bytes(b"back")
    result = _run(db_session_factory, now=day_one + timedelta(days=30))

    assert result["returned"] == 1
    assert result["removed"] == 0
    assert _missing_since(db_session_factory, seeded[1]) is None


def test_large_removal_is_refused_without_force(seeded, library, db_session_factory):
    from app.services.maintenance import CLEANUP_GRACE_DAYS, CleanupRefused

    for index in (0, 1, 2):
        (library / f"cleanup-{index}.mp3").unlink()
    day_one = datetime(2026, 9, 1)

    _run(db_session_factory, now=day_one)

    with pytest.raises(CleanupRefused) as refused:
        _run(db_session_factory, now=day_one + timedelta(days=CLEANUP_GRACE_DAYS))

    assert refused.value.missing == 3
    assert set(seeded) <= _track_ids(db_session_factory)

    forced = _run(db_session_factory, force=True, now=day_one + timedelta(days=1))
    assert forced["removed"] == 3
    assert _track_ids(db_session_factory) & set(seeded) == {seeded[3], seeded[4]}


def test_force_skips_the_grace_period_but_not_the_root_checks(seeded, library, db_session_factory):
    (library / "cleanup-4.mp3").unlink()

    result = _run(db_session_factory, force=True)

    assert result["removed"] == 1
    assert seeded[4] not in _track_ids(db_session_factory)


def test_a_backup_is_written_before_any_deletion(seeded, library, db_session_factory):
    from app.db import engine
    from app.services.db_backup import backup_directory

    if engine.dialect.name != "sqlite":
        pytest.skip("pre-cleanup backups are a SQLite safeguard; Postgres uses pg_dump")

    (library / "cleanup-2.mp3").unlink()
    _run(db_session_factory, force=True)

    copies = sorted(backup_directory().glob("*-pre-cleanup-*.db"))
    assert copies, "no pre-cleanup backup was written"

    with sqlite3.connect(str(copies[-1])) as copy:
        ids = {row[0] for row in copy.execute("SELECT id FROM tracks")}
    assert seeded[2] in ids, "the backup must predate the deletion"


# --- the route --------------------------------------------------------------


def _sign_in_admin(client):
    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )
    assert response.status_code == 200, response.text


def test_route_refuses_an_empty_root_and_reports_counts(client, seeded, library, db_session_factory):
    _sign_in_admin(client)

    (library / "cleanup-3.mp3").unlink()
    response = client.post("/api/maintenance/cleanup")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["removed"] == 0
    assert body["marked_missing"] == 1
    assert body["grace_days"] > 0

    shutil.rmtree(library)
    library.mkdir()
    response = client.post("/api/maintenance/cleanup")
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "library_unavailable"
    assert set(seeded) <= _track_ids(db_session_factory)


def test_route_asks_before_a_large_removal(client, seeded, library, db_session_factory):
    _sign_in_admin(client)

    for index in range(3):
        (library / f"cleanup-{index}.mp3").unlink()

    # Mark them missing as of a month ago so the grace period has elapsed.
    from app.models.track import Track

    db = db_session_factory()
    try:
        db.query(Track).filter(Track.id.in_(seeded[:3])).update(
            {Track.missing_since: datetime.utcnow() - timedelta(days=30)},
            synchronize_session=False,
        )
        db.commit()
    finally:
        db.close()

    refused = client.post("/api/maintenance/cleanup")
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "cleanup_refused"
    assert refused.json()["detail"]["missing"] == 3

    forced = client.post("/api/maintenance/cleanup", params={"force": "true"})
    assert forced.status_code == 200, forced.text
    assert forced.json()["removed"] == 3


# --- job locks --------------------------------------------------------------


def _hold_lock(db_session_factory, name):
    from app.services.job_locking import try_acquire_job_lock

    db = db_session_factory()
    try:
        assert try_acquire_job_lock(db, name)
    finally:
        db.close()


def _lock_running(db_session_factory, name):
    from app.models.job_lock import JobLock

    db = db_session_factory()
    try:
        lock = db.query(JobLock).filter_by(job_name=name).first()
        return bool(lock and lock.is_running)
    finally:
        db.close()


def _release(db_session_factory, name):
    from app.services.job_locking import release_job_lock

    db = db_session_factory()
    try:
        release_job_lock(db, name)
    finally:
        db.close()


@pytest.mark.parametrize("name", ["cleanup", "scan", "lastfm_enrichment"])
def test_a_skipped_run_leaves_the_running_jobs_lock_alone(client, db_session_factory, name):
    """The early return on a failed acquire used to sit inside the try whose
    finally released — unlocking the job that was actually running."""
    from app.services import scheduler
    from app.services.lastfm_enrichment_runner import run_lastfm_enrichment_with_lock

    _hold_lock(db_session_factory, name)
    try:
        if name == "cleanup":
            scheduler._run_cleanup_job()
        elif name == "scan":
            scheduler._run_scan_job()
        else:
            assert run_lastfm_enrichment_with_lock() is False

        assert _lock_running(db_session_factory, name), f"{name} lock was released by a skipped run"
    finally:
        _release(db_session_factory, name)


def test_staleness_is_measured_from_the_heartbeat(client, db_session_factory):
    from app.models.job_lock import JobLock
    from app.services.job_locking import STALE_LOCK_MINUTES, try_acquire_job_lock

    _hold_lock(db_session_factory, "scan")
    try:
        db = db_session_factory()
        try:
            lock = db.query(JobLock).filter_by(job_name="scan").one()
            # Started hours ago — the old rule would have called this hung.
            lock.started_at = datetime.utcnow() - timedelta(hours=3)
            lock.heartbeat_at = datetime.utcnow() - timedelta(minutes=1)
            db.commit()

            assert try_acquire_job_lock(db, "scan") is False

            lock.heartbeat_at = datetime.utcnow() - timedelta(minutes=STALE_LOCK_MINUTES + 1)
            db.commit()

            assert try_acquire_job_lock(db, "scan") is True
        finally:
            db.close()
    finally:
        _release(db_session_factory, "scan")


def test_heartbeat_touches_the_lock(client, db_session_factory):
    from app.models.job_lock import JobLock
    from app.services.job_locking import JobHeartbeat

    _hold_lock(db_session_factory, "scan")
    try:
        db = db_session_factory()
        try:
            lock = db.query(JobLock).filter_by(job_name="scan").one()
            lock.heartbeat_at = datetime.utcnow() - timedelta(hours=1)
            db.commit()
        finally:
            db.close()

        JobHeartbeat("scan", interval_seconds=0).tick()

        db = db_session_factory()
        try:
            lock = db.query(JobLock).filter_by(job_name="scan").one()
            assert datetime.utcnow() - lock.heartbeat_at < timedelta(seconds=5)
        finally:
            db.close()
    finally:
        _release(db_session_factory, "scan")


def test_no_job_starts_while_writes_are_paused(client, db_session_factory):
    from app.services import maintenance_mode
    from app.services.job_locking import try_acquire_job_lock

    maintenance_mode.enable_migration()
    try:
        db = db_session_factory()
        try:
            assert try_acquire_job_lock(db, "scan") is False
            assert try_acquire_job_lock(db, "cleanup") is False
            assert try_acquire_job_lock(db, "pg_migration") is True
        finally:
            db.close()
    finally:
        maintenance_mode.clear()
        _release(db_session_factory, "pg_migration")


def test_backfill_stops_when_writes_are_paused(client, db_session_factory, monkeypatch):
    from app.models.track import Track
    from app.services import maintenance_mode, musicbrainz_backfill

    db = db_session_factory()
    try:
        db.add(Track(title="No MBID yet", artist="Someone", file_path="/x/backfill.mp3"))
        db.commit()
    finally:
        db.close()

    looked_up = []
    monkeypatch.setattr(
        musicbrainz_backfill,
        "find_recording_mbid",
        lambda *args, **kwargs: looked_up.append(args) or None,
    )
    # The backfill refuses to run without a contact address before it looks
    # at anything else; a fresh checkout has none, so say one is configured.
    monkeypatch.setattr(musicbrainz_backfill, "contact_configured", lambda: True)

    maintenance_mode.enable_migration()
    try:
        summary = musicbrainz_backfill.backfill_musicbrainz_recording_ids(max_batches=1)
    finally:
        maintenance_mode.clear()

    assert summary.get("paused") is True
    assert looked_up == []


def test_cooccurrence_rebuild_holds_a_job_lock(client, db_session_factory):
    from app.services.recommendations.cooccurrence_builder import (
        COOCCURRENCE_JOB_NAME,
        rebuild_track_cooccurrence_standalone,
    )

    _hold_lock(db_session_factory, COOCCURRENCE_JOB_NAME)
    try:
        assert rebuild_track_cooccurrence_standalone() == {"skipped": "already_running"}
        assert _lock_running(db_session_factory, COOCCURRENCE_JOB_NAME)
    finally:
        _release(db_session_factory, COOCCURRENCE_JOB_NAME)

    result = rebuild_track_cooccurrence_standalone()
    assert "pairs_written" in result
    assert not _lock_running(db_session_factory, COOCCURRENCE_JOB_NAME)


# --- backups ----------------------------------------------------------------


def test_backup_is_a_complete_copy_and_rotates(client, db_session_factory):
    from app.db import engine
    from app.models.track import Track
    from app.services.db_backup import backup_directory, backup_sqlite_database

    if engine.dialect.name != "sqlite":
        pytest.skip("SQLite backups only")

    written = [backup_sqlite_database(label="test", keep=2) for _ in range(3)]
    remaining = sorted(backup_directory().glob("*-test-*.db"))

    assert len(remaining) == 2
    assert written[-1] in remaining
    assert not list(backup_directory().glob("*.part"))

    db = db_session_factory()
    try:
        live = db.query(Track).count()
    finally:
        db.close()

    with sqlite3.connect(str(written[-1])) as copy:
        assert copy.execute("SELECT count(*) FROM tracks").fetchone()[0] == live
        assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
