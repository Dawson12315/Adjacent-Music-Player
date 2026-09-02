"""Integration tests for the SQLite → Postgres migration engine.

These run only when the suite itself is on SQLite (a Postgres-hosted app has
nothing to migrate) and a target Postgres is reachable — in CI that is the
service container; locally, any Postgres on the MIGRATION_TEST_* coordinates.
Otherwise they skip rather than fail, so a bare `pytest` works anywhere.

The failure-injection test runs first: it proves a mid-flight crash leaves
SQLite untouched and the target wiped, which is the property the whole design
leans on. The success test then migrates the same data for real and checks it
row for row from the Postgres side.
"""

import os

import pytest
from sqlalchemy import create_engine, func, inspect, select, text


class _Params:
    host = os.environ.get("MIGRATION_TEST_PG_HOST", "127.0.0.1")
    port = int(os.environ.get("MIGRATION_TEST_PG_PORT", "55432"))
    database = os.environ.get("MIGRATION_TEST_PG_DATABASE", "adjacent")
    username = os.environ.get("MIGRATION_TEST_PG_USER", "adjacent")
    password = os.environ.get("MIGRATION_TEST_PG_PASSWORD", "adjacent")
    sslmode = "prefer"


def _target_available() -> bool:
    from app.services.pg_migration import build_postgres_url

    probe = create_engine(
        build_postgres_url(_Params), connect_args={"connect_timeout": 3}
    )
    try:
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        probe.dispose()


@pytest.fixture()
def migration_env(client, tmp_path, monkeypatch):
    """Sandbox the migration's file side effects and neutralize the restart."""
    from app.db import engine
    from app.services import maintenance_mode, pg_migration

    if engine.dialect.name != "sqlite":
        pytest.skip("migration source must be SQLite")

    if not _target_available():
        pytest.skip("no target Postgres reachable for migration tests")

    monkeypatch.setattr(
        pg_migration, "RUNTIME_DATABASE_CONFIG_PATH", tmp_path / "database.json"
    )
    monkeypatch.setattr(pg_migration, "SNAPSHOT_PATH", tmp_path / "snapshot.db")
    monkeypatch.setattr(pg_migration, "_schedule_restart", lambda: None)

    _seed_source_data(client)

    yield pg_migration

    maintenance_mode.clear()
    pg_migration._update(state="idle", step=None, error=None)


def _seed_source_data(client):
    """A lifelike source, independent of what other test files have done —
    pytest runs this file before the smoke tests, so it seeds its own world."""
    from app.db import SessionLocal
    from app.models.track import Track

    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "test-password-1"},
    )

    db = SessionLocal()
    try:
        if db.query(Track).count() == 0:
            for index in range(3):
                db.add(
                    Track(
                        title=f"Migration Song {index}",
                        artist="Migration Artist",
                        album="Migration Album",
                        genre="Electronic",
                        file_path=f"/nonexistent/migration-{index}.mp3",
                        duration_seconds=200 + index,
                    )
                )
            db.commit()
    finally:
        db.close()

    client.post("/api/playlists", json={"name": "Migration Playlist"})
    client.get("/api/playlists/liked-songs")


def _table_counts(engine) -> dict:
    from app.db import Base

    counts = {}
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            # job_locks is transient by design — the copy skips its rows and
            # lock bookkeeping creates them as a side effect of any run.
            if table.name == "job_locks":
                continue
            counts[table.name] = connection.execute(
                select(func.count()).select_from(table)
            ).scalar()
    return counts


def test_failed_migration_leaves_sqlite_untouched_and_target_clean(
    migration_env, monkeypatch
):
    from app.db import engine as live_engine
    from app.services import maintenance_mode

    pg_migration = migration_env
    before = _table_counts(live_engine)
    assert before["tracks"] > 0, "smoke tests should have seeded data"

    def _explode(*args, **kwargs):
        raise RuntimeError("injected failure during verify")

    monkeypatch.setattr(pg_migration, "_verify", _explode)

    pg_migration._run_migration(_Params)

    progress = pg_migration.get_migration_progress()
    assert progress["state"] == "failed"
    assert "injected failure" in progress["error"]

    # SQLite: byte-for-byte business as usual.
    assert _table_counts(live_engine) == before

    # Target: wiped, so the next attempt starts clean.
    target = create_engine(pg_migration.build_postgres_url(_Params))
    try:
        assert inspect(target).get_table_names() == []
    finally:
        target.dispose()

    # The app is writable again and no cutover config exists.
    assert maintenance_mode.current() is None
    assert not pg_migration.RUNTIME_DATABASE_CONFIG_PATH.exists()


def test_migration_copies_everything_and_writes_cutover(migration_env, client):
    import json

    from app.db import SessionLocal
    from app.db import engine as live_engine
    from app.models.listening_event import ListeningEvent
    from app.services import maintenance_mode

    pg_migration = migration_env

    # A pre-auth-era row: NULL user_id must be assigned to the admin.
    db = SessionLocal()
    try:
        track_id = db.execute(text("SELECT id FROM tracks LIMIT 1")).scalar()
        db.add(
            ListeningEvent(
                track_id=track_id,
                user_id=None,
                event_type="play_started",
                source_type="library",
            )
        )
        db.commit()
    finally:
        db.close()

    before = _table_counts(live_engine)

    pg_migration._run_migration(_Params)

    progress = pg_migration.get_migration_progress()
    assert progress["state"] == "restarting", progress["error"]
    assert progress["rows_done"] == progress["rows_total"] > 0

    config_path = pg_migration.RUNTIME_DATABASE_CONFIG_PATH
    assert config_path.exists()
    written = json.loads(config_path.read_text())
    assert written["database_url"].startswith("postgresql+psycopg://")
    assert written["engine"] == "postgresql"

    target = create_engine(pg_migration.build_postgres_url(_Params))
    try:
        after = _table_counts(target)
        for name, count in before.items():
            assert after[name] == count, f"{name}: {count} → {after[name]}"

        from app.db import Base

        tracks_table = Base.metadata.tables["tracks"]
        with target.connect() as connection:
            orphans = connection.execute(
                text("SELECT count(*) FROM listening_events WHERE user_id IS NULL")
            ).scalar()
            assert orphans == 0, "NULL user_id rows must be backfilled to the admin"

            # Sequences must be past the copied ids: a fresh insert works.
            # (Core insert, so Python-level column defaults apply.)
            new_id = connection.execute(
                tracks_table.insert()
                .values(title="post-migration insert", file_path="/tmp/x.mp3")
                .returning(tracks_table.c.id)
            ).scalar()
            connection.commit()
            assert new_id > 0

        # Leave the target clean for other runs of this suite.
        from app.db import Base

        Base.metadata.drop_all(bind=target)
    finally:
        target.dispose()

    # Cutover flips the app into its restart hold.
    assert maintenance_mode.current() == maintenance_mode.MODE_RESTARTING
    assert maintenance_mode.blocks("GET", "/api/tracks")
    assert not maintenance_mode.blocks("GET", "/api/settings/database/migration")
    assert not maintenance_mode.blocks("GET", "/api/health")
