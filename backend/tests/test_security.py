"""Regression tests for the hardening applied after the exposure audit.

Each test pins one property that was found missing. They are written to fail
loudly if a future refactor quietly restores the old behaviour.
"""

import pytest


@pytest.fixture()
def signed_in(client):
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


# --------------------------------------------------------------------------
# Stream tokens must not work as session credentials
# --------------------------------------------------------------------------


def test_stream_token_is_rejected_as_a_session_cookie(signed_in, db_session_factory):
    """The audit's highest finding: stream tokens ride in URLs (HLS playlists,
    query strings, proxy logs) on the promise that they only grant streaming.
    Presented as a session cookie they must be refused."""
    from app.config import settings
    from app.models.track import Track
    from app.routes.tracks import create_stream_token, verify_stream_token

    me = signed_in.get("/api/auth/me").json()

    db = db_session_factory()
    try:
        track = db.query(Track).first()
        if track is None:
            track = Track(title="Token Test", file_path="/nonexistent/token.mp3")
            db.add(track)
            db.commit()
        track_id = track.id

        stream_token = create_stream_token(track_id=track_id, user_id=me["id"])

        # Sanity: the token really is valid for the thing it was minted for.
        assert verify_stream_token(stream_token, track_id=track_id, db=db) is True
    finally:
        db.close()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as fresh:
        fresh.cookies.set(settings.auth_cookie_name, stream_token)
        assert fresh.get("/api/auth/me").status_code == 401
        assert fresh.get("/api/playlists").status_code == 401
        assert fresh.get("/api/settings").status_code == 401


def test_session_tokens_still_work(signed_in):
    """The narrowing above must not touch ordinary sessions."""
    assert signed_in.get("/api/auth/me").status_code == 200
    assert signed_in.get("/api/playlists").status_code == 200


# --------------------------------------------------------------------------
# Password changes invalidate outstanding sessions
# --------------------------------------------------------------------------


def test_password_change_invalidates_other_sessions(client):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    client.post(
        "/api/auth/setup-admin",
        json={"username": "admin", "password": "test-password-1"},
    )
    client.post(
        "/api/auth/login", json={"username": "admin", "password": "test-password-1"}
    )

    # A second device, holding its own copy of the session cookie.
    stolen_cookie = client.cookies.get(settings.auth_cookie_name)
    assert stolen_cookie

    with TestClient(app) as other_device:
        other_device.cookies.set(settings.auth_cookie_name, stolen_cookie)
        assert other_device.get("/api/auth/me").status_code == 200

        changed = client.patch(
            "/api/auth/me",
            json={
                "current_password": "test-password-1",
                "new_password": "test-password-2",
                "confirm_password": "test-password-2",
            },
        )
        assert changed.status_code == 200

        # The old cookie is now worthless...
        assert other_device.get("/api/auth/me").status_code == 401

    # ...while the session that performed the change carries on.
    assert client.get("/api/auth/me").status_code == 200

    # Restore for any later test in the session-scoped client.
    client.patch(
        "/api/auth/me",
        json={
            "current_password": "test-password-2",
            "new_password": "test-password-1",
            "confirm_password": "test-password-1",
        },
    )


def test_tokens_without_a_pwd_claim_are_grandfathered(signed_in):
    """Deploying the change must not sign existing users out: tokens minted
    before the claim existed carry no 'pwd' and stay valid."""
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from app.config import settings
    from app.main import app

    me = signed_in.get("/api/auth/me").json()

    legacy_token = jwt.encode(
        {
            "sub": str(me["id"]),
            "username": me["username"],
            "role": me["role"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )

    from fastapi.testclient import TestClient

    with TestClient(app) as legacy_client:
        legacy_client.cookies.set(settings.auth_cookie_name, legacy_token)
        assert legacy_client.get("/api/auth/me").status_code == 200


# --------------------------------------------------------------------------
# Request body limits
# --------------------------------------------------------------------------


def test_oversized_body_is_refused_before_auth(client):
    oversized = "x" * (2 * 1024 * 1024)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": oversized},
    )
    assert response.status_code == 413


def test_normal_bodies_pass(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "wrong-password"},
    )
    # 401 (or 429 under repeated runs) — anything but the size refusal.
    assert response.status_code != 413


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_username_tier_survives_client_rotation():
    """The per-IP tier collapses behind a proxy and can be sidestepped by
    address rotation; the username ceiling must still engage."""
    from app.services.rate_limit import FailureRateLimiter

    limiter = FailureRateLimiter(max_failures=3, window_seconds=60)

    for _ in range(3):
        limiter.record_failure("victim")

    assert limiter.retry_after_seconds("victim") > 0
    assert limiter.retry_after_seconds("someone-else") == 0


# --------------------------------------------------------------------------
# Temp password strength and expiry
# --------------------------------------------------------------------------


