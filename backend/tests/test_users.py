"""User-management endpoints.

Multi-user is gated on the engine: on SQLite every management call must 403
with a pointer to Settings → Server; on Postgres the full lifecycle works.
The same file asserts both, keyed off the engine the suite is running on.
"""

import pytest


@pytest.fixture()
def admin_client(client):
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


def _is_postgres() -> bool:
    from app.db import engine

    return engine.dialect.name == "postgresql"


def test_user_management_is_gated_by_engine(admin_client):
    response = admin_client.get("/api/users")

    if _is_postgres():
        assert response.status_code == 200
    else:
        assert response.status_code == 403
        assert "multi-user" in response.json()["detail"].lower()


def test_full_user_lifecycle(admin_client):
    if not _is_postgres():
        pytest.skip("user management requires the Postgres leg")

    created = admin_client.post("/api/users", json={"username": "sam", "role": "user"})
    assert created.status_code == 201
    body = created.json()
    assert body["user"]["username"] == "sam"
    assert body["user"]["must_change_password"] is True
    temp_password = body["temp_password"]
    assert len(temp_password) >= 10

    # Duplicate names refuse cleanly.
    duplicate = admin_client.post("/api/users", json={"username": "sam"})
    assert duplicate.status_code == 409

    listing = admin_client.get("/api/users")
    names = {user["username"] for user in listing.json()}
    assert {"admin", "sam"} <= names

    # The temp password signs in and carries the must-change flag...
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as sam:
        login = sam.post(
            "/api/auth/login", json={"username": "sam", "password": temp_password}
        )
        assert login.status_code == 200
        assert login.json()["user"]["must_change_password"] is True

        # ...which clears once they set their own password.
        changed = sam.patch(
            "/api/auth/me",
            json={
                "current_password": temp_password,
                "new_password": "sams-real-password-1",
                "confirm_password": "sams-real-password-1",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["user"]["must_change_password"] is False

    # Reset re-arms the flag with a fresh one-time password.
    sam_id = next(u["id"] for u in listing.json() if u["username"] == "sam")
    reset = admin_client.post(f"/api/users/{sam_id}/reset-password")
    assert reset.status_code == 200
    assert reset.json()["temp_password"] != temp_password

    # Deactivation locks them out.
    deactivated = admin_client.patch(f"/api/users/{sam_id}", json={"is_active": False})
    assert deactivated.status_code == 200

    with TestClient(app) as sam:
        login = sam.post(
            "/api/auth/login",
            json={"username": "sam", "password": reset.json()["temp_password"]},
        )
        assert login.status_code == 403


def test_admin_guard_rails(admin_client):
    if not _is_postgres():
        pytest.skip("user management requires the Postgres leg")

    me = admin_client.get("/api/auth/me").json()

    self_demote = admin_client.patch(f"/api/users/{me['id']}", json={"role": "user"})
    assert self_demote.status_code == 400

    self_deactivate = admin_client.patch(
        f"/api/users/{me['id']}", json={"is_active": False}
    )
    assert self_deactivate.status_code == 400


def test_delete_erases_the_profile_and_its_data(admin_client):
    if not _is_postgres():
        pytest.skip("user management requires the Postgres leg")

    from fastapi.testclient import TestClient

    from app.db import SessionLocal
    from app.main import app
    from app.models.listening_event import ListeningEvent
    from app.models.playlist import Playlist
    from app.models.track import Track
    from app.models.user import User

    # A track to interact with, independent of other test files.
    db = SessionLocal()
    try:
        track = db.query(Track).first()
        if track is None:
            track = Track(
                title="Delete-Test Song",
                artist="Delete Artist",
                file_path="/nonexistent/delete-test.mp3",
            )
            db.add(track)
            db.commit()
        track_id = track.id
    finally:
        db.close()

    created = admin_client.post("/api/users", json={"username": "gone", "role": "user"})
    assert created.status_code == 201
    gone_id = created.json()["user"]["id"]
    temp_password = created.json()["temp_password"]

    # The user lives a little: their own playlist, a like, a listening event.
    with TestClient(app) as gone:
        login = gone.post(
            "/api/auth/login", json={"username": "gone", "password": temp_password}
        )
        assert login.status_code == 200
        gone.patch(
            "/api/auth/me",
            json={
                "current_password": temp_password,
                "new_password": "gone-for-good-1",
                "confirm_password": "gone-for-good-1",
            },
        )
        assert gone.post("/api/playlists", json={"name": "Gone Mix"}).status_code == 200
        assert (
            gone.post(
                "/api/playlists/liked-songs/tracks", json={"track_id": track_id}
            ).status_code
            == 200
        )
        assert (
            gone.post(
                "/api/listening-events",
                json={
                    "track_id": track_id,
                    "event_type": "play_started",
                    "source_type": "library",
                },
            ).status_code
            == 200
        )

    deleted = admin_client.delete(f"/api/users/{gone_id}")
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted"] is True
    assert body["removed"]["playlists"] >= 2  # Gone Mix + their Ducking Good
    assert body["removed"]["listening_events"] >= 1

    # Everything of theirs is gone; the shared library is not.
    db = SessionLocal()
    try:
        assert db.query(User).filter(User.id == gone_id).first() is None
        assert (
            db.query(Playlist).filter(Playlist.user_id == gone_id).count() == 0
        )
        assert (
            db.query(ListeningEvent)
            .filter(ListeningEvent.user_id == gone_id)
            .count()
            == 0
        )
        assert db.query(Track).filter(Track.id == track_id).first() is not None
    finally:
        db.close()

    # Their credentials no longer work, and repeat deletion is a clean 404.
    with TestClient(app) as gone:
        login = gone.post(
            "/api/auth/login", json={"username": "gone", "password": "gone-for-good-1"}
        )
        assert login.status_code == 401

    assert admin_client.delete(f"/api/users/{gone_id}").status_code == 404


def test_delete_guard_rails(admin_client):
    if not _is_postgres():
        pytest.skip("user management requires the Postgres leg")

    me = admin_client.get("/api/auth/me").json()
    assert admin_client.delete(f"/api/users/{me['id']}").status_code == 400


def test_non_admin_cannot_manage_users(admin_client):
    if not _is_postgres():
        pytest.skip("user management requires the Postgres leg")

    created = admin_client.post(
        "/api/users", json={"username": "limited", "role": "user"}
    )
    assert created.status_code == 201

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as limited:
        login = limited.post(
            "/api/auth/login",
            json={
                "username": "limited",
                "password": created.json()["temp_password"],
            },
        )
        assert login.status_code == 200

        forbidden = limited.get("/api/users")
        assert forbidden.status_code == 403
