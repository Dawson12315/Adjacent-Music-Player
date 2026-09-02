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