def test_temp_passwords_carry_enough_entropy():
    import math

    from app.routes.users import _ADJECTIVES, _BIRDS, generate_temp_password

    space = len(_ADJECTIVES) ** 2 * len(_BIRDS) ** 2 * 90000
    assert math.log2(space) >= 35

    sample = generate_temp_password()
    assert len(sample.split("-")) == 5
    assert len({generate_temp_password() for _ in range(50)}) > 45


def test_expired_temp_password_is_refused(client, db_session_factory):
    from datetime import datetime, timedelta

    from app.db import engine
    from app.models.user import User
    from app.services.auth import hash_password

    if engine.dialect.name != "postgresql":
        pytest.skip("user creation via the admin API requires the Postgres leg")

    db = db_session_factory()
    try:
        stale = User(
            username="stale-temp",
            password_hash=hash_password("stale-temp-password-1"),
            role="user",
            is_active=True,
            must_change_password=True,
            temp_password_issued_at=datetime.utcnow() - timedelta(days=5),
        )
        db.add(stale)
        db.commit()
    finally:
        db.close()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as visitor:
        response = visitor.post(
            "/api/auth/login",
            json={"username": "stale-temp", "password": "stale-temp-password-1"},
        )
        assert response.status_code == 403
        assert "expired" in response.json()["detail"].lower()


def test_fresh_temp_password_still_works(client, db_session_factory):
    from datetime import datetime

    from app.models.user import User
    from app.services.auth import hash_password

    db = db_session_factory()
    try:
        fresh = User(
            username="fresh-temp",
            password_hash=hash_password("fresh-temp-password-1"),
            role="user",
            is_active=True,
            must_change_password=True,
            temp_password_issued_at=datetime.utcnow(),
        )
        db.add(fresh)
        db.commit()
    finally:
        db.close()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as visitor:
        response = visitor.post(
            "/api/auth/login",
            json={"username": "fresh-temp", "password": "fresh-temp-password-1"},
        )
        assert response.status_code == 200
        assert response.json()["user"]["must_change_password"] is True


# --------------------------------------------------------------------------
# Setup token
# --------------------------------------------------------------------------


def test_setup_status_reports_token_requirement(client):
    body = client.get("/api/auth/setup-status").json()
    assert "setup_token_required" in body
    # Unset in tests, so first-run stays zero-config exactly as before.
    assert body["setup_token_required"] is False


# --------------------------------------------------------------------------
# Transport / integration hygiene
# --------------------------------------------------------------------------


def test_lastfm_calls_use_https():
    from app.services.lastfm import LASTFM_BASE_URL

    assert LASTFM_BASE_URL.startswith("https://")


def test_cache_budget_helpers_exist_and_are_sane():
    from app.services import stream_cache_maintenance as scm

    assert scm.CACHE_BUDGET_BYTES > 0
    assert scm.MIN_FREE_DISK_BYTES > 0
    # Never blocks playback when the volume is healthy.
    assert scm.has_room_for_transcode() is True


# --------------------------------------------------------------------------
# Schema drift (the bug that broke migrated Postgres installs)
# --------------------------------------------------------------------------


def test_every_model_column_exists_in_the_database(client):
    """The models and the live schema must agree on both engines.

    users.temp_password_issued_at was added to the model and to the
    SQLite-only migration runner, which does not run on PostgreSQL — so
    migrated installs selected a column that did not exist and every
    authenticated request 500'd. sync_model_columns() closes that gap; this
    test fails if any future column reopens it.
    """
    from sqlalchemy import inspect

    from app.db import Base, engine

    inspector = inspect(engine)
    live_tables = set(inspector.get_table_names())
    missing = []

    for table in Base.metadata.sorted_tables:
        if table.name not in live_tables:
            missing.append(f"{table.name} (whole table)")
            continue

        live_columns = {c["name"] for c in inspector.get_columns(table.name)}

        for column in table.columns:
            if column.name not in live_columns:
                missing.append(f"{table.name}.{column.name}")

    assert not missing, f"schema is missing: {missing}"


def test_schema_sync_repairs_a_dropped_column(client, db_session_factory):
    """Drop a column behind SQLAlchemy's back, then prove the boot-time sync
    puts it back — the exact repair a migrated install needs."""
    from sqlalchemy import inspect, text

    from app.db import Base, engine
    from app.db_migrations import sync_model_columns

    if engine.dialect.name != "postgresql":
        pytest.skip("SQLite cannot drop columns on older versions; PG leg covers this")

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE users DROP COLUMN IF EXISTS temp_password_issued_at")
        )

    assert "temp_password_issued_at" not in {
        c["name"] for c in inspect(engine).get_columns("users")
    }

    sync_model_columns()

    assert "temp_password_issued_at" in {
        c["name"] for c in inspect(engine).get_columns("users")
    }

    # And the app works again.
    assert client.get("/api/auth/setup-status").status_code == 200
